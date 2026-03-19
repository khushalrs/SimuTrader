from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from fastapi import Request


class ActorTier(str, Enum):
    GUEST = "guest"
    USER = "user"


@dataclass(frozen=True)
class ActorContext:
    tier: ActorTier
    actor_key: str


def get_actor_context(request: Request) -> ActorContext:
    # Auth is not wired yet: default every request to guest.
    client_host = request.client.host if request.client else "unknown"
    return ActorContext(tier=ActorTier.GUEST, actor_key=f"guest:{client_host}")
