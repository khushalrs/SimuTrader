from __future__ import annotations

import importlib.util
from datetime import date, timedelta
from pathlib import Path

import duckdb
from fastapi import FastAPI
from fastapi.testclient import TestClient

MARKET_ROUTE_FILE = Path(__file__).resolve().parents[1] / "app" / "api" / "routes" / "market.py"
_market_spec = importlib.util.spec_from_file_location("isolated_market_route", MARKET_ROUTE_FILE)
if _market_spec is None or _market_spec.loader is None:
    raise RuntimeError(f"Failed to load market route module from {MARKET_ROUTE_FILE}")
_market_module = importlib.util.module_from_spec(_market_spec)
_market_spec.loader.exec_module(_market_module)
market_router = _market_module.router


def _seed_duckdb(
    path: str,
    symbols: list[str],
    start: date,
    end: date,
    missing: dict[str, set[date]] | None = None,
) -> None:
    con = duckdb.connect(path)
    con.execute(
        """
        CREATE TABLE trading_calendars (
            calendar_id VARCHAR,
            name VARCHAR
        );
        """
    )
    con.executemany(
        "INSERT INTO trading_calendars VALUES (?, ?)",
        [("us", "US"), ("in", "IN"), ("fx", "FX")],
    )
    con.execute(
        """
        CREATE TABLE calendar_days (
            calendar_id VARCHAR,
            date DATE,
            is_trading_day BOOLEAN
        );
        """
    )

    cal_rows = []
    price_rows = []
    missing = missing or {}
    current = start
    while current <= end:
        is_weekday = current.weekday() < 5
        cal_rows.extend(
            [
                ("us", current.isoformat(), is_weekday),
                ("in", current.isoformat(), is_weekday),
                ("fx", current.isoformat(), is_weekday),
            ]
        )
        if is_weekday:
            for idx, symbol in enumerate(symbols):
                if current in missing.get(symbol, set()):
                    continue
                price = 100.0 + idx * 10.0 + (current - start).days
                price_rows.append(
                    (
                        current.isoformat(),
                        symbol,
                        "US_EQUITY",
                        "USD",
                        price - 1.0,
                        price + 1.0,
                        price - 2.0,
                        price,
                        1000.0 + idx,
                        "NYSE",
                        "seed",
                    )
                )
        current += timedelta(days=1)

    con.executemany("INSERT INTO calendar_days VALUES (?, ?, ?)", cal_rows)
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
        );
        """
    )
    con.executemany(
        "INSERT INTO prices VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        price_rows,
    )
    con.execute(
        """
        CREATE OR REPLACE VIEW calendar_pivot AS
        SELECT
          d.date,
          max(case when c.name = 'US' and d.is_trading_day then 1 else 0 end)::boolean as is_us_trading,
          max(case when c.name = 'IN' and d.is_trading_day then 1 else 0 end)::boolean as is_in_trading,
          max(case when c.name = 'FX' and d.is_trading_day then 1 else 0 end)::boolean as is_fx_trading
        FROM calendar_days d
        JOIN trading_calendars c using (calendar_id)
        GROUP BY 1;
        """
    )
    con.execute(
        """
        CREATE OR REPLACE VIEW global_calendar AS
        SELECT
          date,
          is_us_trading,
          is_in_trading,
          is_fx_trading,
          (is_us_trading or is_in_trading or is_fx_trading) as is_global_trading
        FROM calendar_pivot;
        """
    )
    con.execute(
        """
        CREATE OR REPLACE VIEW global_trading_days AS
        SELECT date
        FROM global_calendar
        WHERE is_global_trading
        ORDER BY date;
        """
    )
    con.close()


def _client() -> TestClient:
    test_app = FastAPI()
    test_app.include_router(market_router)
    return TestClient(test_app)


def _clear_market_caches() -> None:
    _market_module._bars_cache.clear()
    _market_module._snapshot_cache.clear()
    _market_module._redis_client = None


def test_market_bars_returns_rows_within_bounds(tmp_path, monkeypatch):
    duckdb_path = tmp_path / "market_bars.duckdb"
    _seed_duckdb(str(duckdb_path), ["SPY", "QQQ"], date(2024, 1, 1), date(2024, 1, 10))
    monkeypatch.setenv("DUCKDB_PATH", str(duckdb_path))
    _clear_market_caches()

    client = _client()
    res = client.get(
        "/market/bars",
        params={
            "symbols": "SPY,QQQ",
            "start_date": "2024-01-02",
            "end_date": "2024-01-05",
            "fields": "close,volume",
        },
    )
    assert res.status_code == 200
    payload = res.json()
    assert payload
    assert all("close" in row and "volume" in row for row in payload)
    assert all("2024-01-02" <= row["date"] <= "2024-01-05" for row in payload)
    assert res.headers["cache-control"] == "public, max-age=60, stale-while-revalidate=300"


def test_market_bars_forward_fill_is_continuous_with_start_bootstrap(tmp_path, monkeypatch):
    duckdb_path = tmp_path / "market_fill.duckdb"
    missing = {"SPY": {date(2024, 1, 1), date(2024, 1, 4)}}
    _seed_duckdb(str(duckdb_path), ["SPY"], date(2024, 1, 1), date(2024, 1, 8), missing=missing)
    monkeypatch.setenv("DUCKDB_PATH", str(duckdb_path))
    _clear_market_caches()

    client = _client()
    res = client.get(
        "/market/bars",
        params={
            "symbols": "SPY",
            "start_date": "2024-01-01",
            "end_date": "2024-01-08",
            "calendar": "US",
            "missing_bar": "FORWARD_FILL",
        },
    )
    assert res.status_code == 200
    payload = res.json()
    dates = [row["date"] for row in payload]
    assert dates == ["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05", "2024-01-08"]
    assert payload[0]["close"] == payload[1]["close"]
    assert payload[3]["close"] == payload[2]["close"]


def test_market_coverage_returns_first_last_and_rows(tmp_path, monkeypatch):
    duckdb_path = tmp_path / "market_coverage.duckdb"
    missing = {"SPY": {date(2024, 1, 4)}}
    _seed_duckdb(str(duckdb_path), ["SPY"], date(2024, 1, 1), date(2024, 1, 8), missing=missing)
    monkeypatch.setenv("DUCKDB_PATH", str(duckdb_path))
    _clear_market_caches()

    client = _client()
    res = client.get(
        "/market/coverage",
        params={"symbols": "SPY", "start_date": "2024-01-01", "end_date": "2024-01-08", "calendar": "US"},
    )
    assert res.status_code == 200
    payload = res.json()
    assert payload == [
        {
            "symbol": "SPY",
            "first_date": "2024-01-01",
            "last_date": "2024-01-08",
            "rows": 5,
            "missing_ratio": 1 / 6,
        }
    ]


def test_market_snapshot_returns_derived_fields(tmp_path, monkeypatch):
    duckdb_path = tmp_path / "market_snapshot.duckdb"
    _seed_duckdb(str(duckdb_path), ["SPY"], date(2024, 1, 1), date(2025, 3, 1))
    monkeypatch.setenv("DUCKDB_PATH", str(duckdb_path))
    _clear_market_caches()

    client = _client()
    res = client.get("/market/snapshot", params={"symbols": "SPY"})
    assert res.status_code == 200
    payload = res.json()
    assert len(payload) == 1
    assert payload[0]["symbol"] == "SPY"
    assert payload[0]["last_close"] > 0
    assert "return_1m" in payload[0]
    assert "recent_vol_20d" in payload[0]
    assert res.headers["cache-control"] == "public, max-age=30, stale-while-revalidate=300"


def test_market_snapshot_uses_cache(tmp_path, monkeypatch):
    duckdb_path = tmp_path / "market_snapshot_cache.duckdb"
    _seed_duckdb(str(duckdb_path), ["SPY"], date(2024, 1, 1), date(2025, 3, 1))
    monkeypatch.setenv("DUCKDB_PATH", str(duckdb_path))
    _clear_market_caches()

    client = _client()
    first = client.get("/market/snapshot", params={"symbols": "SPY"})
    assert first.status_code == 200

    monkeypatch.setattr(_market_module, "get_duckdb_conn", lambda: (_ for _ in ()).throw(AssertionError("cache miss")))
    second = client.get("/market/snapshot", params={"symbols": "SPY"})
    assert second.status_code == 200
    assert second.json() == first.json()


def test_market_bars_uses_shorter_default_range(tmp_path, monkeypatch):
    duckdb_path = tmp_path / "market_default_range.duckdb"
    _seed_duckdb(str(duckdb_path), ["SPY"], date(2024, 1, 1), date(2025, 3, 1))
    monkeypatch.setenv("DUCKDB_PATH", str(duckdb_path))
    _clear_market_caches()

    client = _client()
    res = client.get("/market/bars", params={"symbols": "SPY"})
    assert res.status_code == 200
    payload = res.json()
    assert payload[0]["date"] == "2024-09-02"
    assert payload[-1]["date"] == "2025-02-28"
    assert all(set(row).issuperset({"date", "symbol", "currency", "exchange", "close"}) for row in payload)
    assert all("volume" not in row for row in payload)


def test_market_bars_uses_cache_and_downsamples(tmp_path, monkeypatch):
    duckdb_path = tmp_path / "market_bars_cache.duckdb"
    _seed_duckdb(str(duckdb_path), ["SPY"], date(2024, 1, 1), date(2024, 3, 1))
    monkeypatch.setenv("DUCKDB_PATH", str(duckdb_path))
    _clear_market_caches()

    client = _client()
    first = client.get(
        "/market/bars",
        params={"symbols": "SPY", "start_date": "2024-01-01", "end_date": "2024-03-01"},
    )
    assert first.status_code == 200

    monkeypatch.setattr(_market_module, "get_duckdb_conn", lambda: (_ for _ in ()).throw(AssertionError("cache miss")))
    second = client.get(
        "/market/bars",
        params={"symbols": "SPY", "start_date": "2024-01-01", "end_date": "2024-03-01", "max_points": 5},
    )
    assert second.status_code == 200
    payload = second.json()
    assert len(payload) == 5
    assert payload == sorted(payload, key=lambda row: (row["date"], row["symbol"]))


def test_market_bars_can_aggregate_weekly(tmp_path, monkeypatch):
    duckdb_path = tmp_path / "market_weekly.duckdb"
    _seed_duckdb(str(duckdb_path), ["SPY"], date(2024, 1, 1), date(2024, 1, 19))
    monkeypatch.setenv("DUCKDB_PATH", str(duckdb_path))
    _clear_market_caches()

    client = _client()
    res = client.get(
        "/market/bars",
        params={
            "symbols": "SPY",
            "start_date": "2024-01-01",
            "end_date": "2024-01-19",
            "fields": "open,high,low,close,volume",
            "interval": "1w",
        },
    )
    assert res.status_code == 200
    payload = res.json()
    assert len(payload) == 3
    assert payload[0]["date"] == "2024-01-05"
    assert payload[0]["open"] == 99.0
    assert payload[0]["close"] == 104.0
    assert payload[0]["high"] == 105.0
    assert payload[0]["low"] == 98.0
    assert payload[0]["volume"] == 5000.0
