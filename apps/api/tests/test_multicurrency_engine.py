from __future__ import annotations

from datetime import date, timedelta
from uuid import uuid4

import duckdb
import pytest

from app.backtest.executor import execute_run
from app.models.backtests import BacktestRun
from test_backtest_integration import _FakeSession


def _seed_mixed_market(path: str, start: date, end: date) -> None:
    con = duckdb.connect(path)
    con.execute("CREATE TABLE trading_calendars (calendar_id VARCHAR, name VARCHAR)")
    con.executemany(
        "INSERT INTO trading_calendars VALUES (?, ?)",
        [("us", "US"), ("in", "IN"), ("fx", "FX")],
    )
    con.execute(
        "CREATE TABLE calendar_days (calendar_id VARCHAR, date DATE, is_trading_day BOOLEAN)"
    )
    calendar_rows = []
    price_rows = []
    current = start
    while current <= end:
        open_day = current.weekday() < 5
        for calendar_id in ("us", "in", "fx"):
            calendar_rows.append((calendar_id, current, open_day))
        if open_day:
            step = (current - start).days
            price_rows.extend(
                [
                    (current, "AAPL", "US_EQUITY", "USD", 100.0 + step),
                    (current, "RELIANCE", "IN_EQUITY", "INR", 2000.0 + step * 30.0),
                    (current, "USDINR", "FX", "INR", 80.0),
                ]
            )
        current += timedelta(days=1)
    con.executemany("INSERT INTO calendar_days VALUES (?, ?, ?)", calendar_rows)
    con.execute(
        """
        CREATE TABLE prices (
            date DATE, symbol VARCHAR, asset_class VARCHAR, currency VARCHAR,
            open DOUBLE, high DOUBLE, low DOUBLE, close DOUBLE,
            volume DOUBLE, exchange VARCHAR, data_source VARCHAR
        )
        """
    )
    con.executemany(
        "INSERT INTO prices VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (day, symbol, asset_class, currency, close, close, close, close, 1000.0, "TEST", "seed")
            for day, symbol, asset_class, currency, close in price_rows
        ],
    )
    con.execute(
        """
        CREATE VIEW calendar_pivot AS
        SELECT d.date,
          max(c.name = 'US' AND d.is_trading_day)::boolean AS is_us_trading,
          max(c.name = 'IN' AND d.is_trading_day)::boolean AS is_in_trading,
          max(c.name = 'FX' AND d.is_trading_day)::boolean AS is_fx_trading
        FROM calendar_days d JOIN trading_calendars c USING (calendar_id)
        GROUP BY d.date
        """
    )
    con.execute(
        """
        CREATE VIEW global_calendar AS
        SELECT *, (is_us_trading OR is_in_trading OR is_fx_trading) AS is_global_trading
        FROM calendar_pivot
        """
    )
    con.execute(
        "CREATE VIEW global_trading_days AS SELECT date FROM global_calendar WHERE is_global_trading"
    )
    con.close()


def test_mixed_currency_momentum_fx_sweep_and_base_accounting(tmp_path, monkeypatch):
    start = date(2024, 1, 2)
    end = date(2024, 1, 19)
    path = tmp_path / "mixed.duckdb"
    _seed_mixed_market(str(path), start, end)
    monkeypatch.setenv("DUCKDB_PATH", str(path))

    db = _FakeSession()
    run = BacktestRun(
        run_id=uuid4(),
        status="QUEUED",
        config_snapshot={
            "strategy": "MOMENTUM",
            "base_currency": "USD",
            "strategy_params": {
                "lookback_days": 2,
                "skip_days": 0,
                "top_k": 1,
                "rebalance_frequency": "WEEKLY",
                "weighting": "EQUAL",
            },
            "universe": {
                "instruments": [
                    {"symbol": "AAPL", "asset_class": "US_EQUITY"},
                    {"symbol": "RELIANCE", "asset_class": "IN_EQUITY"},
                ]
            },
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "initial_cash": 10_000.0,
            "commission": {"model": "BPS", "bps": 0.0},
            "slippage": {"model": "BPS", "bps": 10.0},
        },
        data_snapshot_id="mixed_snapshot",
        seed=42,
    )

    execute_run(db, run)

    assert run.status == "SUCCEEDED"
    sweeps = [fill for fill in db.fill_rows if fill.meta.get("kind") == "FX_SWEEP"]
    assert sweeps
    first_sweep = sweeps[0]
    assert first_sweep.symbol == "USDINR"
    assert first_sweep.commission_native == 0.0
    assert first_sweep.slippage_native == pytest.approx(
        first_sweep.notional_native * 0.001
    )

    sweep_day_equity = next(row for row in db.equity_rows if row.date == first_sweep.date)
    assert sweep_day_equity.equity_base == pytest.approx(
        10_000.0 - sweep_day_equity.fees_cum_base, rel=1e-9
    )

    final_position = next(
        row
        for row in reversed(db.position_rows)
        if row.symbol == "RELIANCE" and row.qty > 0
    )
    final_close = 2000.0 + (final_position.date - start).days * 30.0
    native_pnl = (final_close - final_position.avg_cost_native) * final_position.qty
    assert final_position.unrealized_pnl_base == pytest.approx(native_pnl / 80.0)

    reliance_fill = next(fill for fill in db.fill_rows if fill.symbol == "RELIANCE")
    assert first_sweep.qty == pytest.approx(
        reliance_fill.notional_native + reliance_fill.commission_native
    )
