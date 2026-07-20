from __future__ import annotations

from datetime import date, timedelta

import duckdb
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes import data as data_routes


def _seed_data(path: str) -> None:
    con = duckdb.connect(path)
    con.execute(
        """
        CREATE TABLE prices (
            date DATE, symbol VARCHAR, asset_class VARCHAR, currency VARCHAR,
            open DOUBLE, high DOUBLE, low DOUBLE, close DOUBLE, volume DOUBLE,
            exchange VARCHAR, data_source VARCHAR
        )
        """
    )
    start = date(2024, 1, 1)
    rows = []
    for offset in range(5):
        day = start + timedelta(days=offset)
        if day.weekday() >= 5 or day == date(2024, 1, 3):
            continue
        rows.append((day, "AAPL", "US_EQUITY", "USD", 99, 102, 98, 100, 1000, "NASDAQ", "test"))
    con.executemany("INSERT INTO prices VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", rows)
    con.execute(
        """
        CREATE VIEW global_calendar AS
        SELECT d::DATE AS date,
               dayofweek(d) BETWEEN 1 AND 5 AS is_us_trading,
               dayofweek(d) BETWEEN 1 AND 5 AS is_in_trading,
               dayofweek(d) BETWEEN 1 AND 5 AS is_fx_trading,
               dayofweek(d) BETWEEN 1 AND 5 AS is_global_trading
        FROM range(DATE '2024-01-01', DATE '2024-01-06', INTERVAL 1 DAY) t(d)
        """
    )
    con.close()


def test_data_observability_endpoints(tmp_path, monkeypatch):
    path = tmp_path / "data.duckdb"
    _seed_data(str(path))
    monkeypatch.setenv("DUCKDB_PATH", str(path))
    monkeypatch.setenv("DUCKDB_READ_ONLY", "true")
    app = FastAPI()
    data_routes._data_cache.clear()
    app.include_router(data_routes.router)
    client = TestClient(app)

    snapshot = client.get("/data/snapshot")
    coverage = client.get(
        "/data/coverage",
        params={"symbols": "AAPL,MISSING", "start": "2024-01-01", "end": "2024-01-05"},
    )
    quality = client.get("/data/quality", params={"symbols": "AAPL"})
    missing = client.get(
        "/data/missing-bars",
        params={"symbols": "AAPL", "start": "2024-01-01", "end": "2024-01-05"},
    )

    assert snapshot.status_code == 200
    assert snapshot.json()["symbol_count"] == 1
    assert snapshot.json()["row_count"] == 4
    assert coverage.status_code == 200
    coverage_by_symbol = {row["symbol"]: row for row in coverage.json()}
    assert {symbol: row["rows"] for symbol, row in coverage_by_symbol.items()} == {
        "AAPL": 4,
        "MISSING": 0,
    }
    assert coverage_by_symbol["AAPL"]["asset_class"] == "US_EQUITY"
    assert coverage_by_symbol["AAPL"]["exchange"] == "NASDAQ"
    assert quality.status_code == 200
    assert quality.json()[0]["quality_score"] == 1.0
    assert missing.status_code == 200
    assert missing.json() == [
        {"symbol": "AAPL", "asset_class": "US_EQUITY", "date": "2024-01-03"}
    ]

    cached_quality = client.get("/data/quality", params={"symbols": "AAPL"})
    assert quality.headers["X-Data-Cache"] == "MISS"
    assert cached_quality.headers["X-Data-Cache"] == "HIT"
    assert cached_quality.json() == quality.json()
