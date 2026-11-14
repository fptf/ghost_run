"""Пересчёт популярности маршрутов (раз в час) и чтение рейтинга."""

from datetime import UTC, datetime

from sqlalchemy import ColumnElement, and_, delete, func, select
from sqlalchemy.orm import Session

from app.domain.ratings import Weights, popularity
from app.infra.models import PopularityScore, Track, TrackDownload, User
from app.infra.settings_repo import get_setting
from app.infra.tracks_repo import group_runners, public_root

PERIOD_ALL = "all"


def _listed_roots() -> ColumnElement[bool]:
    return and_(public_root(), Track.category.is_not(None))


def recalc(db: Session) -> int:
    """Пересчитывает популярность всех публичных исходных треков. Возвращает их число."""
    weights = Weights.from_setting(get_setting(db, "popularity.weights"))
    downloads_sq = (
        select(func.count())
        .where(TrackDownload.track_id == Track.id)
        .correlate(Track)
        .scalar_subquery()
    )
    rows = db.execute(
        select(Track.id, Track.category, group_runners(), downloads_sq).where(_listed_roots())
    ).all()
    now = datetime.now(UTC)
    ids = []
    for track_id, category, runners_raw, downloads in rows:
        runners = int(runners_raw)
        likes = 0  # лайков в MVP нет (ФТ-31 — этап 2)
        ids.append(track_id)
        db.merge(
            PopularityScore(
                track_id=track_id,
                period=PERIOD_ALL,
                category=category,
                runners=runners,
                downloads=int(downloads),
                likes=likes,
                value=popularity(runners, int(downloads), likes, weights),
                computed_at=now,
            )
        )
    db.execute(
        delete(PopularityScore).where(
            PopularityScore.period == PERIOD_ALL, PopularityScore.track_id.not_in(ids)
        )
        if ids
        else delete(PopularityScore).where(PopularityScore.period == PERIOD_ALL)
    )
    return len(ids)


def rating(db: Session, category: str, limit: int) -> list[tuple[PopularityScore, Track, User]]:
    return [
        (score, track, user)
        for score, track, user in db.execute(
            select(PopularityScore, Track, User)
            .join(Track, Track.id == PopularityScore.track_id)
            .join(User, User.id == Track.user_id)
            .where(
                PopularityScore.period == PERIOD_ALL,
                PopularityScore.category == category,
                _listed_roots(),
            )
            .order_by(PopularityScore.value.desc(), Track.published_at.asc(), Track.id)
            .limit(limit)
        ).all()
    ]
