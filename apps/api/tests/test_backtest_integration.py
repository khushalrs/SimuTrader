from __future__ import annotations

from datetime import date, timedelta
from uuid import uuid4

import duckdb

from app.backtest.executor import execute_run
import pytest
from app.models.backtests import (
    BacktestRun,
    RunDailyEquity,
    RunFill,
    RunFinancing,
    RunMetric,
    RunOrder,
    RunPosition,
)


class _FakeQuery:
    def __init__(self, session, model):
        self._session = session
        self._model = model

    def filter(self, *args, **kwargs):  # noqa: ANN002, ANN003 - signature matches SQLAlchemy
        return self

    def delete(self, synchronize_session=False):  # noqa: ANN001 - compatibility
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
        return 0


class _FakeSession:
    def __init__(self):
        self.equity_rows: list[RunDailyEquity] = []
        self.metrics_rows: list[RunMetric] = []
        self.order_rows: list[RunOrder] = []
        self.fill_rows: list[RunFill] = []
        self.position_rows: list[RunPosition] = []
        self.financing_rows: list[RunFinancing] = []

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

    def add(self, obj):
        if isinstance(obj, RunMetric):
            self.metrics_rows.append(obj)

    def commit(self):
        return None

    def refresh(self, obj):
        return None


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
    con.execute("INSERT INTO trading_calendars VALUES ('us', 'US');")
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
    current = start
    missing = missing or {}
    while current <= end:
        is_weekday = current.weekday() < 5
        cal_rows.append(("us", current.isoformat(), is_weekday))
        if is_weekday:
            for idx, symbol in enumerate(symbols):
                if current in missing.get(symbol, set()):
                    continue
                price = 100.0 + idx * 10.0 + (current - start).days * (1.0 + idx * 0.1)
                price_rows.append(
                    (
                        current.isoformat(),
                        symbol,
                        "US_EQUITY",
                        "USD",
                        price,
                        price,
                        price,
                        price,
                        1000.0,
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


def test_buy_and_hold_persists_equity_and_metrics(tmp_path, monkeypatch):
    duckdb_path = tmp_path / "simutrader.duckdb"
    start = date(2024, 1, 2)
    end = date(2024, 3, 1)
    symbols = ["TESTA", "TESTB"]

    _seed_duckdb(str(duckdb_path), symbols, start, end)
    monkeypatch.setenv("DUCKDB_PATH", str(duckdb_path))

    db = _FakeSession()
    run = BacktestRun(
        run_id=uuid4(),
        status="QUEUED",
        config_snapshot={
            "universe": {
                "instruments": [
                    {"symbol": symbols[0], "asset_class": "US_EQUITY", "amount": 4000.0},
                    {"symbol": symbols[1], "asset_class": "US_EQUITY", "amount": 6000.0},
                ]
            },
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "initial_cash": 10000.0,
        },
        data_snapshot_id="test_snapshot",
        seed=42,
    )

    execute_run(db, run)

    assert run.status == "SUCCEEDED"
    assert db.equity_rows, "Expected equity rows to be persisted"
    assert db.equity_rows[0].equity_base != db.equity_rows[-1].equity_base
    assert db.metrics_rows, "Expected metrics row to be persisted"
    assert db.order_rows, "Expected order rows to be persisted"
    assert db.fill_rows, "Expected fill rows to be persisted"
    assert db.position_rows, "Expected position rows to be persisted"
    assert db.financing_rows, "Expected financing rows to be persisted"
    assert len(db.order_rows) == len(symbols)
    assert len(db.fill_rows) == len(symbols)
    metric_meta = db.metrics_rows[0].meta
    assert metric_meta["requested_start_date"] == start.isoformat()
    assert metric_meta["requested_end_date"] == end.isoformat()
    assert metric_meta["effective_start_date"] == start.isoformat()
    assert metric_meta["effective_end_date"] == end.isoformat()
    assert metric_meta["date_shift_warnings"] == []


def test_buy_and_hold_commission_and_slippage(tmp_path, monkeypatch):
    duckdb_path = tmp_path / "simutrader.duckdb"
    start = date(2024, 1, 2)
    end = date(2024, 1, 3)
    symbols = ["FEE"]

    _seed_duckdb(str(duckdb_path), symbols, start, end)
    monkeypatch.setenv("DUCKDB_PATH", str(duckdb_path))

    db = _FakeSession()
    run = BacktestRun(
        run_id=uuid4(),
        status="QUEUED",
        config_snapshot={
            "universe": {
                "instruments": [
                    {"symbol": symbols[0], "asset_class": "US_EQUITY", "amount": 1000.0},
                ]
            },
            "backtest": {
                "start_date": start.isoformat(),
                "end_date": end.isoformat(),
                "initial_cash": 1010.0,
            },
            "commission": {"model": "BPS", "bps": 10, "min_fee_native": 0.0},
            "slippage": {"model": "BPS", "bps": 50},
            "fill_price_policy": "CLOSE",
        },
        data_snapshot_id="test_snapshot",
        seed=42,
    )

    execute_run(db, run)

    assert run.status == "SUCCEEDED"
    assert db.fill_rows, "Expected fill rows to be persisted"
    fill = db.fill_rows[0]
    assert fill.price_native == pytest.approx(100.5, rel=1e-6)
    assert fill.slippage_native == pytest.approx(5.0, rel=1e-6)
    assert fill.commission_native == pytest.approx(1.005, rel=1e-6)
    assert db.equity_rows, "Expected equity rows to be persisted"
    fees = db.equity_rows[-1].fees_cum_by_currency.get("USD")
    assert fees == pytest.approx(6.005, rel=1e-6)
    metric = db.metrics_rows[0]
    assert metric.gross_return is not None
    assert metric.net_return is not None
    assert metric.fee_drag is not None
    assert metric.gross_return > metric.net_return


def test_buy_and_hold_equal_weight_default(tmp_path, monkeypatch):
    duckdb_path = tmp_path / "simutrader.duckdb"
    start = date(2024, 1, 2)
    end = date(2024, 2, 1)
    symbols = ["ALPHA", "BETA"]

    _seed_duckdb(str(duckdb_path), symbols, start, end)
    monkeypatch.setenv("DUCKDB_PATH", str(duckdb_path))

    db = _FakeSession()
    run = BacktestRun(
        run_id=uuid4(),
        status="QUEUED",
        config_snapshot={
            "universe": {
                "instruments": [
                    {"symbol": symbols[0], "asset_class": "US_EQUITY"},
                    {"symbol": symbols[1], "asset_class": "US_EQUITY"},
                ]
            },
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "initial_cash": 10000.0,
        },
        data_snapshot_id="test_snapshot",
        seed=42,
    )

    execute_run(db, run)

    assert run.status == "SUCCEEDED"
    assert db.equity_rows, "Expected equity rows to be persisted"
    # Strategies now keep a 1% cash buffer (99% deployment).
    assert db.equity_rows[-1].cash_base == pytest.approx(100.0, rel=1e-6)


def test_buy_and_hold_missing_bars_carry_forward(tmp_path, monkeypatch):
    duckdb_path = tmp_path / "simutrader.duckdb"
    start = date(2024, 1, 2)
    end = date(2024, 1, 20)
    symbols = ["GAMMA", "DELTA"]

    missing = {
        "DELTA": {
            date(2024, 1, 8),
            date(2024, 1, 12),
        }
    }
    _seed_duckdb(str(duckdb_path), symbols, start, end, missing=missing)
    monkeypatch.setenv("DUCKDB_PATH", str(duckdb_path))

    db = _FakeSession()
    run = BacktestRun(
        run_id=uuid4(),
        status="QUEUED",
        config_snapshot={
            "universe": {
                "instruments": [
                    {"symbol": symbols[0], "asset_class": "US_EQUITY", "amount": 5000.0},
                    {"symbol": symbols[1], "asset_class": "US_EQUITY", "amount": 5000.0},
                ]
            },
            "data_policy": {"missing_bar": "FORWARD_FILL"},
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "initial_cash": 10000.0,
        },
        data_snapshot_id="test_snapshot",
        seed=42,
    )

    execute_run(db, run)

    con = duckdb.connect(str(duckdb_path))
    expected_days = con.execute(
        "select count(*) from global_trading_days where date between ? and ?",
        [start, end],
    ).fetchone()[0]
    con.close()
    assert run.status == "SUCCEEDED"
    assert len(db.equity_rows) == expected_days


def test_buy_and_hold_forward_fill_bootstraps_from_next_available_start_bar(tmp_path, monkeypatch):
    duckdb_path = tmp_path / "simutrader.duckdb"
    start = date(2024, 1, 1)
    end = date(2024, 1, 10)
    symbols = ["AAPL"]

    missing = {"AAPL": {start}}
    _seed_duckdb(str(duckdb_path), symbols, start, end, missing=missing)
    monkeypatch.setenv("DUCKDB_PATH", str(duckdb_path))

    db = _FakeSession()
    run = BacktestRun(
        run_id=uuid4(),
        status="QUEUED",
        config_snapshot={
            "universe": {
                "instruments": [
                    {"symbol": symbols[0], "asset_class": "US_EQUITY", "amount": 10000.0},
                ]
            },
            "data_policy": {"missing_bar": "FORWARD_FILL"},
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "initial_cash": 10000.0,
        },
        data_snapshot_id="test_snapshot",
        seed=42,
    )

    execute_run(db, run)

    assert run.status == "SUCCEEDED"
    assert db.fill_rows, "Expected at least one fill"
    assert db.fill_rows[0].date == start


def test_buy_and_hold_missing_bars_fail_by_default(tmp_path, monkeypatch):
    duckdb_path = tmp_path / "simutrader.duckdb"
    start = date(2024, 1, 2)
    end = date(2024, 1, 20)
    symbols = ["EPSILON", "ZETA"]

    missing = {
        "ZETA": {
            date(2024, 1, 8),
        }
    }
    _seed_duckdb(str(duckdb_path), symbols, start, end, missing=missing)
    monkeypatch.setenv("DUCKDB_PATH", str(duckdb_path))

    db = _FakeSession()
    run = BacktestRun(
        run_id=uuid4(),
        status="QUEUED",
        config_snapshot={
            "universe": {
                "instruments": [
                    {"symbol": symbols[0], "asset_class": "US_EQUITY", "amount": 5000.0},
                    {"symbol": symbols[1], "asset_class": "US_EQUITY", "amount": 5000.0},
                ]
            },
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "initial_cash": 10000.0,
        },
        data_snapshot_id="test_snapshot",
        seed=42,
    )

    execute_run(db, run)

    assert run.status == "FAILED"
    assert run.error and "Missing bar" in run.error


def test_buy_and_hold_weekend_boundary_records_effective_dates(tmp_path, monkeypatch):
    duckdb_path = tmp_path / "simutrader.duckdb"
    calendar_start = date(2024, 1, 1)
    calendar_end = date(2024, 1, 31)
    symbols = ["SHIFT1"]
    start = date(2024, 1, 6)  # Saturday
    end = date(2024, 1, 12)   # Friday

    _seed_duckdb(str(duckdb_path), symbols, calendar_start, calendar_end)
    monkeypatch.setenv("DUCKDB_PATH", str(duckdb_path))

    db = _FakeSession()
    run = BacktestRun(
        run_id=uuid4(),
        status="QUEUED",
        config_snapshot={
            "universe": {
                "instruments": [
                    {"symbol": symbols[0], "asset_class": "US_EQUITY", "amount": 10000.0},
                ]
            },
            "backtest": {
                "start_date": start.isoformat(),
                "end_date": end.isoformat(),
                "initial_cash": 10000.0,
            },
            "data_policy": {"missing_bar": "FORWARD_FILL"},
        },
        data_snapshot_id="test_snapshot",
        seed=42,
    )

    execute_run(db, run)

    assert run.status == "SUCCEEDED"
    assert db.metrics_rows, "Expected metrics row to be persisted"
    meta = db.metrics_rows[0].meta
    assert meta["requested_start_date"] == start.isoformat()
    assert meta["requested_end_date"] == end.isoformat()
    assert meta["effective_start_date"] == date(2024, 1, 8).isoformat()
    assert meta["effective_end_date"] == end.isoformat()
    warnings = meta["date_shift_warnings"]
    assert warnings
    assert "Start date shifted" in warnings[0]


def test_buy_and_hold_no_trading_days_in_range_returns_explicit_error(tmp_path, monkeypatch):
    duckdb_path = tmp_path / "simutrader.duckdb"
    calendar_start = date(2024, 1, 1)
    calendar_end = date(2024, 1, 31)
    symbols = ["WEEKEND_ONLY"]
    start = date(2024, 1, 6)  # Saturday
    end = date(2024, 1, 7)    # Sunday

    _seed_duckdb(str(duckdb_path), symbols, calendar_start, calendar_end)
    monkeypatch.setenv("DUCKDB_PATH", str(duckdb_path))

    db = _FakeSession()
    run = BacktestRun(
        run_id=uuid4(),
        status="QUEUED",
        config_snapshot={
            "universe": {
                "instruments": [
                    {"symbol": symbols[0], "asset_class": "US_EQUITY", "amount": 10000.0},
                ]
            },
            "backtest": {
                "start_date": start.isoformat(),
                "end_date": end.isoformat(),
                "initial_cash": 10000.0,
            },
            "data_policy": {"missing_bar": "FORWARD_FILL"},
        },
        data_snapshot_id="test_snapshot",
        seed=42,
    )

    execute_run(db, run)

    assert run.status == "FAILED"
    assert run.error and run.error.startswith("E_NO_TRADING_DAYS_IN_RANGE:")


def test_fixed_weight_rebalance_daily(tmp_path, monkeypatch):
    duckdb_path = tmp_path / "simutrader.duckdb"
    start = date(2024, 1, 2)
    end = date(2024, 1, 10)
    symbols = ["OMEGA", "SIGMA"]

    _seed_duckdb(str(duckdb_path), symbols, start, end)
    monkeypatch.setenv("DUCKDB_PATH", str(duckdb_path))

    db = _FakeSession()
    run = BacktestRun(
        run_id=uuid4(),
        status="QUEUED",
        config_snapshot={
            "strategy": "FIXED_WEIGHT_REBALANCE",
            "strategy_params": {
                "target_weights": {symbols[0]: 0.6, symbols[1]: 0.4},
                "rebalance_frequency": "DAILY",
                "drift_threshold": 0.0,
            },
            "universe": {
                "instruments": [
                    {"symbol": symbols[0], "asset_class": "US_EQUITY"},
                    {"symbol": symbols[1], "asset_class": "US_EQUITY"},
                ]
            },
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "initial_cash": 10000.0,
        },
        data_snapshot_id="test_snapshot",
        seed=42,
    )

    execute_run(db, run)

    assert run.status == "SUCCEEDED"
    assert db.order_rows, "Expected orders for rebalance"
    assert db.position_rows, "Expected positions to be persisted"

    last_date = max(row.date for row in db.position_rows)
    positions = [row for row in db.position_rows if row.date == last_date]
    equity_row = next(row for row in db.equity_rows if row.date == last_date)
    weights = {
        row.symbol: row.market_value_base / equity_row.equity_base for row in positions
    }
    # Rebalance targets are applied with a 1% cash reserve.
    assert weights[symbols[0]] == pytest.approx(0.6 * 0.99, rel=1e-3)
    assert weights[symbols[1]] == pytest.approx(0.4 * 0.99, rel=1e-3)


def test_dca_weekly_contributions_daily_buys(tmp_path, monkeypatch):
    duckdb_path = tmp_path / "simutrader.duckdb"
    start = date(2024, 1, 2)
    end = date(2024, 1, 10)
    symbols = ["DCA1", "DCA2"]

    _seed_duckdb(str(duckdb_path), symbols, start, end)
    monkeypatch.setenv("DUCKDB_PATH", str(duckdb_path))

    db = _FakeSession()
    run = BacktestRun(
        run_id=uuid4(),
        status="QUEUED",
        config_snapshot={
            "strategy": "DCA",
            "strategy_params": {"buy_frequency": "DAILY", "weighting": "EQUAL"},
            "backtest": {
                "start_date": start.isoformat(),
                "end_date": end.isoformat(),
                "initial_cash": 100.0,
                "contributions": {"enabled": True, "amount": 1000.0, "frequency": "WEEKLY"},
            },
            "universe": {
                "instruments": [
                    {"symbol": symbols[0], "asset_class": "US_EQUITY"},
                    {"symbol": symbols[1], "asset_class": "US_EQUITY"},
                ]
            },
        },
        data_snapshot_id="test_snapshot",
        seed=42,
    )

    execute_run(db, run)

    assert run.status == "SUCCEEDED"
    assert db.order_rows, "Expected DCA buy orders"
    con = duckdb.connect(str(duckdb_path))
    trading_days = con.execute(
        "select count(*) from global_trading_days where date between ? and ?",
        [start, end],
    ).fetchone()[0]
    con.close()
    expected_buys = trading_days * len(symbols)
    assert len(db.order_rows) == expected_buys
    assert all(order.side == "BUY" for order in db.order_rows)


def test_momentum_monthly_top_k(tmp_path, monkeypatch):
    duckdb_path = tmp_path / "simutrader.duckdb"
    start = date(2024, 1, 2)
    end = date(2024, 1, 31)
    symbols = ["MOMO1", "MOMO2"]

    _seed_duckdb(str(duckdb_path), symbols, start, end)
    monkeypatch.setenv("DUCKDB_PATH", str(duckdb_path))

    db = _FakeSession()
    run = BacktestRun(
        run_id=uuid4(),
        status="QUEUED",
        config_snapshot={
            "strategy": "MOMENTUM",
            "strategy_params": {
                "lookback_days": 3,
                "skip_days": 1,
                "top_k": 1,
                "rebalance_frequency": "WEEKLY",
                "weighting": "EQUAL",
            },
            "universe": {
                "instruments": [
                    {"symbol": symbols[0], "asset_class": "US_EQUITY"},
                    {"symbol": symbols[1], "asset_class": "US_EQUITY"},
                ]
            },
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "initial_cash": 10000.0,
        },
        data_snapshot_id="test_snapshot",
        seed=42,
    )

    execute_run(db, run)

    assert run.status == "SUCCEEDED"
    assert db.order_rows, "Expected momentum rebalance orders"

    last_date = max(row.date for row in db.position_rows)
    positions = [row for row in db.position_rows if row.date == last_date]
    equity_row = next(row for row in db.equity_rows if row.date == last_date)
    weights = {
        row.symbol: row.market_value_base / equity_row.equity_base for row in positions
    }

    # Momentum allocations now deploy 99% of equity into winners.
    assert weights[symbols[1]] == pytest.approx(0.99, rel=1e-3)
    assert weights.get(symbols[0], 0.0) == pytest.approx(0.0, abs=1e-6)


def test_mean_reversion_entry_and_hold(tmp_path, monkeypatch):
    duckdb_path = tmp_path / "simutrader.duckdb"
    start = date(2024, 1, 2)
    end = date(2024, 1, 31)
    symbols = ["MEAN1"]

    _seed_duckdb(str(duckdb_path), symbols, start, end)
    con = duckdb.connect(str(duckdb_path))
    # Inject a sharp dip to create negative z-scores for entry.
    con.execute(
        """
        UPDATE prices
        SET close = close * 0.8,
            open = open * 0.8,
            high = high * 0.8,
            low = low * 0.8
        WHERE symbol = ? AND date IN (?, ?)
        """,
        [symbols[0], date(2024, 1, 10).isoformat(), date(2024, 1, 11).isoformat()],
    )
    con.close()
    monkeypatch.setenv("DUCKDB_PATH", str(duckdb_path))

    db = _FakeSession()
    run = BacktestRun(
        run_id=uuid4(),
        status="QUEUED",
        config_snapshot={
            "strategy": "MEAN_REVERSION",
            "strategy_params": {
                "lookback_days": 5,
                "entry_threshold": 0.5,
                "hold_days": 3,
                "rebalance_frequency": "DAILY",
            },
            "universe": {
                "instruments": [
                    {"symbol": symbols[0], "asset_class": "US_EQUITY"},
                ]
            },
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "initial_cash": 10000.0,
        },
        data_snapshot_id="test_snapshot",
        seed=42,
    )

    execute_run(db, run)

    assert run.status == "SUCCEEDED"
    assert db.position_rows, "Expected positions to be persisted"
