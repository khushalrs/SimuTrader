from __future__ import annotations

import pytest

from app.services.config_validation import validate_and_resolve_config


def _base_config() -> dict:
    return {
        "version": 1,
        "universe": {
            "instruments": [
                {"symbol": "AAPL", "asset_class": "US_EQUITY"},
                {"symbol": "MSFT", "asset_class": "US_EQUITY"},
            ]
        },
        "backtest": {
            "start_date": "2024-01-02",
            "end_date": "2024-01-31",
            "initial_cash": 10000,
        },
        "data_policy": {"missing_bar": "FORWARD_FILL"},
    }


def test_mean_reversion_legacy_z_score_threshold_is_mapped() -> None:
    config = {
        **_base_config(),
        "strategy": "MEAN_REVERSION",
        "strategy_params": {
            "lookback_days": 5,
            "z_score_threshold": 0.8,
            "hold_days": 3,
        },
    }
    resolved = validate_and_resolve_config(config)
    params = resolved["strategy_params"]
    assert params["entry_threshold"] == pytest.approx(0.8)
    assert params["z_score_threshold"] == pytest.approx(0.8)


def test_momentum_top_k_validation_remains_strict() -> None:
    config = {
        **_base_config(),
        "strategy": "MOMENTUM",
        "strategy_params": {
            "lookback_days": 5,
            "skip_days": 1,
            "top_k": 3,  # greater than instrument count (2)
            "rebalance_frequency": "MONTHLY",
            "weighting": "EQUAL",
        },
    }
    with pytest.raises(ValueError, match="top_k cannot exceed number of instruments in universe"):
        validate_and_resolve_config(config)
