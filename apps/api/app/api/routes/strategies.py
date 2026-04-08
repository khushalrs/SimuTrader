from __future__ import annotations

import json
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.strategies import Strategy
from app.security import ActorContext, get_current_actor
from app.schemas.strategies import StrategyCreate, StrategyOut
from app.services.config_validation import validate_and_resolve_config

router = APIRouter(prefix="/strategies", tags=["strategies"])

MAX_CONFIG_BYTES = 250_000


def _sanitize_user_string(value: str | None, *, max_len: int) -> str | None:
    if value is None:
        return None
    cleaned = "".join(ch for ch in str(value) if ord(ch) >= 32 or ch in "\t\r\n").strip()
    if not cleaned:
        return None
    return cleaned[:max_len]


@router.post("", response_model=StrategyOut, status_code=status.HTTP_201_CREATED)
def create_strategy(
    payload: StrategyCreate,
    actor: ActorContext = Depends(get_current_actor),
    db: Session = Depends(get_db),
) -> StrategyOut:
    name = _sanitize_user_string(payload.name, max_len=255)
    if not name:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="name is required")
    description = _sanitize_user_string(payload.description, max_len=2000)
    try:
        resolved_config = validate_and_resolve_config(payload.config)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    config_bytes = len(json.dumps(resolved_config, separators=(",", ":")).encode("utf-8"))
    if config_bytes > MAX_CONFIG_BYTES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"config is too large ({config_bytes} bytes > {MAX_CONFIG_BYTES} bytes)",
        )
    strategy = Strategy(
        name=name,
        description=description,
        actor_tier=actor.tier.value,
        actor_key=actor.actor_key,
        config=resolved_config,
    )
    db.add(strategy)
    db.commit()
    db.refresh(strategy)
    return strategy


@router.get("", response_model=list[StrategyOut])
def list_strategies(
    limit: int = 50,
    offset: int = 0,
    actor: ActorContext = Depends(get_current_actor),
    db: Session = Depends(get_db),
) -> list[StrategyOut]:
    if limit < 1 or limit > 200:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="limit must be 1..200")
    if offset < 0:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="offset must be >= 0")
    return (
        db.query(Strategy)
        .filter(Strategy.actor_key == actor.actor_key)
        .order_by(Strategy.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )


@router.get("/{strategy_id}", response_model=StrategyOut)
def get_strategy(
    strategy_id: UUID,
    actor: ActorContext = Depends(get_current_actor),
    db: Session = Depends(get_db),
) -> StrategyOut:
    strategy = (
        db.query(Strategy)
        .filter(Strategy.strategy_id == strategy_id, Strategy.actor_key == actor.actor_key)
        .first()
    )
    if not strategy:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Strategy not found")
    return strategy
