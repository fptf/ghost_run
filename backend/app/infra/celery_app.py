from celery import Celery

from app.config import get_config


def create_celery() -> Celery:
    cfg = get_config()
    app = Celery(
        "runners",
        broker=cfg.redis_url,
        backend=cfg.redis_url,
        include=["app.infra.tasks"],
    )
    app.conf.update(task_serializer="json", result_serializer="json", accept_content=["json"])
    return app


celery_app = create_celery()
