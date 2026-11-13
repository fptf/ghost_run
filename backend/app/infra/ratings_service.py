"""Пересчёт популярности маршрутов (раз в час) и чтение рейтинга."""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import and_, delete, func, select
from sqlalchemy.orm import Session, aliased

from app.domain.ratings import Weights, popularity
from app.infra.models import (
    Attempt,
    AttemptState,
    PopularityScore,
    Track,
    TrackDownload,
    TrackStatus,
    User,
    Visibility,
)
from app.infra.settings_repo import get_setting

PERIOD_ALL = "all"


def _listed_roots() -> Any:
    return and_(
        Track.status == TrackStatus.published.value,
        Track.visibility == Visibility.public.value,
        Track.parent_track_id.is_(None),
        Track.deleted_at.is_(None),
        Track.hidden_by_moderator.is_(False),
        Track.category.is_not(None),
    )


def recalc(db: Session) -> int:
    """Пересчитывает популярность всех публичных исходных треков. Возвращает их число."""
    weights = Weights.from_setting(get_setting(db, "popularity.weights"))
    attempt_track = aliased(Track)
    runners_sq = (
        select(func.count(func.distinct(attempt_track.user_id)))
        .select_from(Attempt)
        .join(attempt_track, attempt_track.id == Attempt.track_id)
        .where(
            Attempt.root_track_id == Track.id,
            Attempt.state == AttemptState.active.value,
            attempt_track.user_id != Track.user_id,
            attempt_track.hidden_by_moderator.is_(False),
        )
        .correlate(Track)
        .scalar_subquery()
    )
    downloads_sq = (
        select(func.count())
        .where(TrackDownload.track_id == Track.id)
        .correlate(Track)
        .scalar_subquery()
    )
    rows = db.execute(
        select(Track.id, Track.category, runners_sq, downloads_sq).where(_listed_roots())
    ).all()
    now = datetime.now(UTC)
    ids = []
    for track_id, category, other_runners, downloads in rows:
        runners = int(other_runners) + 1  # автор маршрута — тоже бегун группы
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
    db.commit()
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
