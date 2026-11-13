"""Проверки зависимостей для GET /health."""

import logging
from collections.abc import Callable

import redis
from sqlalchemy import text

from app.config import Config
from app.infra.db import get_engine
from app.infra.s3 import s3_client

log = logging.getLogger(__name__)


def check_db(cfg: Config) -> None:
    with get_engine(cfg.database_url, cfg.health_timeout_s).connect() as conn:
        conn.execute(text("SELECT 1"))


def check_redis(cfg: Config) -> None:
    client = redis.Redis.from_url(
        cfg.redis_url,
        socket_connect_timeout=cfg.health_timeout_s,
        socket_timeout=cfg.health_timeout_s,
    )
    try:
        client.ping()
    finally:
        client.close()


def check_s3(cfg: Config) -> None:
    s3_client(cfg).head_bucket(Bucket=cfg.s3_bucket)


CHECKS: dict[str, Callable[[Config], None]] = {
    "db": check_db,
    "redis": check_redis,
    "s3": check_s3,
}


def run_checks(cfg: Config) -> dict[str, str]:
    results: dict[str, str] = {}
    for name, check in CHECKS.items():
        try:
            check(cfg)
            results[name] = "ok"
        except Exception:
            log.warning("health check %s failed", name, exc_info=True)
            results[name] = "error"
    return results
