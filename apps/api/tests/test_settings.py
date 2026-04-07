from __future__ import annotations

import pytest

from app.settings import get_settings


def test_settings_reject_sync_mode_in_non_dev_env(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("ENV", "prod")
    monkeypatch.setenv("BACKTEST_EXEC_MODE", "sync")
    monkeypatch.setenv("GUEST_COOKIE_SIGNING_SECRET", "prod-secret")
    monkeypatch.delenv("ALLOW_SYNC_EXECUTION", raising=False)

    settings = get_settings()
    with pytest.raises(RuntimeError):
        settings.validate()


def test_settings_allow_sync_override_in_non_dev_env(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("ENV", "prod")
    monkeypatch.setenv("BACKTEST_EXEC_MODE", "sync")
    monkeypatch.setenv("GUEST_COOKIE_SIGNING_SECRET", "prod-secret")
    monkeypatch.setenv("ALLOW_SYNC_EXECUTION", "true")

    settings = get_settings()
    settings.validate()


def test_settings_accept_async_mode_in_non_dev_env(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("ENV", "prod")
    monkeypatch.setenv("BACKTEST_EXEC_MODE", "async")
    monkeypatch.setenv("GUEST_COOKIE_SIGNING_SECRET", "prod-secret")
    monkeypatch.delenv("ALLOW_SYNC_EXECUTION", raising=False)

    settings = get_settings()
    settings.validate()


def test_settings_reject_trusted_user_header_in_prod(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("ENV", "prod")
    monkeypatch.setenv("TRUSTED_USER_HEADER_ENABLED", "true")
    monkeypatch.setenv("BACKTEST_EXEC_MODE", "async")
    monkeypatch.setenv("GUEST_COOKIE_SIGNING_SECRET", "prod-secret")

    settings = get_settings()
    with pytest.raises(RuntimeError, match="TRUSTED_USER_HEADER_ENABLED"):
        settings.validate()


def test_settings_reject_cors_wildcard_with_credentials(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("ENV", "dev")
    monkeypatch.setenv("CORS_ORIGINS", "*,http://localhost:3000")
    monkeypatch.setenv("CORS_ALLOW_CREDENTIALS", "true")

    settings = get_settings()
    with pytest.raises(RuntimeError, match="CORS_ORIGINS"):
        settings.validate()


def test_settings_require_non_default_guest_cookie_secret_in_prod(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("ENV", "prod")
    monkeypatch.setenv("BACKTEST_EXEC_MODE", "async")
    monkeypatch.delenv("GUEST_COOKIE_SIGNING_SECRET", raising=False)

    settings = get_settings()
    with pytest.raises(RuntimeError, match="GUEST_COOKIE_SIGNING_SECRET"):
        settings.validate()
