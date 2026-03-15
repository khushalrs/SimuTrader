from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.data.duckdb import get_duckdb_conn
from app.db import get_db
from app.models.assets import Asset
from app.schemas.assets import AssetCoverageOut, AssetDetailOut, AssetOut

router = APIRouter(prefix="/assets", tags=["assets"])


def _coverage_for_symbol(symbol: str) -> AssetCoverageOut | None:
    con = get_duckdb_conn()
    try:
        row = con.execute(
            """
            SELECT
                symbol,
                min(date) AS first_date,
                max(date) AS last_date,
                count(*) AS rows
            FROM prices
            WHERE upper(symbol) = upper(?)
            GROUP BY symbol
            """,
            [symbol],
        ).fetchone()
    except Exception:
        return None
    finally:
        con.close()

    if row is None:
        return None
    return AssetCoverageOut(
        symbol=row[0],
        first_date=row[1].isoformat(),
        last_date=row[2].isoformat(),
        rows=int(row[3]),
    )


@router.get("", response_model=list[AssetOut])
def list_assets(
    q: str | None = Query(default=None),
    asset_class: str | None = Query(default=None),
    currency: str | None = Query(default=None),
    exchange: str | None = Query(default=None),
    is_active: bool | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> list[AssetOut]:
    normalized_q = (q or "").strip()
    normalized_asset_class = (asset_class or "").strip().lower()
    normalized_currency = (currency or "").strip().upper()
    normalized_exchange = (exchange or "").strip().upper()

    base_query = db.query(Asset)
    if normalized_asset_class:
        base_query = base_query.filter(func.lower(Asset.asset_class) == normalized_asset_class)
    if normalized_currency:
        base_query = base_query.filter(func.upper(Asset.currency) == normalized_currency)
    if normalized_exchange:
        base_query = base_query.filter(func.upper(Asset.exchange) == normalized_exchange)
    if is_active is not None:
        base_query = base_query.filter(Asset.is_active == is_active)

    def _apply_order_and_limit(query):  # noqa: ANN001
        query = query.order_by(Asset.symbol.asc())
        return query.limit(limit)

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


@router.get("/{symbol}", response_model=AssetDetailOut)
def get_asset(symbol: str, db: Session = Depends(get_db)) -> AssetDetailOut:
    asset = db.query(Asset).filter(func.lower(Asset.symbol) == symbol.strip().lower()).first()
    if not asset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found")
    coverage = _coverage_for_symbol(asset.symbol)
    return AssetDetailOut.model_validate(
        {
            **AssetOut.model_validate(asset).model_dump(),
            "coverage": coverage.model_dump() if coverage is not None else None,
        }
    )
