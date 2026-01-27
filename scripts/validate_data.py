"""Validate processed OHLCV parquet data."""

from __future__ import annotations

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


def main() -> int:
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/processed/prices")
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

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
