"""Пересопоставление всех опубликованных публичных треков в порядке публикации.

    python -m app.scripts.rematch_all

Сбрасывает связи «попытка → исходный трек» (кроме отвязанных бегуном) и строит группы заново:
каждый трек сопоставляется только с треками, опубликованными раньше него.
"""

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.infra.db import open_session
from app.infra.matching_service import sync_group
from app.infra.models import Attempt, AttemptState, Track
from app.infra.tracks_repo import listed_public


def rematch_all(db: Session) -> tuple[int, int]:
    db.execute(update(Track).values(parent_track_id=None))
    db.execute(delete(Attempt).where(Attempt.state != AttemptState.detached.value))
    db.flush()
    tracks = list(
        db.execute(
            select(Track).where(listed_public()).order_by(Track.published_at, Track.id)
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
    with open_session() as db:
        total, attached = rematch_all(db)
    print(f"Треков: {total}, стали попытками: {attached}, групп: {total - attached} исходных")


if __name__ == "__main__":
    main()
