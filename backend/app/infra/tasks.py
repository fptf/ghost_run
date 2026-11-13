import uuid
from typing import Any

from app.config import get_config
from app.infra.celery_app import celery_app
from app.infra.track_processing import process_track, recompute_visibility

DEFAULT_RECALC_S = 3600


@celery_app.task(name="ping")
def ping() -> str:
    return "pong"


@celery_app.task(name="process_track")
def process_track_task(track_id: str) -> None:
    process_track(get_config(), uuid.UUID(track_id))


@celery_app.task(name="recompute_visibility")
def recompute_visibility_task(user_id: str) -> None:
    recompute_visibility(get_config(), uuid.UUID(user_id))


@celery_app.task(name="recalc_popularity")
def recalc_popularity_task() -> int:
    from sqlalchemy.orm import sessionmaker

    from app.infra.db import get_engine
    from app.infra.ratings_service import recalc

    with sessionmaker(bind=get_engine(get_config().database_url))() as db:
        return recalc(db)


def recalc_interval_s() -> float:
    """Интервал пересчёта из настроек (popularity.recalc_interval_s); без БД — час."""
    try:
        from sqlalchemy.orm import sessionmaker

        from app.infra.db import get_engine
        from app.infra.settings_repo import get_setting

        with sessionmaker(bind=get_engine(get_config().database_url))() as db:
            return float(get_setting(db, "popularity.recalc_interval_s"))
    except Exception:
        return DEFAULT_RECALC_S


@celery_app.on_after_finalize.connect
def setup_periodic_tasks(sender: Any, **_: Any) -> None:
    sender.add_periodic_task(
        recalc_interval_s(), recalc_popularity_task.s(), name="recalc-popularity"
    )
