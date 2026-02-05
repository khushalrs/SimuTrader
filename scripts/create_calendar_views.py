"""Apply DuckDB calendar view SQL migrations."""

from __future__ import annotations

import os
from pathlib import Path

try:
    import duckdb
except ImportError as exc:
    raise SystemExit("duckdb is required: pip install duckdb") from exc


def main() -> int:
    sql_path = Path(__file__).resolve().parent / "duckdb" / "002_calendar_views.sql"
    data_root = Path(os.getenv("DATA_DIR", "./data"))
    base_root = Path(os.getenv("PARQUET_DIR", data_root / "processed"))
    duckdb_path = os.getenv("DUCKDB_PATH", str(base_root / "simutrader.duckdb"))

    if not sql_path.exists():
        raise SystemExit(f"Missing SQL file: {sql_path}")

    con = duckdb.connect(duckdb_path)
    trading_cal_path = base_root / "trading_calendars.parquet"
    calendar_days_path = base_root / "calendar_days.parquet"
    if trading_cal_path.exists():
        con.execute(
            f"""
            CREATE OR REPLACE VIEW trading_calendars AS
            SELECT * FROM read_parquet('{str(trading_cal_path).replace("'", "''")}')
            """
        )
    if calendar_days_path.exists():
        con.execute(
            f"""
            CREATE OR REPLACE VIEW calendar_days AS
            SELECT * FROM read_parquet('{str(calendar_days_path).replace("'", "''")}')
            """
        )
    con.execute(sql_path.read_text())
    con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
