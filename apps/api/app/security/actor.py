from __future__ import annotations

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


def get_current_actor(request: Request, response: Response) -> ActorContext:
    settings = get_settings()
    # Auth-ready seam: once auth exists, map authenticated identity here.
    if settings.trusted_user_header_enabled:
        user_id = request.headers.get("X-User-Id")
        if user_id:
            user_key = user_id.strip()
            if user_key:
                return ActorContext(tier=ActorTier.USER, actor_key=f"user:{user_key}")

    guest_id = request.cookies.get(GUEST_COOKIE_NAME)
    if not guest_id:
        guest_id = uuid4().hex
        response.set_cookie(
            key=GUEST_COOKIE_NAME,
            value=guest_id,
            max_age=60 * 60 * 24 * 365,
            httponly=True,
            secure=settings.guest_cookie_secure,
            samesite=settings.guest_cookie_samesite,
            path="/",
        )
    return ActorContext(tier=ActorTier.GUEST, actor_key=f"guest:{guest_id}")
