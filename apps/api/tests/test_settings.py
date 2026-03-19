from __future__ import annotations

import pytest

from app.settings import get_settings


def test_settings_reject_sync_mode_in_non_dev_env(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("ENV", "prod")
    monkeypatch.setenv("BACKTEST_EXEC_MODE", "sync")
    monkeypatch.delenv("ALLOW_SYNC_EXECUTION", raising=False)

    settings = get_settings()
    with pytest.raises(RuntimeError):
        settings.validate()


def test_settings_allow_sync_override_in_non_dev_env(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("ENV", "prod")
    monkeypatch.setenv("BACKTEST_EXEC_MODE", "sync")
    monkeypatch.setenv("ALLOW_SYNC_EXECUTION", "true")

    settings = get_settings()
    settings.validate()


def test_settings_accept_async_mode_in_non_dev_env(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("ENV", "prod")
    monkeypatch.setenv("BACKTEST_EXEC_MODE", "async")
    monkeypatch.delenv("ALLOW_SYNC_EXECUTION", raising=False)

    settings = get_settings()
    settings.validate()
