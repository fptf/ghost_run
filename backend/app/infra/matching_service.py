"""Сопоставление треков с маршрутами и жизнь групп: привязка, отвязка, смена исходного трека."""

import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from geoalchemy2 import Geography
from sqlalchemy import and_, delete, func, literal, select
from sqlalchemy.orm import Session

from app.domain.matching import AttemptLine, MatchConfig, MatchResult, Route, compare, match
from app.infra.achievements_service import sync_achievements
from app.infra.models import Attempt, AttemptState, Track, TrackStatus, User, Visibility
from app.infra.settings_repo import get_setting


def load_config(db: Session) -> MatchConfig:
    def num(key: str) -> float:
        return float(get_setting(db, key))

    return MatchConfig(
        start_finish_radius_m=num("matching.start_finish_radius_m"),
        corridor_width_m=num("matching.corridor_width_m"),
        corridor_coverage=num("matching.corridor_coverage"),
        length_tolerance=num("matching.length_tolerance"),
        loop_threshold_m=num("matching.loop_threshold_m"),
        direction_min_share=num("matching.direction_min_share"),
        tie_threshold_s=num("comparison.tie_threshold_s"),
    )


# ---------- Чтение геометрий ----------


def route_of(db: Session, root: Track) -> Route | None:
    raw = db.execute(
        select(func.ST_AsGeoJSON(Track.route_geometry, 7)).where(Track.id == root.id)
    ).scalar_one_or_none()
    if not raw or root.distance_m is None or root.total_time_s is None:
        return None
    coords = json.loads(raw)["coordinates"]
    return Route(
        points=[(float(c[0]), float(c[1])) for c in coords],
        full_distance_m=root.distance_m,
        visible_from_m=root.visible_from_m or 0.0,
        visible_to_m=root.visible_to_m if root.visible_to_m is not None else root.distance_m,
        total_time_s=root.total_time_s,
    )


def attempt_of(db: Session, track: Track) -> AttemptLine | None:
    dump = func.ST_DumpPoints(Track.geometry).table_valued("path", "geom")
    rows = db.execute(
        select(func.ST_X(dump.c.geom), func.ST_Y(dump.c.geom), func.ST_M(dump.c.geom))
        .select_from(Track)
        .join(dump, literal(True))
        .where(Track.id == track.id)
        .order_by(dump.c.path)
    ).all()
    if len(rows) < 2:
        return None
    return AttemptLine(points=[(float(x), float(y), float(m)) for x, y, m in rows])


# ---------- Кандидаты и лучшее совпадение ----------


def _root_conditions() -> list[Any]:
    return [
        Track.status == TrackStatus.published.value,
        Track.visibility == Visibility.public.value,
        Track.parent_track_id.is_(None),
        Track.match_excluded.is_(False),
        Track.root_closed.is_(False),
        Track.deleted_at.is_(None),
        Track.hidden_by_moderator.is_(False),
        Track.route_geometry.is_not(None),
    ]


def candidates(db: Session, track: Track, cfg: MatchConfig) -> list[Track]:
    """Старт видимой части маршрута в 50 м от линии трека; маршрут не длиннее трека + 3%."""
    attempt_geom = (
        select(func.ST_Force2D(Track.geometry)).where(Track.id == track.id).scalar_subquery()
    )
    visible_len = func.coalesce(Track.visible_to_m, Track.distance_m) - func.coalesce(
        Track.visible_from_m, 0
    )
    conds = _root_conditions() + [
        Track.id != track.id,
        func.ST_DWithin(
            Track.start_point.cast(Geography),
            attempt_geom.cast(Geography),
            cfg.start_finish_radius_m,
        ),
        visible_len <= (track.distance_m or 0) * (1 + cfg.length_tolerance),
    ]
    if track.published_at is not None:
        # исходный — первый опубликованный: маршрут должен быть опубликован раньше
        conds.append(Track.published_at < track.published_at)
    return list(db.execute(select(Track).where(and_(*conds))).scalars())


@dataclass(frozen=True)
class Found:
    root: Track
    result: MatchResult


def evaluate(db: Session, root: Track, track: Track, cfg: MatchConfig) -> MatchResult | None:
    route = route_of(db, root)
    line = attempt_of(db, track)
    if route is None or line is None:
        return None
    return match(route, line, cfg)


def best_match(db: Session, track: Track, cfg: MatchConfig | None = None) -> Found | None:
    cfg = cfg or load_config(db)
    if track.match_excluded or track.geometry is None:
        return None
    best: Found | None = None
    for root in candidates(db, track, cfg):
        result = evaluate(db, root, track, cfg)
        if result and result.matched and (best is None or result.coverage > best.result.coverage):
            best = Found(root=root, result=result)
    return best


# ---------- Запись попытки ----------


def _upsert_attempt(
    db: Session, track: Track, found: Found, state: AttemptState, cfg: MatchConfig
) -> Attempt:
    r = found.result
    by_author = found.root.user_id == track.user_id
    cmp = compare(r.result_time_s, found.root.total_time_s or 0.0, cfg.tie_threshold_s)
    attempt = db.execute(select(Attempt).where(Attempt.track_id == track.id)).scalar_one_or_none()
    if attempt is None:
        attempt = Attempt(track_id=track.id)
        db.add(attempt)
    attempt.root_track_id = found.root.id
    if state == AttemptState.active and attempt.state != AttemptState.active.value:
        attempt.activated_at = datetime.now(UTC)
    attempt.state = state.value
    attempt.segment_time_s = r.segment_time_s
    attempt.hidden_time_s = r.hidden_time_s
    attempt.result_time_s = r.result_time_s
    attempt.diff_s = cmp.diff_s
    attempt.beat = cmp.faster and not by_author
    attempt.by_author = by_author
    attempt.coverage = r.coverage
    attempt.start_gap_m = r.start_gap_m
    attempt.finish_gap_m = r.finish_gap_m
    attempt.direction_share = r.direction_share
    attempt.length_ratio = r.length_ratio
    attempt.segment_distance_m = r.segment_distance_m
    attempt.trimmed = r.trimmed
    db.flush()
    sync_achievements(db, track)
    return attempt


def attempt_row(db: Session, track_id: uuid.UUID) -> Attempt | None:
    return db.execute(select(Attempt).where(Attempt.track_id == track_id)).scalar_one_or_none()


def has_group(db: Session, root_id: uuid.UUID) -> bool:
    return (
        db.execute(
            select(func.count()).where(
                Attempt.root_track_id == root_id, Attempt.state == AttemptState.active.value
            )
        ).scalar_one()
        > 0
    )


def save_pending(db: Session, track: Track) -> None:
    """После обработки: запоминаем совпадение для плашки в превью."""
    cfg = load_config(db)
    found = best_match(db, track, cfg)
    if found is None:
        db.execute(delete(Attempt).where(Attempt.track_id == track.id))
    else:
        _upsert_attempt(db, track, found, AttemptState.pending, cfg)


def _leave_group(db: Session, track: Track, state: AttemptState) -> None:
    track.parent_track_id = None
    attempt = attempt_row(db, track.id)
    if attempt is not None:
        attempt.state = state.value
    db.flush()
    sync_achievements(db, track)


def sync_group(db: Session, track: Track) -> None:
    """Приводит членство в группе в соответствие с видимостью и статусом трека.

    Вызывается после публикации и любых изменений видимости.
    """
    is_public = (
        track.status == TrackStatus.published.value
        and track.visibility == Visibility.public.value
        and track.deleted_at is None
        and not track.hidden_by_moderator
    )
    if has_group(db, track.id):
        # исходный трек с группой: непубличный перестаёт принимать попытки, группа остаётся
        track.root_closed = not is_public
        return
    if not is_public or track.match_excluded:
        _leave_group(
            db, track, AttemptState.detached if track.match_excluded else AttemptState.pending
        )
        return
    cfg = load_config(db)
    found = best_match(db, track, cfg)
    if found is None:
        _leave_group(db, track, AttemptState.detached)
        db.execute(delete(Attempt).where(Attempt.track_id == track.id))
        sync_achievements(db, track)
        return
    track.parent_track_id = found.root.id
    _upsert_attempt(db, track, found, AttemptState.active, cfg)


def detach(db: Session, track: Track) -> None:
    """«Не засчитывать»: трек становится обычным и больше ни с чем не сопоставляется."""
    track.match_excluded = True
    _leave_group(db, track, AttemptState.detached)


def promote_next_root(db: Session, root: Track) -> Track | None:
    """Исходным становится самая ранняя по публикации попытка; остальные пересчитываются."""
    rows = list(
        db.execute(
            select(Track)
            .join(Attempt, Attempt.track_id == Track.id)
            .where(Attempt.root_track_id == root.id, Attempt.state == AttemptState.active.value)
            .order_by(Track.published_at, Track.id)
        ).scalars()
    )
    if not rows:
        return None
    new_root, rest = rows[0], rows[1:]
    new_root.parent_track_id = None
    db.execute(delete(Attempt).where(Attempt.track_id == new_root.id))
    db.flush()
    sync_achievements(db, new_root)  # исходный трек ачивок не получает
    cfg = load_config(db)
    for track in rest:
        result = evaluate(db, new_root, track, cfg)
        if result and result.matched:
            track.parent_track_id = new_root.id
            _upsert_attempt(
                db, track, Found(root=new_root, result=result), AttemptState.active, cfg
            )
        else:
            track.parent_track_id = None
            db.execute(delete(Attempt).where(Attempt.track_id == track.id))
            sync_achievements(db, track)
    return new_root


def hide_by_moderator(db: Session, track: Track) -> None:
    """Скрытие модератором (интерфейс модерации — этап 2): ачивки этого трека отзываются."""
    track.hidden_by_moderator = True
    if has_group(db, track.id):
        promote_next_root(db, track)
    else:
        _leave_group(db, track, AttemptState.detached)
    sync_achievements(db, track)
    db.commit()


def before_account_deletion(db: Session, user_id: uuid.UUID) -> None:
    """Группы переживают удаление аккаунта автора: исходным становится следующий трек."""
    roots = db.execute(
        select(Track).where(
            Track.user_id == user_id,
            Track.id.in_(
                select(Attempt.root_track_id).where(Attempt.state == AttemptState.active.value)
            ),
        )
    ).scalars()
    for root in list(roots):
        # попытки самого автора на свой маршрут уйдут вместе с аккаунтом
        db.execute(
            delete(Attempt).where(
                Attempt.root_track_id == root.id,
                Attempt.track_id.in_(select(Track.id).where(Track.user_id == user_id)),
            )
        )
        promote_next_root(db, root)
    db.flush()


# ---------- Таблица группы ----------


def root_of(db: Session, track: Track) -> Track:
    if track.parent_track_id is None:
        return track
    parent = db.get(Track, track.parent_track_id)
    return parent or track


def group_rows(db: Session, root: Track) -> list[dict[str, Any]]:
    """Лучший результат каждого бегуна (включая автора): место, время, число попыток."""
    author = db.get(User, root.user_id)
    entries: list[dict[str, Any]] = []
    if author is not None and root.total_time_s is not None:
        entries.append(
            {
                "user": author,
                "track_id": root.id,
                "time_s": root.total_time_s,
                "date": root.started_at,
                "beat": False,
                "is_author": True,
                "is_root": True,
            }
        )
    attempts = db.execute(
        select(Attempt, Track, User)
        .join(Track, Track.id == Attempt.track_id)
        .join(User, User.id == Track.user_id)
        .where(
            Attempt.root_track_id == root.id,
            Attempt.state == AttemptState.active.value,
            Track.hidden_by_moderator.is_(False),
        )
    ).all()
    for attempt, track, user in attempts:
        entries.append(
            {
                "user": user,
                "track_id": track.id,
                "time_s": attempt.result_time_s,
                "date": track.started_at,
                "beat": attempt.beat,
                "is_author": attempt.by_author,
                "is_root": False,
            }
        )
    best: dict[uuid.UUID, dict[str, Any]] = {}
    counts: dict[uuid.UUID, int] = {}
    for e in entries:
        uid = e["user"].id
        counts[uid] = counts.get(uid, 0) + 1
        if uid not in best or e["time_s"] < best[uid]["time_s"]:
            best[uid] = e
    rows = sorted(best.values(), key=lambda e: e["time_s"])
    for place, row in enumerate(rows, start=1):
        row["place"] = place
        row["runs"] = counts[row["user"].id]
    return rows


def soft_delete_root(track: Track) -> None:
    track.deleted_at = datetime.now(UTC)
    track.root_closed = True
