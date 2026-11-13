"""Requirement: Local Environment — сценарии Cold start и Dependency down."""

import pytest
from fastapi.testclient import TestClient

from app.config import Config, get_config
from app.main import app


def test_cold_start_health_ok(client: TestClient) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "checks": {"db": "ok", "redis": "ok", "s3": "ok"}}


BROKEN = {
    "db": {"database_url": "postgresql+psycopg://x:x@127.0.0.1:1/x"},
    "redis": {"redis_url": "redis://127.0.0.1:1/0"},
    "s3": {"s3_endpoint_url": "http://127.0.0.1:1"},
}


@pytest.mark.parametrize("broken", list(BROKEN))
def test_dependency_down_returns_503(migrated: Config, broken: str) -> None:
    cfg = migrated.model_copy(update={**BROKEN[broken], "health_timeout_s": 1})
    app.dependency_overrides[get_config] = lambda: cfg
    try:
        with TestClient(app) as c:
            resp = c.get("/health")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 503
    body = resp.json()
    assert body["status"] == "error"
    expected = {name: ("error" if name == broken else "ok") for name in BROKEN}
    assert body["checks"] == expected


def test_missing_bucket_is_error(migrated: Config) -> None:
    cfg = migrated.model_copy(update={"s3_bucket": "no-such-bucket"})
    app.dependency_overrides[get_config] = lambda: cfg
    try:
        with TestClient(app) as c:
            resp = c.get("/health")
    finally:
        app.dependency_overrides.clear()
    assert resp.status_code == 503
    assert resp.json()["checks"]["s3"] == "error"
