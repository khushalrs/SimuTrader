from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.strategies import Strategy
from app.schemas.strategies import StrategyCreate, StrategyOut

router = APIRouter(prefix="/strategies", tags=["strategies"])


@router.post("", response_model=StrategyOut, status_code=status.HTTP_201_CREATED)
def create_strategy(payload: StrategyCreate, db: Session = Depends(get_db)) -> StrategyOut:
    name = str(payload.name or "").strip()
    if not name:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="name is required")
    strategy = Strategy(
        name=name,
        description=payload.description,
        config=payload.config,
    )
    db.add(strategy)
    db.commit()
    db.refresh(strategy)
    return strategy


@router.get("", response_model=list[StrategyOut])
def list_strategies(
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
) -> list[StrategyOut]:
    if limit < 1 or limit > 200:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="limit must be 1..200")
    if offset < 0:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="offset must be >= 0")
    return (
        db.query(Strategy)
        .order_by(Strategy.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )


@router.get("/{strategy_id}", response_model=StrategyOut)
def get_strategy(strategy_id: UUID, db: Session = Depends(get_db)) -> StrategyOut:
    strategy = db.query(Strategy).filter(Strategy.strategy_id == strategy_id).first()
    if not strategy:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Strategy not found")
    return strategy
