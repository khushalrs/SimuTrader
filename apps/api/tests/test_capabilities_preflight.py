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
