"""Счётчик запросов на IP в минуту (Redis, фиксированное окно)."""

import time

import redis

from app.config import Config


class RateLimiter:
    def __init__(self, cfg: Config) -> None:
        self.client = redis.Redis.from_url(cfg.redis_url)

    def hit(self, scope: str, ident: str, limit: int) -> bool:
        """Возвращает True, если запрос укладывается в лимит."""
        window = int(time.time() // 60)
        key = f"rl:{scope}:{ident}:{window}"
        pipe = self.client.pipeline()
        pipe.incr(key)
        pipe.expire(key, 61)
        count, _ = pipe.execute()
        return int(count) <= limit
