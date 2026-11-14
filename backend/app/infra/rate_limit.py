"""Ограничение частоты запросов в Redis."""

import secrets
import time
from functools import lru_cache

import redis

from app.config import Config

# Проверка и запись — одной операцией: параллельные запросы не проскочат лимит вдвоём.
_SLIDING = """
local key, now, window, limit, member = KEYS[1], tonumber(ARGV[1]), tonumber(ARGV[2]),
    tonumber(ARGV[3]), ARGV[4]
redis.call('ZREMRANGEBYSCORE', key, 0, now - window)
if redis.call('ZCARD', key) >= limit then
    local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
    return tostring(tonumber(oldest[2]) + window - now)
end
redis.call('ZADD', key, now, member)
redis.call('EXPIRE', key, window)
return false
"""


@lru_cache(maxsize=4)
def _client(url: str) -> redis.Redis:
    """Один пул соединений на процесс, а не новый на каждый запрос."""
    return redis.Redis.from_url(url)


class RateLimiter:
    def __init__(self, cfg: Config) -> None:
        self.client = _client(cfg.redis_url)

    def hit(self, scope: str, ident: str, limit: int) -> bool:
        """Фиксированное окно в минуту. True — запрос укладывается в лимит."""
        window = int(time.time() // 60)
        key = f"rl:{scope}:{ident}:{window}"
        pipe = self.client.pipeline()
        pipe.incr(key)
        pipe.expire(key, 61)
        count, _ = pipe.execute()
        return int(count) <= limit

    def hit_sliding(self, scope: str, ident: str, limit: int, window_s: int) -> int | None:
        """Скользящее окно. None — запрос разрешён; иначе — через сколько секунд можно снова."""
        now = time.time()
        member = f"{now:.6f}:{secrets.token_hex(4)}"
        wait = self.client.eval(_SLIDING, 1, f"rl:{scope}:{ident}", now, window_s, limit, member)
        if wait is None:
            return None
        return max(1, int(float(wait)) + 1)
