from __future__ import annotations

from datetime import date, timedelta
from uuid import uuid4

import duckdb
import pytest

from app.backtest.engine import run_engine
from app.models.backtests import (
    BacktestRun,
    RunDailyEquity,
    RunFill,
    RunFinancing,
    RunMetric,
    RunOrder,
    RunPosition,
    RunTaxEvent,
)


class _FakeQuery:
    def __init__(self, session, model):
        self._session = session
        self._model = model

    def filter(self, *args, **kwargs):  # noqa: ANN002, ANN003
        return self

    def delete(self, synchronize_session=False):  # noqa: ANN001
        if self._model is RunDailyEquity:
            self._session.equity_rows = []
        elif self._model is RunMetric:
            self._session.metrics_rows = []
        elif self._model is RunOrder:
            self._session.order_rows = []
        elif self._model is RunFill:
            self._session.fill_rows = []
        elif self._model is RunPosition:
            self._session.position_rows = []
        elif self._model is RunFinancing:
            self._session.financing_rows = []
        elif self._model is RunTaxEvent:
            self._session.tax_rows = []
        return 0


class _FakeSession:
    def __init__(self):
        self.equity_rows: list[RunDailyEquity] = []
        self.metrics_rows: list[RunMetric] = []
        self.order_rows: list[RunOrder] = []
        self.fill_rows: list[RunFill] = []
        self.position_rows: list[RunPosition] = []
        self.financing_rows: list[RunFinancing] = []
        self.tax_rows: list[RunTaxEvent] = []

    def query(self, model):
        return _FakeQuery(self, model)

    def bulk_save_objects(self, records):
        if not records:
            return
        first = records[0]
        if isinstance(first, RunDailyEquity):
            self.equity_rows.extend(records)
        elif isinstance(first, RunOrder):
            self.order_rows.extend(records)
        elif isinstance(first, RunFill):
            self.fill_rows.extend(records)
        elif isinstance(first, RunPosition):
            self.position_rows.extend(records)
        elif isinstance(first, RunFinancing):
            self.financing_rows.extend(records)
        elif isinstance(first, RunTaxEvent):
            self.tax_rows.extend(records)

    def add(self, obj):
        if isinstance(obj, RunMetric):
            self.metrics_rows.append(obj)


def _seed_duckdb(path: str, symbol: str, start: date, end: date) -> None:
    con = duckdb.connect(path)
    con.execute(
        """
        CREATE TABLE trading_calendars (calendar_id VARCHAR, name VARCHAR);
        """
    )
    con.executemany(
        "INSERT INTO trading_calendars VALUES (?, ?)",
        [("us", "US"), ("in", "IN"), ("fx", "FX")],
    )
    con.execute(
        """
        CREATE TABLE calendar_days (calendar_id VARCHAR, date DATE, is_trading_day BOOLEAN);
        """
    )
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

    cal_rows = []
    price_rows = []
    d = start
    day_idx = 0
    while d <= end:
        is_weekday = d.weekday() < 5
        cal_rows.append(("us", d.isoformat(), is_weekday))
        cal_rows.append(("in", d.isoformat(), is_weekday))
        cal_rows.append(("fx", d.isoformat(), is_weekday))
        if is_weekday:
            px = 100.0 + day_idx
            price_rows.append(
                (
                    d.isoformat(),
                    symbol,
                    "US_EQUITY",
                    "USD",
                    px,
                    px,
                    px,
                    px,
                    1000.0,
                    "NYSE",
                    "seed",
                )
            )
            usd_inr = 80.0
            price_rows.append(
                (
                    d.isoformat(),
                    "USDINR",
                    "FX",
                    "INR",
                    usd_inr,
                    usd_inr,
                    usd_inr,
                    usd_inr,
                    1000.0,
                    "FX",
                    "seed",
                )
            )
            day_idx += 1
        d += timedelta(days=1)

    con.executemany("INSERT INTO calendar_days VALUES (?, ?, ?)", cal_rows)
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


def test_fifo_realized_pnl_and_us_tax_events(tmp_path, monkeypatch):
    duckdb_path = tmp_path / "fifo_tax.duckdb"
    start = date(2024, 1, 2)
    end = date(2024, 1, 5)
    _seed_duckdb(str(duckdb_path), "AAA", start, end)
    monkeypatch.setenv("DUCKDB_PATH", str(duckdb_path))

    run = BacktestRun(
        run_id=uuid4(),
        status="QUEUED",
        config_snapshot={
            "base_currency": "USD",
            "financing": {
                "margin": {"enabled": False, "max_leverage": 1.0, "daily_interest_bps": 0.0},
                "shorting": {"enabled": True, "borrow_fee_daily_bps": 0.0},
            },
            "risk": {"max_gross_leverage": 1.0, "max_net_leverage": 1.0},
            "tax": {
                "regime": "US",
                "us": {"short_term_days": 365, "short_rate": 0.30, "long_rate": 0.15},
            },
            "data_policy": {"missing_fx": "FORWARD_FILL"},
        },
        data_snapshot_id="snap",
        seed=42,
    )
    db = _FakeSession()

    trade_days: list[date] = []

    def target_allocations(ctx):
        if not trade_days:
            trade_days.append(ctx.date)
            return {"AAA": ctx.prices["AAA"] * 10.0}
        if ctx.date == trade_days[0] + timedelta(days=1):
            return {"AAA": ctx.prices["AAA"] * 4.0}
        if ctx.date == trade_days[0] + timedelta(days=2):
            return {"AAA": 0.0}
        return None

    run_engine(
        db=db,
        run=run,
        instruments=[{"symbol": "AAA", "asset_class": "US_EQUITY"}],
        calendars_map=None,
        start_date=start,
        end_date=end,
        initial_cash=10000.0,
        initial_cash_by_currency=None,
        target_allocations_fn=target_allocations,
        commission_cfg={"model": "BPS", "bps": 0, "min_fee_native": 0},
        slippage_cfg={"model": "BPS", "bps": 0},
        fill_price_policy="CLOSE",
        allocation_mode="AMOUNT",
        include_financing=True,
    )

    assert len(db.tax_rows) == 2
    total_realized = sum(row.realized_pnl_base for row in db.tax_rows)
    total_tax_due = sum(row.tax_due_base for row in db.tax_rows)
    assert total_realized == 14.0
    assert total_tax_due == pytest.approx(4.2)
    assert all(row.bucket == "US_ST" for row in db.tax_rows)
    assert db.equity_rows[-1].taxes_cum_base == pytest.approx(4.2)
    assert db.metrics_rows[0].tax_drag == pytest.approx(4.2 / 10000.0)


def test_short_cover_creates_tax_event_and_india_lt_bucket(tmp_path, monkeypatch):
    duckdb_path = tmp_path / "short_tax.duckdb"
    start = date(2024, 1, 2)
    end = date(2025, 1, 10)
    _seed_duckdb(str(duckdb_path), "BBB", start, end)
    monkeypatch.setenv("DUCKDB_PATH", str(duckdb_path))

    run = BacktestRun(
        run_id=uuid4(),
        status="QUEUED",
        config_snapshot={
            "base_currency": "USD",
            "financing": {
                "margin": {"enabled": True, "max_leverage": 2.0, "daily_interest_bps": 0.0},
                "shorting": {"enabled": True, "borrow_fee_daily_bps": 0.0},
            },
            "risk": {"max_gross_leverage": 2.0, "max_net_leverage": 2.0},
            "tax": {
                "regime": "INDIA",
                "india": {"short_term_days": 365, "short_rate": 0.15, "long_rate": 0.10},
            },
            "data_policy": {"missing_fx": "FORWARD_FILL"},
        },
        data_snapshot_id="snap",
        seed=42,
    )
    db = _FakeSession()
    first_day = start
    cover_day = date(2025, 1, 8)

    def target_allocations(ctx):
        if ctx.date == first_day:
            return {"BBB": -(ctx.prices["BBB"] * 5.0)}
        if ctx.date == cover_day:
            return {"BBB": 0.0}
        return None

    run_engine(
        db=db,
        run=run,
        instruments=[{"symbol": "BBB", "asset_class": "US_EQUITY"}],
        calendars_map=None,
        start_date=start,
        end_date=end,
        initial_cash=10000.0,
        initial_cash_by_currency=None,
        target_allocations_fn=target_allocations,
        commission_cfg={"model": "BPS", "bps": 0, "min_fee_native": 0},
        slippage_cfg={"model": "BPS", "bps": 0},
        fill_price_policy="CLOSE",
        allocation_mode="AMOUNT",
        include_financing=True,
    )

    cover_events = [row for row in db.tax_rows if row.meta.get("side") == "COVER"]
    assert len(cover_events) == 1
    assert cover_events[0].bucket == "INDIA_LT"


def test_india_defaults_apply_when_rates_omitted(tmp_path, monkeypatch):
    duckdb_path = tmp_path / "india_defaults.duckdb"
    start = date(2024, 1, 2)
    end = date(2024, 1, 5)
    _seed_duckdb(str(duckdb_path), "CCC", start, end)
    monkeypatch.setenv("DUCKDB_PATH", str(duckdb_path))

    run = BacktestRun(
        run_id=uuid4(),
        status="QUEUED",
        config_snapshot={
            "base_currency": "USD",
            "financing": {
                "margin": {"enabled": False, "max_leverage": 1.0, "daily_interest_bps": 0.0},
                "shorting": {"enabled": False, "borrow_fee_daily_bps": 0.0},
            },
            "risk": {"max_gross_leverage": 1.0, "max_net_leverage": 1.0},
            "tax": {
                "regime": "INDIA",
                "india": {"short_term_days": 365},
            },
            "data_policy": {"missing_fx": "FORWARD_FILL"},
        },
        data_snapshot_id="snap",
        seed=42,
    )
    db = _FakeSession()
    first_day: date | None = None

    def target_allocations(ctx):
        nonlocal first_day
        if first_day is None:
            first_day = ctx.date
            return {"CCC": ctx.prices["CCC"] * 10.0}
        if ctx.date == first_day + timedelta(days=2):
            return {"CCC": 0.0}
        return None

    run_engine(
        db=db,
        run=run,
        instruments=[{"symbol": "CCC", "asset_class": "US_EQUITY"}],
        calendars_map=None,
        start_date=start,
        end_date=end,
        initial_cash=10000.0,
        initial_cash_by_currency=None,
        target_allocations_fn=target_allocations,
        commission_cfg={"model": "BPS", "bps": 0, "min_fee_native": 0},
        slippage_cfg={"model": "BPS", "bps": 0},
        fill_price_policy="CLOSE",
        allocation_mode="AMOUNT",
        include_financing=True,
    )

    assert db.tax_rows, "Expected tax events when realizing gains"
    assert all(row.bucket == "INDIA_ST" for row in db.tax_rows)
    assert all(row.tax_rate == pytest.approx(0.20) for row in db.tax_rows)
