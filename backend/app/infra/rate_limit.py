"""Счётчик запросов на IP в минуту (Redis, фиксированное окно)."""

import secrets
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

    def hit_sliding(self, scope: str, ident: str, limit: int, window_s: int) -> int | None:
        """Скользящее окно. None — запрос разрешён; иначе — через сколько секунд можно снова."""
        key = f"rl:{scope}:{ident}"
        now = time.time()
        pipe = self.client.pipeline()
        pipe.zremrangebyscore(key, 0, now - window_s)
        pipe.zrange(key, 0, 0, withscores=True)
        pipe.zcard(key)
        _, oldest, count = pipe.execute()
        if int(count) >= limit:
            return max(1, int(oldest[0][1] + window_s - now) + 1)
        member = f"{now:.6f}:{secrets.token_hex(4)}"
        self.client.zadd(key, {member: now})
        self.client.expire(key, window_s)
        return None
