"""Requirement: Background Worker — сценарий Ping task."""

from collections.abc import Iterator

import pytest
from celery.contrib.testing.worker import start_worker

from app.config import Config
from app.infra.celery_app import celery_app
from app.infra.tasks import ping


@pytest.fixture
def worker(config: Config) -> Iterator[None]:
    celery_app.conf.update(broker_url=config.redis_url, result_backend=config.redis_url)
    with start_worker(celery_app, pool="solo", perform_ping_check=False):
        yield


def test_ping_task_returns_pong(worker: None) -> None:
    result = ping.delay()
    assert result.get(timeout=20) == "pong"
