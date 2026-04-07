from __future__ import annotations

from fastapi import Response
from starlette.requests import Request

from app.security.actor import ActorTier, get_current_actor
from app.settings import get_settings


def _request_with_headers(headers: list[tuple[bytes, bytes]] | None = None) -> Request:
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": headers or [],
            "query_string": b"",
            "client": ("127.0.0.1", 12345),
            "server": ("testserver", 80),
            "scheme": "http",
        }
    )


def test_user_header_ignored_in_prod_by_default(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("ENV", "prod")
    monkeypatch.delenv("TRUSTED_USER_HEADER_ENABLED", raising=False)

    req = _request_with_headers([(b"x-user-id", b"abc123")])
    res = Response()
    actor = get_current_actor(req, res)
    assert actor.tier == ActorTier.GUEST
    assert actor.actor_key.startswith("guest:")
    cookie = res.headers.get("set-cookie", "").lower()
    assert "secure" in cookie
    get_settings.cache_clear()


def test_user_header_not_allowed_in_prod_even_if_enabled(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("ENV", "prod")
    monkeypatch.setenv("TRUSTED_USER_HEADER_ENABLED", "true")

    req = _request_with_headers([(b"x-user-id", b"user-42")])
    res = Response()
    actor = get_current_actor(req, res)
    assert actor.tier == ActorTier.GUEST
    assert actor.actor_key.startswith("guest:")
    get_settings.cache_clear()


def test_user_header_requires_proxy_secret_when_configured(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("ENV", "dev")
    monkeypatch.setenv("TRUSTED_USER_HEADER_ENABLED", "true")
    monkeypatch.setenv("TRUSTED_USER_HEADER_PROXY_SECRET", "proxy-secret")

    bad_req = _request_with_headers([(b"x-user-id", b"user-42")])
    bad_actor = get_current_actor(bad_req, Response())
    assert bad_actor.tier == ActorTier.GUEST

    good_req = _request_with_headers(
        [(b"x-user-id", b"user-42"), (b"x-trusted-proxy-secret", b"proxy-secret")]
    )
    good_actor = get_current_actor(good_req, Response())
    assert good_actor.tier == ActorTier.USER
    assert good_actor.actor_key == "user:user-42"
    get_settings.cache_clear()
