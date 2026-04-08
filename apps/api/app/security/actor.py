from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass
from enum import Enum
from uuid import uuid4

from fastapi import Request, Response
from app.settings import get_settings


class ActorTier(str, Enum):
    GUEST = "guest"
    USER = "user"


@dataclass(frozen=True)
class ActorContext:
    tier: ActorTier
    actor_key: str


GUEST_COOKIE_NAME = "simutrader_guest_id"
TRUSTED_PROXY_SECRET_HEADER = "X-Trusted-Proxy-Secret"


def _clean_user_id(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = "".join(ch for ch in str(value) if ord(ch) >= 32 or ch in "\t\r\n").strip()
    if not cleaned:
        return None
    return cleaned[:128]


def _guest_signature(guest_id: str, secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), guest_id.encode("utf-8"), hashlib.sha256).hexdigest()


def _encode_guest_cookie_value(guest_id: str, secret: str) -> str:
    return f"{guest_id}.{_guest_signature(guest_id, secret)}"


def _decode_guest_cookie_value(cookie_value: str | None, secret: str) -> str | None:
    if not cookie_value or "." not in cookie_value:
        return None
    guest_id, signature = cookie_value.rsplit(".", 1)
    if not guest_id or not signature:
        return None
    expected = _guest_signature(guest_id, secret)
    if not hmac.compare_digest(signature, expected):
        return None
    return guest_id


def get_current_actor(request: Request, response: Response) -> ActorContext:
    settings = get_settings()
    # Auth-ready seam: once auth exists, map authenticated identity here.
    if settings.trusted_user_header_enabled:
        expected_proxy_secret = settings.trusted_user_header_proxy_secret
        if expected_proxy_secret:
            provided_proxy_secret = request.headers.get(TRUSTED_PROXY_SECRET_HEADER, "")
            if hmac.compare_digest(provided_proxy_secret, expected_proxy_secret):
                user_key = _clean_user_id(request.headers.get("X-User-Id"))
                if user_key:
                    return ActorContext(tier=ActorTier.USER, actor_key=f"user:{user_key}")
        else:
            user_key = _clean_user_id(request.headers.get("X-User-Id"))
            if user_key:
                return ActorContext(tier=ActorTier.USER, actor_key=f"user:{user_key}")

    guest_id = _decode_guest_cookie_value(
        request.cookies.get(GUEST_COOKIE_NAME), settings.guest_cookie_signing_secret
    )
    if not guest_id:
        guest_id = uuid4().hex
        response.set_cookie(
            key=GUEST_COOKIE_NAME,
            value=_encode_guest_cookie_value(guest_id, settings.guest_cookie_signing_secret),
            max_age=60 * 60 * 24 * 365,
            httponly=True,
            secure=settings.guest_cookie_secure,
            samesite=settings.guest_cookie_samesite,
            path="/",
        )
    return ActorContext(tier=ActorTier.GUEST, actor_key=f"guest:{guest_id}")
