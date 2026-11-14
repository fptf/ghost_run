import uuid
from typing import Any

from sqlalchemy.exc import OperationalError

from app.config import get_config
from app.infra.celery_app import celery_app
from app.infra.db import open_session
from app.infra.track_processing import (
    TransientError,
    process_track,
    recompute_visibility,
    requeue_stuck,
)

DEFAULT_RECALC_S = 3600
STUCK_CHECK_S = 300


@celery_app.task(name="ping")
def ping() -> str:
    return "pong"


@celery_app.task(
    name="process_track",
    autoretry_for=(TransientError, OperationalError),
    retry_backoff=5,
    max_retries=5,
)
def process_track_task(track_id: str) -> None:
    process_track(get_config(), uuid.UUID(track_id))


@celery_app.task(name="requeue_stuck_tracks")
def requeue_stuck_task() -> int:
    from app.infra.queue import CeleryQueue

    return requeue_stuck(get_config(), CeleryQueue())


@celery_app.task(name="recompute_visibility")
def recompute_visibility_task(user_id: str) -> None:
    recompute_visibility(get_config(), uuid.UUID(user_id))


@celery_app.task(name="recalc_popularity")
def recalc_popularity_task() -> int:
    from app.infra.ratings_service import recalc

    with open_session(get_config().database_url) as db:
        return recalc(db)


def recalc_interval_s() -> float:
    """Интервал пересчёта из настроек (popularity.recalc_interval_s); без БД — час."""
    try:
        from app.infra.settings_repo import get_setting

        with open_session(get_config().database_url) as db:
            return float(get_setting(db, "popularity.recalc_interval_s"))
    except Exception:
        return DEFAULT_RECALC_S


@celery_app.on_after_finalize.connect
def setup_periodic_tasks(sender: Any, **_: Any) -> None:
    sender.add_periodic_task(
        recalc_interval_s(), recalc_popularity_task.s(), name="recalc-popularity"
    )
    sender.add_periodic_task(STUCK_CHECK_S, requeue_stuck_task.s(), name="requeue-stuck-tracks")
