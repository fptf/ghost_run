import json
import uuid
from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.infra.models import Track, TrackPhoto, TrackSplit, TrackStatus, Visibility

PROCESSED = (TrackStatus.draft.value, TrackStatus.published.value)


def public_filter(stmt: Select[Any]) -> Select[Any]:
    return stmt.where(
        Track.status == TrackStatus.published.value, Track.visibility == Visibility.public.value
    )


def user_tracks(db: Session, user_id: uuid.UUID, public_only: bool) -> list[Track]:
    stmt = select(Track).where(Track.user_id == user_id, Track.deleted_at.is_(None))
    stmt = public_filter(stmt) if public_only else stmt
    return list(db.execute(stmt.order_by(Track.created_at.desc())).scalars())


def stats(db: Session, user_id: uuid.UUID, public_only: bool) -> dict[str, Any]:
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
    return {
        "runs": int(runs),
        "total_distance_m": int(round(float(total))),
        "records": {k: int(round(v)) for k, v in records.items()},
    }


def geojson(db: Session, track_id: uuid.UUID, column: str) -> dict[str, Any] | None:
    raw = db.execute(
        select(func.ST_AsGeoJSON(getattr(Track, column), 7)).where(Track.id == track_id)
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
        select(Track).where(Track.user_id == user_id, Track.file_sha256 == sha256)
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
