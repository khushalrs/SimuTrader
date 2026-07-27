#!/usr/bin/env python3
"""Safely rebuild the shared DuckDB file from processed parquet data.

Builds a new DuckDB file offline, verifies required relations, and leaves the
caller to atomically swap it into place.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import duckdb


def _q(value: str) -> str:
    return value.replace("'", "''")


def _iter_symbol_globs(processed_root: Path) -> list[str]:
    price_root = processed_root / "prices"
    globs: list[str] = []
    for asset_dir in sorted(price_root.glob("asset_class=*")):
        if not asset_dir.is_dir():
            continue
        for symbol_dir in sorted(asset_dir.glob("symbol=*")):
            if not symbol_dir.is_dir():
                continue
            globs.append(str(symbol_dir / "year=*" / "ohlcv.parquet"))
    return globs


def _materialize_prices(con: duckdb.DuckDBPyConnection, processed_root: Path) -> None:
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
            data_source VARCHAR,
            base_ccy VARCHAR,
            quote_ccy VARCHAR,
            year BIGINT
        )
        """
    )
    symbol_globs = _iter_symbol_globs(processed_root)
    if not symbol_globs:
        raise RuntimeError(f"No parquet symbol partitions found under {processed_root / 'prices'}")
    for idx, symbol_glob in enumerate(symbol_globs, start=1):
        con.execute(
            f"""
            INSERT INTO prices BY NAME
            SELECT *
            FROM read_parquet(
                '{_q(symbol_glob)}',
                hive_partitioning=1,
                union_by_name=1
            )
            """
        )
        if idx % 500 == 0:
            print(f"loaded_symbol_partitions={idx}")
    con.execute("ANALYZE prices")


def rebuild(processed_root: Path, output_path: Path) -> None:
    assets_path = processed_root / "assets.parquet"
    trading_calendars_path = processed_root / "trading_calendars.parquet"
    calendar_days_path = processed_root / "calendar_days.parquet"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        output_path.unlink()

    con = duckdb.connect(str(output_path))
    try:
        _materialize_prices(con, processed_root)

        if assets_path.exists():
            con.execute(
                f"""
                CREATE OR REPLACE VIEW assets AS
                SELECT *
                FROM read_parquet('{_q(str(assets_path))}')
                """
            )
        if trading_calendars_path.exists():
            con.execute(
                f"""
                CREATE OR REPLACE VIEW trading_calendars AS
                SELECT *
                FROM read_parquet('{_q(str(trading_calendars_path))}')
                """
            )
        if calendar_days_path.exists():
            con.execute(
                f"""
                CREATE OR REPLACE VIEW calendar_days AS
                SELECT *
                FROM read_parquet('{_q(str(calendar_days_path))}')
                """
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
            GROUP BY 1
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
            FROM calendar_pivot
            """
        )
        con.execute(
            """
            CREATE OR REPLACE VIEW global_trading_days AS
            SELECT date
            FROM global_calendar
            WHERE is_global_trading
            ORDER BY date
            """
        )
        con.execute(
            """
            CREATE OR REPLACE VIEW latest_close AS
            SELECT symbol, asset_class, max(date) AS date, arg_max(close, date) AS close
            FROM prices
            GROUP BY 1,2
            """
        )

        # Verification gates: fail early if the rebuilt DB is incomplete.
        prices_count = con.execute("select count(*) from prices").fetchone()[0]
        con.execute("select symbol, asset_class, date, close from prices limit 1").fetchone()
        con.execute("select count(*) from global_trading_days").fetchone()

        print(f"rebuilt_prices_count={prices_count}")
        print(f"output_path={output_path}")
    finally:
        con.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--processed-root", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    rebuild(Path(args.processed_root).resolve(), Path(args.output).resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
