from __future__ import annotations

import asyncio

from starlette.responses import Response

from app.main import _security_headers


def test_security_headers_are_set_on_response():
    async def call_next(_request):
        return Response()

    response = asyncio.run(_security_headers(None, call_next))

    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
