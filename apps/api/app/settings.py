from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache


def _parse_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _parse_csv(value: str | None, default: str) -> list[str]:
    raw = value if value is not None else default
    return [part.strip() for part in raw.split(",") if part.strip()]


DEFAULT_DEV_GUEST_COOKIE_SECRET = "dev-only-guest-cookie-secret"


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
    trusted_user_header_requested: bool
    trusted_user_header_enabled: bool
    trusted_user_header_proxy_secret: str
    guest_cookie_secure: bool
    guest_cookie_samesite: str
    guest_cookie_signing_secret: str
    redis_cache_url: str
    redis_lock_url: str
    redis_cache_prefix: str
    redis_lock_prefix: str
    run_status_cache_ttl_seconds: int
    run_summary_cache_ttl_seconds: int
    top_holdings_cache_ttl_seconds: int
    redis_lock_timeout_seconds: int
    cors_origins: list[str]
    cors_allow_credentials: bool
    cors_allow_methods: list[str]
    cors_allow_headers: list[str]
    trusted_hosts: list[str]

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
        if not self.is_dev_env and self.trusted_user_header_requested:
            raise RuntimeError(
                "TRUSTED_USER_HEADER_ENABLED must be false outside dev/test environments."
            )
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
        if not self.guest_cookie_signing_secret:
            raise RuntimeError("GUEST_COOKIE_SIGNING_SECRET must be set.")
        if (not self.is_dev_env) and self.guest_cookie_signing_secret == DEFAULT_DEV_GUEST_COOKIE_SECRET:
            raise RuntimeError(
                "GUEST_COOKIE_SIGNING_SECRET must be explicitly set in non-dev environments."
            )
        if self.cors_allow_credentials and "*" in self.cors_origins:
            raise RuntimeError("CORS_ORIGINS cannot contain '*' when credentials are enabled.")
        if "*" in self.cors_allow_methods:
            raise RuntimeError("CORS_ALLOW_METHODS must be explicit; wildcard is not allowed.")
        if "*" in self.cors_allow_headers:
            raise RuntimeError("CORS_ALLOW_HEADERS must be explicit; wildcard is not allowed.")
        if not self.trusted_hosts:
            raise RuntimeError("TRUSTED_HOSTS must include at least one host.")


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
    trusted_user_header_requested = _parse_bool(
        os.getenv("TRUSTED_USER_HEADER_ENABLED"),
        default=env in {"dev", "development", "test"},
    )
    trusted_user_header_enabled = (
        trusted_user_header_requested if env in {"dev", "development", "test"} else False
    )
    trusted_user_header_proxy_secret = os.getenv("TRUSTED_USER_HEADER_PROXY_SECRET", "").strip()
    guest_cookie_secure = _parse_bool(
        os.getenv("GUEST_COOKIE_SECURE"),
        default=env not in {"dev", "development", "test"},
    )
    guest_cookie_samesite = os.getenv("GUEST_COOKIE_SAMESITE", "lax").strip().lower()
    guest_cookie_signing_secret = os.getenv(
        "GUEST_COOKIE_SIGNING_SECRET", DEFAULT_DEV_GUEST_COOKIE_SECRET
    ).strip()
    origins_env = os.getenv(
        "CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
    )
    cors_origins = [origin.strip() for origin in origins_env.split(",") if origin.strip()]
    cors_allow_credentials = _parse_bool(os.getenv("CORS_ALLOW_CREDENTIALS"), default=True)
    cors_allow_methods = _parse_csv(
        os.getenv("CORS_ALLOW_METHODS"), default="GET,POST,OPTIONS"
    )
    cors_allow_headers = _parse_csv(
        os.getenv("CORS_ALLOW_HEADERS"), default="Content-Type,Idempotency-Key"
    )
    trusted_hosts = _parse_csv(
        os.getenv("TRUSTED_HOSTS"), default="localhost,127.0.0.1,::1"
    )
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
        trusted_user_header_requested=trusted_user_header_requested,
        trusted_user_header_enabled=trusted_user_header_enabled,
        trusted_user_header_proxy_secret=trusted_user_header_proxy_secret,
        guest_cookie_secure=guest_cookie_secure,
        guest_cookie_samesite=guest_cookie_samesite,
        guest_cookie_signing_secret=guest_cookie_signing_secret,
        redis_cache_url=redis_cache_url,
        redis_lock_url=redis_lock_url,
        redis_cache_prefix=redis_cache_prefix,
        redis_lock_prefix=redis_lock_prefix,
        run_status_cache_ttl_seconds=run_status_cache_ttl_seconds,
        run_summary_cache_ttl_seconds=run_summary_cache_ttl_seconds,
        top_holdings_cache_ttl_seconds=top_holdings_cache_ttl_seconds,
        redis_lock_timeout_seconds=redis_lock_timeout_seconds,
        cors_origins=cors_origins,
        cors_allow_credentials=cors_allow_credentials,
        cors_allow_methods=cors_allow_methods,
        cors_allow_headers=cors_allow_headers,
        trusted_hosts=trusted_hosts,
    )
