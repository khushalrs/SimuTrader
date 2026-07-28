from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.capabilities import router as capabilities_router
from app.services.config_paths import (
    canonicalize_config_path,
    get_config_paths,
    validate_sweep_path,
)


def test_sweep_registry_is_canonical_sorted_and_strategy_scoped() -> None:
    entries = get_config_paths(strategy="MOMENTUM", sweepable=True)
    paths = [entry["path"] for entry in entries]

    assert paths == sorted(paths)
    assert len(paths) == len(set(paths))
    assert all(entry["sweepable"] for entry in entries)
    assert {
        "commission.bps",
        "slippage.bps",
        "commission.min_fee_native",
        "execution.cash_buffer_pct",
        "financing.margin.max_leverage",
        "financing.margin.daily_interest_bps",
        "financing.shorting.borrow_fee_daily_bps",
        "strategy_params.lookback_days",
    }.issubset(paths)
    assert "execution.commission.bps" not in paths
    assert "universe.top_n" not in paths
    assert "backtest.start_date" not in paths
    assert {
        entry["strategy"]
        for entry in entries
        if entry["strategy"] is not None
    } == {"MOMENTUM"}


def test_aliases_and_strategy_wildcards_validate_to_patchable_paths() -> None:
    assert canonicalize_config_path("execution.commission.bps") == "commission.bps"
    assert (
        validate_sweep_path(
            "execution.commission.bps",
            strategy="MOMENTUM",
        )
        == "commission.bps"
    )
    assert (
        validate_sweep_path(
            "strategy_params.target_weights.AAPL",
            strategy="FIXED_WEIGHT_REBALANCE",
        )
        == "strategy_params.target_weights.AAPL"
    )


def test_registry_rejects_paths_from_an_unselected_strategy() -> None:
    with pytest.raises(
        ValueError,
        match="not a valid sweep dimension for strategy BUY_AND_HOLD",
    ):
        validate_sweep_path(
            "strategy_params.lookback_days",
            strategy="BUY_AND_HOLD",
        )


def test_config_paths_endpoint_filters_and_describes_capabilities() -> None:
    app = FastAPI()
    app.include_router(capabilities_router)
    client = TestClient(app)

    response = client.get(
        "/capabilities/config-paths",
        params={"strategy": "MOMENTUM", "sweepable": "true"},
    )

    assert response.status_code == 200
    paths = {entry["path"]: entry for entry in response.json()}
    assert paths["commission.bps"]["aliases"] == ["execution.commission.bps"]
    assert paths["commission.bps"]["range_supported"] is True
    assert paths["commission.bps"]["unit"] == "basis_points"
    assert paths["strategy_params.rebalance_frequency"]["enum"] == [
        "DAILY",
        "WEEKLY",
        "MONTHLY",
        "QUARTERLY",
    ]


def test_config_paths_endpoint_rejects_unknown_strategy() -> None:
    app = FastAPI()
    app.include_router(capabilities_router)
    client = TestClient(app)

    response = client.get(
        "/capabilities/config-paths",
        params={"strategy": "NOT_A_STRATEGY"},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "Unknown strategy 'NOT_A_STRATEGY'."
