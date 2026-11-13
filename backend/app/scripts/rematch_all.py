"""Пересопоставление всех опубликованных публичных треков в порядке публикации.

    python -m app.scripts.rematch_all

Сбрасывает связи «попытка → исходный трек» (кроме отвязанных бегуном) и строит группы заново:
каждый трек сопоставляется только с треками, опубликованными раньше него.
"""

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_config
from app.infra.db import get_engine
from app.infra.matching_service import sync_group
from app.infra.models import Attempt, AttemptState, Track, TrackStatus, Visibility


def rematch_all(db: Session) -> tuple[int, int]:
    db.execute(update(Track).values(parent_track_id=None))
    db.execute(delete(Attempt).where(Attempt.state != AttemptState.detached.value))
    db.flush()
    tracks = list(
        db.execute(
            select(Track)
            .where(
                Track.status == TrackStatus.published.value,
                Track.visibility == Visibility.public.value,
                Track.deleted_at.is_(None),
                Track.hidden_by_moderator.is_(False),
            )
            .order_by(Track.published_at, Track.id)
        ).scalars()
    )
    attached = 0
    for track in tracks:
        sync_group(db, track)
        db.flush()
        attached += track.parent_track_id is not None
    db.commit()
    return len(tracks), attached


def main() -> None:
    with sessionmaker(bind=get_engine(get_config().database_url))() as db:
        total, attached = rematch_all(db)
    print(f"Треков: {total}, стали попытками: {attached}, групп: {total - attached} исходных")


if __name__ == "__main__":
    main()
