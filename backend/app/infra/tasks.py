import uuid

from app.config import get_config
from app.infra.celery_app import celery_app
from app.infra.track_processing import process_track, recompute_visibility


@celery_app.task(name="ping")
def ping() -> str:
    return "pong"


@celery_app.task(name="process_track")
def process_track_task(track_id: str) -> None:
    process_track(get_config(), uuid.UUID(track_id))


@celery_app.task(name="recompute_visibility")
def recompute_visibility_task(user_id: str) -> None:
    recompute_visibility(get_config(), uuid.UUID(user_id))
