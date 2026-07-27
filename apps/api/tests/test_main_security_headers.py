from __future__ import annotations

import asyncio
from types import SimpleNamespace

from starlette.responses import Response

from app import main as main_module


def test_security_headers_are_set_on_response():
    async def call_next(_request):
        return Response()

    response = asyncio.run(main_module._security_headers(None, call_next))

    assert response.headers["Content-Security-Policy"] == (
        "default-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'"
    )
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert "Strict-Transport-Security" not in response.headers


def test_security_headers_include_hsts_outside_dev(monkeypatch):
    async def call_next(_request):
        return Response()

    monkeypatch.setattr(main_module, "settings", SimpleNamespace(is_dev_env=False))
    response = asyncio.run(main_module._security_headers(None, call_next))

    assert response.headers["Strict-Transport-Security"] == "max-age=31536000; includeSubDomains"
