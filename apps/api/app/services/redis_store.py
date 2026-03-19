from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from typing import Any

from redis import Redis
from redis.exceptions import RedisError

from app.models.backtests import BacktestRun
from app.settings import get_settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RunCacheSnapshot:
    run_id: str
    status: str
    started_at: str | None
    finished_at: str | None
    error_code: str | None
    error_message_public: str | None


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


@lru_cache(maxsize=1)
def get_cache_redis() -> Redis:
    settings = get_settings()
    return Redis.from_url(settings.redis_cache_url, decode_responses=True)


@lru_cache(maxsize=1)
def get_lock_redis() -> Redis:
    settings = get_settings()
    return Redis.from_url(settings.redis_lock_url, decode_responses=True)


def _status_key(actor_key: str, run_id: str) -> str:
    settings = get_settings()
    return f"{settings.redis_cache_prefix}:run_status:{actor_key}:{run_id}"


def _summary_key(actor_key: str, run_id: str) -> str:
    settings = get_settings()
    return f"{settings.redis_cache_prefix}:run_summary:{actor_key}:{run_id}"


def _top_holdings_key(actor_key: str, run_id: str, limit: int) -> str:
    settings = get_settings()
    return f"{settings.redis_cache_prefix}:top_holdings:{actor_key}:{run_id}:{limit}"


def _lock_key(run_id: str) -> str:
    settings = get_settings()
    return f"{settings.redis_lock_prefix}:run_exec:{run_id}"


def _safe_get_json(key: str) -> dict[str, Any] | list[dict[str, Any]] | None:
    try:
        value = get_cache_redis().get(key)
        if not value:
            return None
        parsed = json.loads(value)
        if isinstance(parsed, (dict, list)):
            return parsed
    except (RedisError, ValueError, TypeError):
        logger.debug("Redis cache get failed for key=%s", key, exc_info=True)
    return None


def _safe_set_json(key: str, value: Any, ttl_seconds: int) -> None:
    try:
        get_cache_redis().setex(key, ttl_seconds, json.dumps(value))
    except (RedisError, TypeError, ValueError):
        logger.debug("Redis cache set failed for key=%s", key, exc_info=True)


def _safe_delete(prefix_key: str) -> None:
    try:
        get_cache_redis().delete(prefix_key)
    except RedisError:
        logger.debug("Redis cache delete failed for key=%s", prefix_key, exc_info=True)


def get_cached_run_status(actor_key: str, run_id: str) -> RunCacheSnapshot | None:
    value = _safe_get_json(_status_key(actor_key, run_id))
    if not isinstance(value, dict):
        return None
    try:
        return RunCacheSnapshot(
            run_id=str(value["run_id"]),
            status=str(value["status"]),
            started_at=value.get("started_at"),
            finished_at=value.get("finished_at"),
            error_code=value.get("error_code"),
            error_message_public=value.get("error_message_public"),
        )
    except KeyError:
        return None


def set_cached_run_status(run: BacktestRun) -> None:
    if not run.actor_key:
        return
    settings = get_settings()
    _safe_set_json(
        _status_key(run.actor_key, str(run.run_id)),
        {
            "run_id": str(run.run_id),
            "status": run.status,
            "started_at": _iso(run.started_at),
            "finished_at": _iso(run.finished_at),
            "error_code": run.error_code,
            "error_message_public": run.error_message_public,
        },
        settings.run_status_cache_ttl_seconds,
    )


def set_cached_run_summary(run: BacktestRun) -> None:
    if not run.actor_key:
        return
    settings = get_settings()
    _safe_set_json(
        _summary_key(run.actor_key, str(run.run_id)),
        {
            "run_id": str(run.run_id),
            "name": run.name,
            "status": run.status,
            "created_at": _iso(run.created_at),
            "started_at": _iso(run.started_at),
            "finished_at": _iso(run.finished_at),
            "error_code": run.error_code,
            "error_message_public": run.error_message_public,
        },
        settings.run_summary_cache_ttl_seconds,
    )


def get_cached_top_holdings(
    actor_key: str, run_id: str, limit: int
) -> list[dict[str, Any]] | None:
    value = _safe_get_json(_top_holdings_key(actor_key, run_id, limit))
    if isinstance(value, list):
        return [row for row in value if isinstance(row, dict)]
    return None


def set_cached_top_holdings(
    actor_key: str, run_id: str, limit: int, holdings: list[dict[str, Any]]
) -> None:
    settings = get_settings()
    _safe_set_json(
        _top_holdings_key(actor_key, run_id, limit),
        holdings,
        settings.top_holdings_cache_ttl_seconds,
    )


def invalidate_run_cache(actor_key: str | None, run_id: str, limits: list[int] | None = None) -> None:
    if not actor_key:
        return
    _safe_delete(_status_key(actor_key, run_id))
    _safe_delete(_summary_key(actor_key, run_id))
    for item_limit in limits or [10, 20, 50]:
        _safe_delete(_top_holdings_key(actor_key, run_id, item_limit))


def refresh_run_cache(run: BacktestRun) -> None:
    set_cached_run_status(run)
    set_cached_run_summary(run)
    # Top-holdings projections are derived and can become stale when status changes.
    if run.actor_key:
        for item_limit in [10, 20, 50]:
            _safe_delete(_top_holdings_key(run.actor_key, str(run.run_id), item_limit))


def try_acquire_run_lock(run_id: str, timeout_seconds: int) -> str | None:
    token = f"lock-{run_id}-{datetime.utcnow().timestamp()}"
    try:
        acquired = get_lock_redis().set(
            _lock_key(run_id),
            token,
            nx=True,
            ex=timeout_seconds,
        )
        if acquired:
            return token
    except RedisError:
        logger.debug("Redis lock acquire failed for run_id=%s", run_id, exc_info=True)
    return None


def release_run_lock(run_id: str, token: str | None) -> None:
    if not token:
        return
    try:
        key = _lock_key(run_id)
        value = get_lock_redis().get(key)
        if value == token:
            get_lock_redis().delete(key)
    except RedisError:
        logger.debug("Redis lock release failed for run_id=%s", run_id, exc_info=True)
