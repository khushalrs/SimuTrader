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


def test_negative_weights_require_shorting_enabled() -> None:
    config = _base_config()
    config["universe"]["instruments"][0]["weight"] = -0.25
    config["universe"]["instruments"][1]["weight"] = 0.75
    with pytest.raises(ValueError, match="negative weights require"):
        validate_and_resolve_config(config)


def test_leverage_requires_margin_enabled() -> None:
    config = _base_config()
    config["risk"] = {"max_gross_leverage": 1.5, "max_net_leverage": 1.0}
    with pytest.raises(ValueError, match="max_gross_leverage > 1 requires"):
        validate_and_resolve_config(config)


def test_mixed_currency_momentum_validation_is_supported() -> None:
    config = _base_config()
    config["strategy"] = "MOMENTUM"
    config["strategy_params"] = {
        "lookback_days": 5,
        "skip_days": 1,
        "top_k": 1,
        "weighting": "EQUAL",
    }
    config["universe"]["instruments"][1]["asset_class"] = "IN_EQUITY"
    resolved = validate_and_resolve_config(config)
    assert resolved["strategy"] == "MOMENTUM"


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


def test_canonical_cost_fields_win_over_stale_execution_aliases() -> None:
    config = _base_config()
    config["commission"] = {"model": "BPS", "bps": 5, "min_fee_native": 2}
    config["slippage"] = {"model": "BPS", "bps": 2}
    config["execution"] = {
        "commission": {"bps": 500},
        "slippage": {"bps": 75},
    }

    resolved = validate_and_resolve_config(config)

    assert resolved["commission"] == {
        "model": "BPS",
        "bps": pytest.approx(5),
        "min_fee_native": pytest.approx(2),
    }
    assert resolved["slippage"] == {
        "model": "BPS",
        "bps": pytest.approx(2),
    }
    assert "execution" not in resolved
    assert validate_and_resolve_config(resolved) == resolved


def test_config_sanitizes_control_characters() -> None:
    config = _base_config()
    config["universe"]["instruments"][0]["symbol"] = "AAPL\x00\x01"
    resolved = validate_and_resolve_config(config)
    assert resolved["universe"]["instruments"][0]["symbol"] == "AAPL"


def test_config_accepts_explicit_or_null_benchmark() -> None:
    explicit = _base_config()
    explicit["benchmark"] = "SPY"
    assert validate_and_resolve_config(explicit)["benchmark"] == "SPY"

    disabled = _base_config()
    disabled["benchmark"] = None
    assert validate_and_resolve_config(disabled)["benchmark"] is None


def test_evaluation_start_date_is_validated_within_backtest_window() -> None:
    config = _base_config()
    config["backtest"]["evaluation_start_date"] = "2024-01-15"
    resolved = validate_and_resolve_config(config)
    assert resolved["backtest"]["evaluation_start_date"] == "2024-01-15"

    config["backtest"]["evaluation_start_date"] = "2024-02-01"
    with pytest.raises(ValueError, match="evaluation_start_date must be <= end_date"):
        validate_and_resolve_config(config)
