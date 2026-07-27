from __future__ import annotations

from collections import OrderedDict
import logging
from math import ceil
import time

from fastapi import HTTPException, status

try:
    import redis
except ImportError:  # pragma: no cover - dependency exists in deployed app
    redis = None


logger = logging.getLogger(__name__)

MAX_RATE_LIMIT_KEYS = 1_000
_memory_rate_limits: OrderedDict[str, tuple[float, int]] = OrderedDict()
_redis_clients: dict[str, "redis.Redis"] = {}


def _retry_after_headers(retry_after_seconds: int) -> dict[str, str]:
    return {"Retry-After": str(max(1, retry_after_seconds))}


def rate_limit_exceeded(detail: str, retry_after_seconds: int) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail=detail,
        headers=_retry_after_headers(retry_after_seconds),
    )


def _redis_client(redis_url: str) -> "redis.Redis | None":
    if redis is None or not redis_url:
        return None
    if redis_url in _redis_clients:
        return _redis_clients[redis_url]
    try:
        client = redis.Redis.from_url(redis_url, decode_responses=True)
        client.ping()
    except Exception:
        logger.exception("Rate limit Redis connection failed")
        return None
    _redis_clients[redis_url] = client
    return client


def enforce_fixed_window_rate_limit(
    *,
    key: str,
    limit: int,
    window_seconds: int,
    redis_url: str,
    redis_prefix: str,
    detail: str,
) -> None:
    if limit <= 0:
        raise ValueError("rate limit must be > 0")
    if window_seconds <= 0:
        raise ValueError("rate limit window_seconds must be > 0")

    full_key = f"{redis_prefix}:rate:{key}"
    client = _redis_client(redis_url)
    if client is not None:
        try:
            count = int(client.incr(full_key))
            if count == 1:
                client.expire(full_key, window_seconds)
            if count > limit:
                ttl = client.ttl(full_key)
                retry_after = ttl if ttl > 0 else window_seconds
                raise rate_limit_exceeded(detail, retry_after)
            return
        except HTTPException:
            raise
        except Exception:
            logger.exception("Rate limit Redis check failed")

    now = time.monotonic()
    expires_at, count = _memory_rate_limits.get(full_key, (0.0, 0))
    if now >= expires_at:
        expires_at = now + window_seconds
        count = 0
    count += 1
    _memory_rate_limits[full_key] = (expires_at, count)
    _memory_rate_limits.move_to_end(full_key)
    while len(_memory_rate_limits) > MAX_RATE_LIMIT_KEYS:
        _memory_rate_limits.popitem(last=False)
    if count > limit:
        retry_after = ceil(max(1.0, expires_at - now))
        raise rate_limit_exceeded(detail, retry_after)


def clear_memory_rate_limits() -> None:
    _memory_rate_limits.clear()
