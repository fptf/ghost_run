"""Ачивки: «Превзошёл» существует, пока попытка в группе и быстрее автора маршрута."""

import uuid
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.infra.models import (
    Achievement,
    Attempt,
    AttemptState,
    Track,
    TrackStatus,
    UserAchievement,
    Visibility,
)

OUTPERFORMED = "outperformed"


def _achievement_id(db: Session, code: str) -> int | None:
    return db.execute(select(Achievement.id).where(Achievement.code == code)).scalar_one_or_none()


def sync_achievements(db: Session, track: Track) -> None:
    """Приводит ачивку «Превзошёл» за трек в соответствие с состоянием попытки. Идемпотентно."""
    ach_id = _achievement_id(db, OUTPERFORMED)
    if ach_id is None:
        return
    attempt = db.execute(select(Attempt).where(Attempt.track_id == track.id)).scalar_one_or_none()
    deserved = (
        attempt is not None
        and attempt.state == AttemptState.active.value
        and attempt.beat
        and not attempt.by_author
        and not track.hidden_by_moderator
        and track.deleted_at is None
    )
    if deserved:
        db.execute(
            insert(UserAchievement)
            .values(user_id=track.user_id, achievement_id=ach_id, track_id=track.id)
            .on_conflict_do_nothing(constraint="user_achievement_once")
        )
    else:
        db.execute(
            delete(UserAchievement).where(
                UserAchievement.track_id == track.id, UserAchievement.achievement_id == ach_id
            )
        )


def track_achievements(db: Session, track_id: uuid.UUID) -> list[Achievement]:
    return list(
        db.execute(
            select(Achievement)
            .join(UserAchievement, UserAchievement.achievement_id == Achievement.id)
            .where(UserAchievement.track_id == track_id)
        ).scalars()
    )


def user_showcase(db: Session, user_id: uuid.UUID, public_only: bool) -> list[dict[str, Any]]:
    stmt = (
        select(Achievement, UserAchievement, Track)
        .join(UserAchievement, UserAchievement.achievement_id == Achievement.id)
        .join(Track, Track.id == UserAchievement.track_id)
        .where(UserAchievement.user_id == user_id)
        .order_by(UserAchievement.awarded_at.desc())
    )
    if public_only:
        stmt = stmt.where(
            Track.status == TrackStatus.published.value,
            Track.visibility == Visibility.public.value,
        )
    grouped: dict[str, dict[str, Any]] = {}
    for ach, ua, track in db.execute(stmt).all():
        item = grouped.setdefault(
            ach.code,
            {"achievement": ach, "items": []},
        )
        item["items"].append({"track_id": track.id, "title": track.title, "at": ua.awarded_at})
    return list(grouped.values())


def new_attempts(db: Session, owner_id: uuid.UUID) -> dict[uuid.UUID, int]:
    """Новые попытки других бегунов на исходных треках автора: {root_id: число}."""
    root = Track.__table__.alias("root")
    rows = db.execute(
        select(Attempt.root_track_id, func.count())
        .join(root, root.c.id == Attempt.root_track_id)
        .where(
            root.c.user_id == owner_id,
            Attempt.state == AttemptState.active.value,
            Attempt.by_author.is_(False),
            Attempt.activated_at.is_not(None),
            (root.c.attempts_seen_at.is_(None)) | (Attempt.activated_at > root.c.attempts_seen_at),
        )
        .group_by(Attempt.root_track_id)
    ).all()
    return {r[0]: int(r[1]) for r in rows}
