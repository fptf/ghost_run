"""Обработка трека в воркере и пересчёт видимой части при смене дома."""

import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from botocore.exceptions import BotoCoreError, ClientError
from sqlalchemy import delete, func, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.config import Config
from app.domain.tracks.model import FileFormat, RejectReason, TrackRejectedError
from app.domain.tracks.pipeline import ProcessedTrack, Visibility, process
from app.infra import wkt
from app.infra.db import open_session
from app.infra.matching_service import save_pending, sync_group
from app.infra.models import Track, TrackSplit, TrackStatus, User
from app.infra.models import Visibility as Vis
from app.infra.s3 import s3_client
from app.infra.track_settings import load_configs
from app.infra.users_repo import get_home

if TYPE_CHECKING:
    from app.infra.queue import TaskQueue

log = logging.getLogger(__name__)

STUCK_AFTER = timedelta(minutes=10)
GIVE_UP_AFTER = timedelta(hours=1)


def track_prefix(user_id: uuid.UUID, track_id: uuid.UUID) -> str:
    return f"users/{user_id}/tracks/{track_id}/"


def source_key(track: Track) -> str:
    return f"{track_prefix(track.user_id, track.id)}source.{track.file_format}"


def _geom(ewkt: str | None) -> object:
    return func.ST_GeomFromEWKT(ewkt) if ewkt else None


def apply_visibility(track: Track, vis: Visibility) -> None:
    if vis.range is None:
        track.fully_hidden = True
        track.visible_from_m = track.visible_to_m = None
        track.visible_geometry = track.route_geometry = track.display_geometry = None
        track.start_point = track.finish_point = None
        track.visibility = Vis.private.value  # трек целиком в зоне — только приватный
        return
    track.fully_hidden = False
    track.visible_from_m, track.visible_to_m = vis.range.from_m, vis.range.to_m
    track.visible_geometry = _geom(wkt.linestring(vis.visible, "M"))
    track.route_geometry = _geom(wkt.linestring(vis.route, "M"))
    track.display_geometry = _geom(wkt.linestring(vis.display))
    track.start_point = _geom(wkt.point(*vis.visible[0][:2]))
    track.finish_point = _geom(wkt.point(*vis.visible[-1][:2]))


def _apply(db: Session, track: Track, result: ProcessedTrack) -> None:
    m = result.metrics
    start = result.clean.points[0].time
    track.started_at = start
    track.distance_m = m.distance_m
    track.total_time_s = m.total_time_s
    track.moving_time_s = m.moving_time_s
    track.avg_pace_s_per_km = m.avg_pace_s_per_km
    track.elevation_gain_m = m.elevation_gain_m
    track.has_elevation = m.has_elevation
    track.category = m.category
    track.geometry = _geom(wkt.linestring(result.full, "ZM"))
    track.full_display_geometry = _geom(wkt.linestring(result.full_display))
    apply_visibility(track, result.visibility)
    db.execute(delete(TrackSplit).where(TrackSplit.track_id == track.id))
    for s in m.splits:
        db.add(TrackSplit(track_id=track.id, idx=s.index, distance_m=s.distance_m, time_s=s.time_s))
    if not track.title and start is not None:
        track.title = default_title(start)


MONTHS = [
    "января", "февраля", "марта", "апреля", "мая", "июня",
    "июля", "августа", "сентября", "октября", "ноября", "декабря",
]  # fmt: skip


def default_title(started_at: datetime) -> str:
    return f"Пробежка {started_at.day} {MONTHS[started_at.month - 1]}"


def _download(cfg: Config, track: Track) -> bytes:
    try:
        body = s3_client(cfg, timeout_s=60).get_object(Bucket=cfg.s3_bucket, Key=source_key(track))
        return bytes(body["Body"].read())
    except (BotoCoreError, ClientError) as exc:
        raise TransientError(f"source of {track.id} unavailable") from exc


def _run(cfg: Config, db: Session, track: Track, user: User) -> ProcessedTrack:
    data = _download(cfg, track)
    metrics_cfg, geo_cfg = load_configs(db)
    return process(
        data,
        FileFormat(track.file_format),
        get_home(db, user),
        user.hide_radius_m,
        metrics_cfg,
        geo_cfg,
        seed=str(track.id),
    )


class TransientError(Exception):
    """Сбой хранилища или БД: трек остаётся в processing и будет обработан повторно."""


def process_track(cfg: Config, track_id: uuid.UUID) -> None:
    with open_session(cfg.database_url) as db:
        track = db.get(Track, track_id)
        if track is None or track.status != TrackStatus.processing.value:
            return
        user = db.get(User, track.user_id)
        assert user is not None
        try:
            result = _run(cfg, db, track, user)
            _apply(db, track, result)
        except TrackRejectedError as exc:
            db.rollback()
            _reject(db, track, exc.reason.value)
            return
        except (TransientError, OperationalError):
            db.rollback()
            raise
        except Exception:
            log.exception("track %s processing failed", track_id)
            db.rollback()
            _reject(db, track, RejectReason.broken_file.value)
            return
        track.status = TrackStatus.draft.value
        db.flush()
        # Совпадение с маршрутом — для плашки в превью; в группу трек попадёт при публикации.
        # Ошибка сопоставления не должна стоить бегуну обработанного трека — откатываем только её.
        try:
            with db.begin_nested():
                save_pending(db, track)
        except Exception:
            log.exception("matching failed for track %s", track_id)
        db.commit()


def _reject(db: Session, track: Track, reason: str) -> None:
    track.status = TrackStatus.rejected.value
    track.reject_reason = reason
    db.commit()


def requeue_stuck(cfg: Config, queue: "TaskQueue", now: datetime | None = None) -> int:
    """Треки, застрявшие в processing (упал воркер, недоступно хранилище), — снова в очередь.

    Слишком старые помечаются отклонёнными, чтобы бегун не ждал бесконечно.
    """
    now = now or datetime.now(UTC)
    with open_session(cfg.database_url) as db:
        stuck = (
            db.execute(
                select(Track).where(
                    Track.status == TrackStatus.processing.value,
                    Track.created_at < now - STUCK_AFTER,
                )
            )
            .scalars()
            .all()
        )
        requeued = 0
        for track in stuck:
            if track.created_at < now - GIVE_UP_AFTER:
                track.status = TrackStatus.rejected.value
                track.reject_reason = RejectReason.broken_file.value
            else:
                queue.process_track(track.id)
                requeued += 1
        db.commit()
        return requeued


def recompute_visibility(cfg: Config, user_id: uuid.UUID) -> None:
    """Пересчитывает видимую часть всех обработанных треков бегуна (смена дома или радиуса)."""
    with open_session(cfg.database_url) as db:
        user = db.get(User, user_id)
        if user is None:
            return
        tracks = db.execute(
            select(Track).where(
                Track.user_id == user_id,
                Track.status.in_([TrackStatus.draft.value, TrackStatus.published.value]),
            )
        ).scalars()
        for track in tracks:
            try:
                result = _run(cfg, db, track, user)
            except Exception:
                log.exception("visibility recompute failed for track %s", track.id)
                continue
            apply_visibility(track, result.visibility)
            db.flush()
            # видимая часть изменилась — членство в группе и попытка пересчитываются
            try:
                with db.begin_nested():
                    if track.status == TrackStatus.published.value:
                        sync_group(db, track)
                    else:
                        save_pending(db, track)
            except Exception:
                log.exception("rematch after visibility change failed for track %s", track.id)
        db.commit()
