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


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    env = os.getenv("ENV", "dev").strip().lower()
    exec_mode = os.getenv("BACKTEST_EXEC_MODE", "async").strip().lower()
    allow_sync_execution = _parse_bool(os.getenv("ALLOW_SYNC_EXECUTION"), default=False)
    origins_env = os.getenv(
        "CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
    )
    cors_origins = [origin.strip() for origin in origins_env.split(",") if origin.strip()]
    return Settings(
        env=env,
        backtest_exec_mode=exec_mode,
        allow_sync_execution=allow_sync_execution,
        cors_origins=cors_origins,
    )
