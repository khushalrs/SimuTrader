"""Validate processed OHLCV parquet data and calendar coverage."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys
import pandas as pd


def _load_parquet_dataset(root: Path) -> pd.DataFrame:
    try:
        import pyarrow.dataset as ds
    except Exception as exc:  # pragma: no cover - dependency error
        raise SystemExit("pyarrow is required to read parquet datasets") from exc

    dataset = ds.dataset(root, format="parquet", partitioning="hive")
    table = dataset.to_table(columns=[
        "date",
        "symbol",
        "asset_class",
        "open",
        "high",
        "low",
        "close",
    ])
    return table.to_pandas()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate processed OHLCV parquet data")
    parser.add_argument("--root", default="data/processed/prices")
    parser.add_argument("--duckdb", default=os.getenv("DUCKDB_PATH", "data/processed/simutrader.duckdb"))
    parser.add_argument("--strict", action="store_true", default=False)
    parser.add_argument("--skip-calendar-coverage", action="store_true", default=False)
    return parser.parse_args()


def check_duplicates(df: pd.DataFrame) -> list[tuple[str, str, str, int]]:
    dup = df.duplicated(subset=["symbol", "asset_class", "date"], keep=False)
    if not dup.any():
        return []
    counts = (
        df.loc[dup]
        .groupby(["symbol", "asset_class", "date"], dropna=False)
        .size()
        .reset_index(name="count")
    )
    return [tuple(row) for row in counts.itertuples(index=False, name=None)]


def check_null_ohlc(df: pd.DataFrame) -> pd.DataFrame:
    cols = ["open", "high", "low", "close"]
    return df[df[cols].isna().any(axis=1)][["symbol", "asset_class", "date"] + cols]


def check_date_ranges(df: pd.DataFrame) -> pd.DataFrame:
    return (
        df.groupby("asset_class")["date"]
        .agg(["min", "max", "count"])
        .reset_index()
    )


def check_calendar_coverage(duckdb_path: str) -> tuple[list[tuple], list[tuple]]:
    try:
        import duckdb
    except Exception as exc:  # pragma: no cover - dependency error
        raise SystemExit("duckdb is required for calendar coverage checks") from exc

    con = duckdb.connect(duckdb_path)
    try:
        con.execute("select 1 from calendar_pivot limit 1")
    except Exception as exc:
        con.close()
        raise SystemExit("calendar_pivot view missing; run scripts/create_calendar_views.py") from exc

    missing = con.execute(
        """
        WITH symbol_ranges AS (
            SELECT symbol,
                   asset_class,
                   min(date) AS min_date,
                   max(date) AS max_date
            FROM prices
            GROUP BY 1,2
        ),
        expected AS (
            SELECT r.symbol,
                   r.asset_class,
                   c.date,
                   CASE
                       WHEN r.asset_class = 'US_EQUITY' THEN c.is_us_trading
                       WHEN r.asset_class = 'IN_EQUITY' THEN c.is_in_trading
                       WHEN r.asset_class = 'FX' THEN c.is_fx_trading
                       ELSE FALSE
                   END AS should_have_bar
            FROM symbol_ranges r
            JOIN calendar_pivot c
              ON c.date BETWEEN r.min_date AND r.max_date
        ),
        bars AS (
            SELECT symbol, asset_class, date, count(*) AS bars
            FROM prices
            GROUP BY 1,2,3
        )
        SELECT e.symbol, e.date
        FROM expected e
        LEFT JOIN bars b
        USING (symbol, asset_class, date)
        WHERE e.should_have_bar AND COALESCE(b.bars, 0) = 0
        ORDER BY e.symbol, e.date
        """
    ).fetchall()

    duplicates = con.execute(
        """
        SELECT symbol, asset_class, date, count(*) AS bars
        FROM prices
        GROUP BY 1,2,3
        HAVING count(*) > 1
        ORDER BY bars DESC
        """
    ).fetchall()

    con.close()
    return missing, duplicates


def main() -> int:
    args = _parse_args()
    root = Path(args.root)
    if not root.exists():
        print(f"Missing data root: {root}")
        return 1

    df = _load_parquet_dataset(root)
    if df.empty:
        print("No rows found in dataset.")
        return 1

    dup_rows = check_duplicates(df)
    if dup_rows:
        print("Duplicates found (symbol, asset_class, date, count):")
        for row in dup_rows[:20]:
            print("  ", row)
        if len(dup_rows) > 20:
            print(f"  ... {len(dup_rows) - 20} more")
    else:
        print("No duplicate (symbol, asset_class, date) rows.")

    null_rows = check_null_ohlc(df)
    if not null_rows.empty:
        print("Rows with null OHLC found:")
        print(null_rows.head(20).to_string(index=False))
        if len(null_rows) > 20:
            print(f"... {len(null_rows) - 20} more")
    else:
        print("No nulls in open/high/low/close.")

    ranges = check_date_ranges(df)
    print("Date ranges by asset_class:")
    print(ranges.to_string(index=False))

    defects = bool(dup_rows or not null_rows.empty)

    if not args.skip_calendar_coverage:
        missing, dup_bars = check_calendar_coverage(args.duckdb)
        if missing:
            print("Missing bars on open market days (symbol, date):")
            for row in missing[:50]:
                print("  ", row)
            if len(missing) > 50:
                print(f"  ... {len(missing) - 50} more")
        if dup_bars:
            print("Duplicate bars (symbol, asset_class, date, count):")
            for row in dup_bars[:20]:
                print("  ", row)
            if len(dup_bars) > 20:
                print(f"  ... {len(dup_bars) - 20} more")
        defects = defects or bool(missing or dup_bars)

    if defects and args.strict:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
