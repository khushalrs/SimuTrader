from __future__ import annotations

from datetime import date, timedelta

import duckdb
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.backtests import router as backtests_router
from app.api.routes.capabilities import router as capabilities_router
from app.security import ActorContext, ActorTier, get_current_actor
from app.security.rate_limit import clear_memory_rate_limits
from app.services.preflight import run_preflight
from app.settings import get_settings


@pytest.fixture(autouse=True)
def _reset_settings_and_rate_limits():
    get_settings.cache_clear()
    clear_memory_rate_limits()
    yield
    get_settings.cache_clear()
    clear_memory_rate_limits()


def _seed_mixed_duckdb(path: str, *, include_fx: bool = True) -> None:
    con = duckdb.connect(path)
    con.execute(
        """
        CREATE TABLE prices (
            date DATE,
            symbol VARCHAR,
            asset_class VARCHAR,
            currency VARCHAR,
            open DOUBLE,
            high DOUBLE,
            low DOUBLE,
            close DOUBLE,
            volume DOUBLE,
            exchange VARCHAR,
            data_source VARCHAR
        )
        """
    )
    rows = []
    current = date(2024, 1, 2)
    end = date(2024, 1, 10)
    while current <= end:
        if current.weekday() < 5:
            rows.extend(
                [
                    (current, "AAPL", "US_EQUITY", "USD", 100.0, 101.0, 99.0, 100.0, 1000.0, "NASDAQ", "seed"),
                    (current, "RELIANCE", "IN_EQUITY", "INR", 2500.0, 2510.0, 2490.0, 2500.0, 1000.0, "NSE", "seed"),
                ]
            )
            if include_fx:
                rows.append(
                    (current, "USDINR", "FX", "INR", 83.0, 83.0, 83.0, 83.0, 1000.0, "FX", "seed")
                )
        current += timedelta(days=1)
    con.executemany("INSERT INTO prices VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", rows)
    con.close()


def _mixed_buy_and_hold_config() -> dict:
    return {
        "version": 1,
        "strategy": "BUY_AND_HOLD",
        "base_currency": "USD",
        "universe": {
            "instruments": [
                {"symbol": "AAPL", "asset_class": "US_EQUITY", "amount": 1000.0},
                {"symbol": "RELIANCE", "asset_class": "IN_EQUITY", "amount": 80000.0},
            ]
        },
        "backtest": {
            "start_date": "2024-01-02",
            "end_date": "2024-01-10",
            "initial_cash": 10000.0,
            "initial_cash_by_currency": {"USD": 2000.0, "INR": 100000.0},
        },
        "data_policy": {"missing_fx": "FORWARD_FILL"},
    }


def test_capabilities_returns_strategy_matrix():
    app = FastAPI()
    app.include_router(capabilities_router)
    client = TestClient(app)

    res = client.get("/capabilities")

    assert res.status_code == 200
    payload = res.json()
    assert payload["strategies"]["BUY_AND_HOLD"]["supports_mixed_currency"] is True
    assert payload["strategies"]["MOMENTUM"]["supports_mixed_currency"] is True
    assert payload["strategies"]["MOMENTUM"]["allocation_modes"] == ["equal"]
    assert payload["strategies"]["MOMENTUM"]["required_params"] == [
        "lookback_days",
        "top_k",
    ]


def test_strategy_schemas_exposes_runtime_parameter_contracts():
    app = FastAPI()
    app.include_router(capabilities_router)
    client = TestClient(app)

    res = client.get("/strategy-schemas")

    assert res.status_code == 200
    payload = res.json()
    assert set(payload) == {
        "BUY_AND_HOLD",
        "FIXED_WEIGHT_REBALANCE",
        "DCA",
        "MOMENTUM",
        "MEAN_REVERSION",
    }
    for schema in payload.values():
        assert set(schema) == {
            "required_params",
            "optional_params",
            "defaults",
            "param_types",
            "description",
            "supported_allocation_modes",
            "supported_asset_classes",
            "supports_shorting",
            "supports_margin",
            "supports_mixed_currency",
        }
        assert set(schema["required_params"] + schema["optional_params"]) == set(
            schema["param_types"]
        )
        assert set(schema["defaults"]).issubset(schema["optional_params"])
        assert schema["description"]
    momentum = payload["MOMENTUM"]
    assert momentum["defaults"] == {
        "skip_days": 1,
        "rebalance_frequency": "MONTHLY",
        "weighting": "EQUAL",
    }
    assert momentum["param_types"]["lookback_days"]["type"] == "integer"
    assert momentum["param_types"]["lookback_days"]["min"] == 1
    assert momentum["param_types"]["lookback_days"]["description"]
    assert momentum["param_types"]["top_k"]["min"] == 1
    assert momentum["supported_allocation_modes"] == ["equal"]
    assert momentum["supported_asset_classes"] == ["US_EQUITY", "IN_EQUITY"]
    assert momentum["supports_shorting"] is False
    assert momentum["supports_margin"] is True
    assert momentum["supports_mixed_currency"] is True

    fixed = payload["FIXED_WEIGHT_REBALANCE"]
    assert fixed["required_params"] == ["target_weights"]
    assert fixed["param_types"]["drift_threshold"]["type"] == "number"
    assert fixed["param_types"]["drift_threshold"]["min"] == 0.0
    assert fixed["param_types"]["drift_threshold"]["max"] == 1.0
    assert fixed["param_types"]["drift_threshold"]["description"]

    mean_reversion = payload["MEAN_REVERSION"]
    assert mean_reversion["defaults"] == {"rebalance_frequency": "DAILY"}
    assert mean_reversion["param_types"]["hold_days"]["min"] == 1

    openapi = app.openapi()
    response_schema = openapi["paths"]["/strategy-schemas"]["get"]["responses"]["200"][
        "content"
    ]["application/json"]["schema"]
    assert response_schema["additionalProperties"]["$ref"].endswith(
        "/StrategySchemaOut"
    )


def test_mixed_us_india_buy_and_hold_preflights_cleanly(tmp_path, monkeypatch):
    duckdb_path = tmp_path / "mixed.duckdb"
    _seed_mixed_duckdb(str(duckdb_path), include_fx=True)
    monkeypatch.setenv("DUCKDB_PATH", str(duckdb_path))

    result = run_preflight(_mixed_buy_and_hold_config())

    assert result["ok"] is True
    assert result["errors"] == []
    assert result["required_fx_pairs"] == ["USDINR"]
    assert result["effective_start_date"] == date(2024, 1, 2)
    assert result["effective_end_date"] == date(2024, 1, 10)
    assert {row["symbol"] for row in result["data_coverage"]} == {"AAPL", "RELIANCE"}
    assert result["strategy_capability"]["supports_mixed_currency"] is True
    assert result["estimated_trading_days"] == 7
    assert result["estimated_symbols"] == 2
    assert result["estimated_rebalance_count"] == 1
    assert result["risk_flags"] == []


def test_preflight_warns_when_explain_capture_will_hit_cap(tmp_path, monkeypatch):
    duckdb_path = tmp_path / "explain_cap.duckdb"
    _seed_mixed_duckdb(str(duckdb_path), include_fx=True)
    monkeypatch.setenv("DUCKDB_PATH", str(duckdb_path))
    config = _mixed_buy_and_hold_config()
    config["explain"] = {
        "enabled": True,
        "capture": "REBALANCE_ONLY",
        "max_records": 1,
    }

    result = run_preflight(config)

    assert result["ok"] is True
    assert any(
        flag["code"] == "EXPLAIN_CAPTURE_WILL_TRUNCATE"
        for flag in result["risk_flags"]
    )


def test_preflight_rejects_missing_benchmark_data(tmp_path, monkeypatch):
    duckdb_path = tmp_path / "missing_benchmark.duckdb"
    _seed_mixed_duckdb(str(duckdb_path), include_fx=True)
    monkeypatch.setenv("DUCKDB_PATH", str(duckdb_path))
    config = _mixed_buy_and_hold_config()
    config["benchmark"] = "DOES_NOT_EXIST"

    result = run_preflight(config)

    assert result["ok"] is False
    assert any("No benchmark market data" in error for error in result["errors"])
    assert any(
        flag["code"] == "MISSING_BENCHMARK_DATA"
        for flag in result["risk_flags"]
    )


def test_preflight_warns_on_partial_benchmark_coverage(tmp_path, monkeypatch):
    duckdb_path = tmp_path / "partial_benchmark.duckdb"
    _seed_mixed_duckdb(str(duckdb_path), include_fx=True)
    con = duckdb.connect(str(duckdb_path))
    con.execute(
        """
        INSERT INTO prices
        SELECT date, 'SPY', asset_class, currency, open, high, low, close, volume,
               exchange, data_source
        FROM prices
        WHERE symbol = 'AAPL'
          AND date BETWEEN DATE '2024-01-04' AND DATE '2024-01-08'
        """
    )
    con.close()
    monkeypatch.setenv("DUCKDB_PATH", str(duckdb_path))
    config = _mixed_buy_and_hold_config()
    config["benchmark"] = "SPY"

    result = run_preflight(config)

    assert result["ok"] is True
    assert any("partial coverage" in warning for warning in result["warnings"])
    assert any(
        flag["code"] == "PARTIAL_BENCHMARK_COVERAGE"
        for flag in result["risk_flags"]
    )


def test_backtest_preflight_route_accepts_raw_config(tmp_path, monkeypatch):
    duckdb_path = tmp_path / "mixed_route.duckdb"
    _seed_mixed_duckdb(str(duckdb_path), include_fx=True)
    monkeypatch.setenv("DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("REDIS_CACHE_URL", "")
    app = FastAPI()
    app.include_router(backtests_router)
    client = TestClient(app)

    res = client.post("/backtests/preflight", json=_mixed_buy_and_hold_config())

    assert res.status_code == 200
    payload = res.json()
    assert payload["ok"] is True
    assert payload["required_fx_pairs"] == ["USDINR"]

    operation = app.openapi()["paths"]["/backtests/preflight"]["post"]
    assert operation["requestBody"]["content"]["application/json"]["schema"] == {
        "anyOf": [
            {"$ref": "#/components/schemas/BacktestPreflightRequest"},
            {"additionalProperties": True, "type": "object"},
        ],
        "title": "Payload",
    }
    assert operation["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/BacktestPreflightOut"
    }


def test_backtest_preflight_route_is_rate_limited(tmp_path, monkeypatch):
    duckdb_path = tmp_path / "mixed_route_limited.duckdb"
    _seed_mixed_duckdb(str(duckdb_path), include_fx=True)
    monkeypatch.setenv("DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("REDIS_CACHE_URL", "")
    monkeypatch.setenv("MAX_MARKET_REQUESTS_PER_WINDOW_GUEST", "1")
    monkeypatch.setenv("MARKET_REQUEST_WINDOW_SECONDS", "60")
    actor = ActorContext(tier=ActorTier.GUEST, actor_key="guest:preflight-test")
    app = FastAPI()
    app.include_router(backtests_router)
    app.dependency_overrides[get_current_actor] = lambda: actor
    client = TestClient(app)

    first = client.post("/backtests/preflight", json=_mixed_buy_and_hold_config())
    second = client.post("/backtests/preflight", json=_mixed_buy_and_hold_config())

    assert first.status_code == 200
    assert second.status_code == 429
    assert second.headers["Retry-After"] == "60"


def test_mixed_us_india_momentum_preflight_succeeds():
    config = _mixed_buy_and_hold_config()
    config["strategy"] = "MOMENTUM"
    config["strategy_params"] = {
        "lookback_days": 3,
        "skip_days": 1,
        "top_k": 1,
        "weighting": "EQUAL",
    }

    result = run_preflight(config)

    assert result["ok"] is True
    assert result["errors"] == []


def test_preflight_reports_missing_fx_history(tmp_path, monkeypatch):
    duckdb_path = tmp_path / "mixed_no_fx.duckdb"
    _seed_mixed_duckdb(str(duckdb_path), include_fx=False)
    monkeypatch.setenv("DUCKDB_PATH", str(duckdb_path))

    result = run_preflight(_mixed_buy_and_hold_config())

    assert result["ok"] is False
    assert result["required_fx_pairs"] == ["USDINR"]
    assert any("Missing USDINR FX history" in error for error in result["errors"])
    assert any(flag["code"] == "MISSING_FX_DATA" for flag in result["risk_flags"])


def test_preflight_flags_weight_sum_and_disabled_shorting() -> None:
    config = _mixed_buy_and_hold_config()
    config["strategy"] = "FIXED_WEIGHT_REBALANCE"
    config["strategy_params"] = {
        "target_weights": {"AAPL": 1.1, "RELIANCE": -0.2},
        "rebalance_frequency": "MONTHLY",
    }

    result = run_preflight(config)

    assert result["ok"] is False
    assert {flag["code"] for flag in result["risk_flags"]} >= {
        "SHORTING_DISABLED",
    }


def test_preflight_flags_non_normalized_weights(tmp_path, monkeypatch) -> None:
    duckdb_path = tmp_path / "weights.duckdb"
    _seed_mixed_duckdb(str(duckdb_path), include_fx=True)
    monkeypatch.setenv("DUCKDB_PATH", str(duckdb_path))
    config = _mixed_buy_and_hold_config()
    config["strategy"] = "FIXED_WEIGHT_REBALANCE"
    config["strategy_params"] = {
        "target_weights": {"AAPL": 0.6, "RELIANCE": 0.3},
        "rebalance_frequency": "MONTHLY",
    }

    result = run_preflight(config)

    assert result["ok"] is False
    assert any(flag["code"] == "WEIGHTS_NOT_NORMALIZED" for flag in result["risk_flags"])


def test_preflight_flags_leverage_and_top_k_before_validation() -> None:
    leverage_config = _mixed_buy_and_hold_config()
    leverage_config["risk"] = {"max_gross_leverage": 1.5, "max_net_leverage": 1.0}
    leverage_result = run_preflight(leverage_config)
    assert any(flag["code"] == "MARGIN_DISABLED" for flag in leverage_result["risk_flags"])

    momentum_config = _mixed_buy_and_hold_config()
    momentum_config["strategy"] = "MOMENTUM"
    momentum_config["strategy_params"] = {
        "lookback_days": 3,
        "skip_days": 1,
        "top_k": 3,
        "weighting": "EQUAL",
    }
    momentum_result = run_preflight(momentum_config)
    assert any(
        flag["code"] == "TOP_K_EXCEEDS_UNIVERSE"
        for flag in momentum_result["risk_flags"]
    )


def test_preflight_flags_insufficient_momentum_coverage(tmp_path, monkeypatch) -> None:
    duckdb_path = tmp_path / "short_momentum.duckdb"
    _seed_mixed_duckdb(str(duckdb_path), include_fx=True)
    monkeypatch.setenv("DUCKDB_PATH", str(duckdb_path))
    config = _mixed_buy_and_hold_config()
    config["strategy"] = "MOMENTUM"
    config["strategy_params"] = {
        "lookback_days": 7,
        "skip_days": 1,
        "top_k": 1,
        "weighting": "EQUAL",
    }

    result = run_preflight(config)

    assert result["ok"] is False
    assert any(
        flag["code"] == "INSUFFICIENT_MOMENTUM_LOOKBACK"
        for flag in result["risk_flags"]
    )


def test_dca_large_contribution_is_warning_not_error(tmp_path, monkeypatch) -> None:
    duckdb_path = tmp_path / "dca_warning.duckdb"
    _seed_mixed_duckdb(str(duckdb_path), include_fx=True)
    monkeypatch.setenv("DUCKDB_PATH", str(duckdb_path))
    config = _mixed_buy_and_hold_config()
    config["strategy"] = "DCA"
    config["strategy_params"] = {"buy_frequency": "DAILY", "weighting": "EQUAL"}
    config["backtest"]["contributions"] = {
        "enabled": True,
        "amount": 3000.0,
        "frequency": "MONTHLY",
    }

    result = run_preflight(config)

    assert result["ok"] is True
    assert result["errors"] == []
    assert any(
        flag["code"] == "DCA_CONTRIBUTION_EXCEEDS_CASH"
        and flag["severity"] == "warning"
        for flag in result["risk_flags"]
    )
