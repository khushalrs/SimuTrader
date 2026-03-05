from __future__ import annotations

import re

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.assets import Asset
from app.schemas.assets import AssetOut

router = APIRouter(prefix="/assets", tags=["assets"])


@router.get("", response_model=list[AssetOut])
def list_assets(
    request: Request,
    q: str | None = Query(default=None),
    asset_class: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> list[AssetOut]:
    normalized_q = (q or "").strip()
    normalized_asset_class = (asset_class or "").strip().lower()
    has_explicit_limit = "limit" in request.query_params

    # Preserve the legacy no-params behavior, otherwise bound latency with limit.
    effective_limit = limit if (normalized_q or normalized_asset_class or has_explicit_limit) else None

    base_query = db.query(Asset)
    if normalized_asset_class:
        base_query = base_query.filter(func.lower(Asset.asset_class) == normalized_asset_class)

    def _apply_order_and_limit(query):  # noqa: ANN001
        query = query.order_by(Asset.symbol.asc())
        if effective_limit is not None:
            query = query.limit(effective_limit)
        return query

    if normalized_q:
        contains_pattern = f"%{normalized_q}%"
        primary_matches = _apply_order_and_limit(
            base_query.filter(
                or_(
                    Asset.symbol.ilike(contains_pattern),
                    Asset.name.ilike(contains_pattern),
                )
            )
        ).all()
        if primary_matches:
            return primary_matches

        # Simple fuzzy-ish fallback: prefix-match tokens when contains-search returns no rows.
        tokens = [token for token in re.split(r"\s+", normalized_q) if token]
        if tokens:
            prefix_conditions = []
            for token in tokens[:5]:
                token_pattern = f"{token}%"
                prefix_conditions.extend(
                    [
                        Asset.symbol.ilike(token_pattern),
                        Asset.name.ilike(token_pattern),
                    ]
                )
            fallback_matches = _apply_order_and_limit(base_query.filter(or_(*prefix_conditions))).all()
            if fallback_matches:
                return fallback_matches
        return []

    return _apply_order_and_limit(base_query).all()
