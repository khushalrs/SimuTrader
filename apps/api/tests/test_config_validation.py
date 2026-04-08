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


def test_negative_amount_requires_shorting_enabled() -> None:
    config = _base_config()
    config["universe"]["instruments"][0]["amount"] = -1000
    config["universe"]["instruments"][1]["amount"] = 2000
    with pytest.raises(ValueError, match="negative amount allocations require"):
        validate_and_resolve_config(config)


def test_execution_block_maps_into_legacy_commission_fields() -> None:
    config = _base_config()
    config["execution"] = {
        "commission": {"model": "BPS", "bps": 3, "min_fee": 1.5},
        "slippage": {"model": "BPS", "bps": 7},
        "fill_price": "CLOSE",
    }
    resolved = validate_and_resolve_config(config)
    assert resolved["commission"]["bps"] == pytest.approx(3.0)
    assert resolved["commission"]["min_fee_native"] == pytest.approx(1.5)
    assert resolved["slippage"]["bps"] == pytest.approx(7.0)
    assert resolved["fill_price_policy"] == "CLOSE"


def test_config_sanitizes_control_characters() -> None:
    config = _base_config()
    config["universe"]["instruments"][0]["symbol"] = "AAPL\x00\x01"
    resolved = validate_and_resolve_config(config)
    assert resolved["universe"]["instruments"][0]["symbol"] == "AAPL"
