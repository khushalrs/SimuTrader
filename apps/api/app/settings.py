from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache


def _parse_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    env: str
    backtest_exec_mode: str
    allow_sync_execution: bool
    backtest_idempotency_window_seconds: int
    stale_run_timeout_seconds: int
    stale_queued_timeout_seconds: int
    max_active_runs_per_guest: int
    max_active_runs_per_user: int
    max_backtest_creates_per_window_guest: int
    max_backtest_creates_per_window_user: int
    backtest_create_window_seconds: int
    trusted_user_header_enabled: bool
    guest_cookie_secure: bool
    guest_cookie_samesite: str
    redis_cache_url: str
    redis_lock_url: str
    redis_cache_prefix: str
    redis_lock_prefix: str
    run_status_cache_ttl_seconds: int
    run_summary_cache_ttl_seconds: int
    top_holdings_cache_ttl_seconds: int
    redis_lock_timeout_seconds: int
    cors_origins: list[str]

    @property
    def is_dev_env(self) -> bool:
        return self.env in {"dev", "development", "test"}

    def validate(self) -> None:
        if self.backtest_exec_mode not in {"sync", "async"}:
            raise RuntimeError(
                "Invalid BACKTEST_EXEC_MODE. Supported values are 'sync' and 'async'."
            )
        if (
            not self.is_dev_env
            and self.backtest_exec_mode != "async"
            and not self.allow_sync_execution
        ):
            raise RuntimeError(
                "Invalid execution mode for non-dev environment: set BACKTEST_EXEC_MODE=async "
                "or explicitly set ALLOW_SYNC_EXECUTION=true."
            )
        if self.backtest_idempotency_window_seconds <= 0:
            raise RuntimeError("BACKTEST_IDEMPOTENCY_WINDOW_SECONDS must be > 0.")
        if self.stale_run_timeout_seconds <= 0:
            raise RuntimeError("STALE_RUN_TIMEOUT_SECONDS must be > 0.")
        if self.stale_queued_timeout_seconds <= 0:
            raise RuntimeError("STALE_QUEUED_TIMEOUT_SECONDS must be > 0.")
        if self.max_active_runs_per_guest <= 0:
            raise RuntimeError("MAX_ACTIVE_RUNS_PER_GUEST must be > 0.")
        if self.max_active_runs_per_user <= 0:
            raise RuntimeError("MAX_ACTIVE_RUNS_PER_USER must be > 0.")
        if self.max_backtest_creates_per_window_guest <= 0:
            raise RuntimeError("MAX_BACKTEST_CREATES_PER_WINDOW_GUEST must be > 0.")
        if self.max_backtest_creates_per_window_user <= 0:
            raise RuntimeError("MAX_BACKTEST_CREATES_PER_WINDOW_USER must be > 0.")
        if self.backtest_create_window_seconds <= 0:
            raise RuntimeError("BACKTEST_CREATE_WINDOW_SECONDS must be > 0.")
        if not self.redis_cache_url:
            raise RuntimeError("REDIS_CACHE_URL must be set.")
        if not self.redis_lock_url:
            raise RuntimeError("REDIS_LOCK_URL must be set.")
        if self.run_status_cache_ttl_seconds <= 0:
            raise RuntimeError("RUN_STATUS_CACHE_TTL_SECONDS must be > 0.")
        if self.run_summary_cache_ttl_seconds <= 0:
            raise RuntimeError("RUN_SUMMARY_CACHE_TTL_SECONDS must be > 0.")
        if self.top_holdings_cache_ttl_seconds <= 0:
            raise RuntimeError("TOP_HOLDINGS_CACHE_TTL_SECONDS must be > 0.")
        if self.redis_lock_timeout_seconds <= 0:
            raise RuntimeError("REDIS_LOCK_TIMEOUT_SECONDS must be > 0.")
        if self.guest_cookie_samesite not in {"lax", "strict", "none"}:
            raise RuntimeError(
                "GUEST_COOKIE_SAMESITE must be one of: lax, strict, none."
            )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    env = os.getenv("ENV", "dev").strip().lower()
    exec_mode = os.getenv("BACKTEST_EXEC_MODE", "async").strip().lower()
    allow_sync_execution = _parse_bool(os.getenv("ALLOW_SYNC_EXECUTION"), default=False)
    redis_url = os.getenv("REDIS_URL", "redis://redis:6379/0").strip()
    idempotency_window_seconds = int(
        os.getenv("BACKTEST_IDEMPOTENCY_WINDOW_SECONDS", "300").strip()
    )
    stale_run_timeout_seconds = int(os.getenv("STALE_RUN_TIMEOUT_SECONDS", "7200").strip())
    stale_queued_timeout_seconds = int(
        os.getenv("STALE_QUEUED_TIMEOUT_SECONDS", "900").strip()
    )
    max_active_runs_per_guest = int(os.getenv("MAX_ACTIVE_RUNS_PER_GUEST", "5").strip())
    max_active_runs_per_user = int(os.getenv("MAX_ACTIVE_RUNS_PER_USER", "20").strip())
    max_backtest_creates_per_window_guest = int(
        os.getenv("MAX_BACKTEST_CREATES_PER_WINDOW_GUEST", "10").strip()
    )
    max_backtest_creates_per_window_user = int(
        os.getenv("MAX_BACKTEST_CREATES_PER_WINDOW_USER", "30").strip()
    )
    backtest_create_window_seconds = int(
        os.getenv("BACKTEST_CREATE_WINDOW_SECONDS", "60").strip()
    )
    trusted_user_header_enabled = _parse_bool(
        os.getenv("TRUSTED_USER_HEADER_ENABLED"),
        default=env in {"dev", "development", "test"},
    )
    guest_cookie_secure = _parse_bool(
        os.getenv("GUEST_COOKIE_SECURE"),
        default=env not in {"dev", "development", "test"},
    )
    guest_cookie_samesite = os.getenv("GUEST_COOKIE_SAMESITE", "lax").strip().lower()
    origins_env = os.getenv(
        "CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
    )
    cors_origins = [origin.strip() for origin in origins_env.split(",") if origin.strip()]
    redis_cache_url = os.getenv("REDIS_CACHE_URL", redis_url).strip()
    redis_lock_url = os.getenv("REDIS_LOCK_URL", redis_url).strip()
    redis_cache_prefix = os.getenv("REDIS_CACHE_PREFIX", "simutrader:cache").strip()
    redis_lock_prefix = os.getenv("REDIS_LOCK_PREFIX", "simutrader:lock").strip()
    run_status_cache_ttl_seconds = int(
        os.getenv("RUN_STATUS_CACHE_TTL_SECONDS", "30").strip()
    )
    run_summary_cache_ttl_seconds = int(
        os.getenv("RUN_SUMMARY_CACHE_TTL_SECONDS", "120").strip()
    )
    top_holdings_cache_ttl_seconds = int(
        os.getenv("TOP_HOLDINGS_CACHE_TTL_SECONDS", "120").strip()
    )
    redis_lock_timeout_seconds = int(os.getenv("REDIS_LOCK_TIMEOUT_SECONDS", "3600").strip())
    return Settings(
        env=env,
        backtest_exec_mode=exec_mode,
        allow_sync_execution=allow_sync_execution,
        backtest_idempotency_window_seconds=idempotency_window_seconds,
        stale_run_timeout_seconds=stale_run_timeout_seconds,
        stale_queued_timeout_seconds=stale_queued_timeout_seconds,
        max_active_runs_per_guest=max_active_runs_per_guest,
        max_active_runs_per_user=max_active_runs_per_user,
        max_backtest_creates_per_window_guest=max_backtest_creates_per_window_guest,
        max_backtest_creates_per_window_user=max_backtest_creates_per_window_user,
        backtest_create_window_seconds=backtest_create_window_seconds,
        trusted_user_header_enabled=trusted_user_header_enabled,
        guest_cookie_secure=guest_cookie_secure,
        guest_cookie_samesite=guest_cookie_samesite,
        redis_cache_url=redis_cache_url,
        redis_lock_url=redis_lock_url,
        redis_cache_prefix=redis_cache_prefix,
        redis_lock_prefix=redis_lock_prefix,
        run_status_cache_ttl_seconds=run_status_cache_ttl_seconds,
        run_summary_cache_ttl_seconds=run_summary_cache_ttl_seconds,
        top_holdings_cache_ttl_seconds=top_holdings_cache_ttl_seconds,
        redis_lock_timeout_seconds=redis_lock_timeout_seconds,
        cors_origins=cors_origins,
    )
