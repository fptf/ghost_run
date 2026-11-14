import json
import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import ColumnElement, Select, and_, func, select
from sqlalchemy.orm import InstrumentedAttribute, Session, aliased

from app.infra.models import (
    Attempt,
    AttemptState,
    Track,
    TrackPhoto,
    TrackSplit,
    TrackStatus,
    User,
    Visibility,
)

PROCESSED = (TrackStatus.draft.value, TrackStatus.published.value)


# ---------- Публичность ----------


def published_public() -> ColumnElement[bool]:
    """Трек опубликован с видимостью «публичный»."""
    return and_(
        Track.status == TrackStatus.published.value, Track.visibility == Visibility.public.value
    )


def listed_public() -> ColumnElement[bool]:
    """Публичный трек виден всем: опубликован, не удалён автором, не скрыт модератором."""
    return and_(
        published_public(), Track.deleted_at.is_(None), Track.hidden_by_moderator.is_(False)
    )


def public_root() -> ColumnElement[bool]:
    """Публичный трек, который не попытка: маршрут в поиске, рейтинге и сопоставлении."""
    return and_(listed_public(), Track.parent_track_id.is_(None))


def is_listed_public(track: Track) -> bool:
    """То же, что listed_public(), для загруженного трека."""
    return (
        track.status == TrackStatus.published.value
        and track.visibility == Visibility.public.value
        and track.deleted_at is None
        and not track.hidden_by_moderator
    )


def public_filter(stmt: Select[Any]) -> Select[Any]:
    return stmt.where(published_public())


# ---------- Группа ----------


def group_runners() -> ColumnElement[int]:
    """Бегунов в группе маршрута Track (коррелированный подзапрос): автор и все, у кого есть
    засчитанная попытка, не скрытая модератором."""
    runner = aliased(Track)
    others = (
        select(func.count(func.distinct(runner.user_id)))
        .select_from(Attempt)
        .join(runner, runner.id == Attempt.track_id)
        .where(
            Attempt.root_track_id == Track.id,
            Attempt.state == AttemptState.active.value,
            runner.user_id != Track.user_id,
            runner.hidden_by_moderator.is_(False),
        )
        .correlate(Track)
        .scalar_subquery()
    )
    return others + 1  # автор маршрута — тоже бегун группы


def runners_count(db: Session, root_id: uuid.UUID) -> int:
    return int(db.execute(select(group_runners()).where(Track.id == root_id)).scalar_one())


def user_tracks(db: Session, user_id: uuid.UUID, public_only: bool) -> list[Track]:
    stmt = select(Track).where(Track.user_id == user_id, Track.deleted_at.is_(None))
    stmt = public_filter(stmt) if public_only else stmt
    return list(db.execute(stmt.order_by(Track.created_at.desc())).scalars())


@dataclass(frozen=True)
class RunnerStats:
    runs: int
    total_distance_m: int
    records: dict[str, int]  # категория -> лучшее время, с


def stats(db: Session, user_id: uuid.UUID, public_only: bool) -> RunnerStats:
    base = select(Track).where(Track.user_id == user_id, Track.deleted_at.is_(None))
    base = public_filter(base) if public_only else base.where(Track.status.in_(PROCESSED))
    sub = base.subquery()
    runs, total = db.execute(
        select(func.count(), func.coalesce(func.sum(sub.c.distance_m), 0)).select_from(sub)
    ).one()
    records = dict(
        db.execute(
            select(sub.c.category, func.min(sub.c.total_time_s))
            .where(sub.c.category.is_not(None))
            .group_by(sub.c.category)
        ).all()
    )
    return RunnerStats(
        runs=int(runs),
        total_distance_m=int(round(float(total))),
        records={k: int(round(v)) for k, v in records.items()},
    )


def with_author(db: Session, track_id: uuid.UUID) -> tuple[Track, User] | None:
    """Трек и его автор; None, если трека нет."""
    track = db.get(Track, track_id)
    user = db.get(User, track.user_id) if track else None
    if track is None or user is None:
        return None
    return track, user


def author(db: Session, track: Track) -> User:
    user = db.get(User, track.user_id)
    assert user is not None  # user_id — внешний ключ с каскадным удалением
    return user


def geojson(
    db: Session, track_id: uuid.UUID, column: InstrumentedAttribute[Any]
) -> dict[str, Any] | None:
    """Геометрия трека из колонки column (например, Track.display_geometry) в GeoJSON."""
    raw = db.execute(
        select(func.ST_AsGeoJSON(column, 7)).where(Track.id == track_id)
    ).scalar_one_or_none()
    return json.loads(raw) if raw else None


def splits(db: Session, track_id: uuid.UUID) -> list[TrackSplit]:
    return list(
        db.execute(
            select(TrackSplit).where(TrackSplit.track_id == track_id).order_by(TrackSplit.idx)
        ).scalars()
    )


def photos(db: Session, track_id: uuid.UUID) -> list[TrackPhoto]:
    return list(
        db.execute(
            select(TrackPhoto)
            .where(TrackPhoto.track_id == track_id)
            .order_by(TrackPhoto.created_at, TrackPhoto.id)
        ).scalars()
    )


def find_duplicate(db: Session, user_id: uuid.UUID, sha256: str) -> Track | None:
    return db.execute(
        select(Track).where(
            Track.user_id == user_id, Track.file_sha256 == sha256, Track.deleted_at.is_(None)
        )
    ).scalar_one_or_none()


def can_view(track: Track, viewer_id: uuid.UUID | None) -> bool:
    if track.deleted_at is not None:
        return False  # удалён автором; группа видна через попытки
    if viewer_id == track.user_id:
        return True
    if track.hidden_by_moderator:
        return False
    return track.status == TrackStatus.published.value and track.visibility in (
        Visibility.public.value,
        Visibility.link.value,
    )
