from __future__ import annotations

from datetime import date, timedelta
from uuid import uuid4

import duckdb

from app.backtest.executor import execute_run
from app.models.backtests import BacktestRun, RunDailyEquity, RunMetric


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
        return 0


class _FakeSession:
    def __init__(self):
        self.equity_rows: list[RunDailyEquity] = []
        self.metrics_rows: list[RunMetric] = []

    def query(self, model):
        return _FakeQuery(self, model)

    def bulk_save_objects(self, records):
        self.equity_rows.extend(records)

    def add(self, obj):
        if isinstance(obj, RunMetric):
            self.metrics_rows.append(obj)

    def commit(self):
        return None

    def refresh(self, obj):
        return None


def _seed_duckdb(path: str, symbol: str, start: date, end: date) -> None:
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
    price = 100.0
    while current <= end:
        is_weekday = current.weekday() < 5
        cal_rows.append(("us", current.isoformat(), is_weekday))
        if is_weekday:
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
            price += 1.0
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
    symbol = "TEST"

    _seed_duckdb(str(duckdb_path), symbol, start, end)
    monkeypatch.setenv("DUCKDB_PATH", str(duckdb_path))

    db = _FakeSession()
    run = BacktestRun(
        run_id=uuid4(),
        status="QUEUED",
        config_snapshot={
            "symbol": symbol,
            "asset_class": "US_EQUITY",
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
    assert db.metrics_rows[0].gross_return is not None
