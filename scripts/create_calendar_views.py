"""Apply DuckDB calendar view SQL migrations."""

from __future__ import annotations

import os
from pathlib import Path

try:
    import duckdb
except ImportError as exc:
    raise SystemExit("duckdb is required: pip install duckdb") from exc


def main() -> int:
    duckdb_path = os.getenv("DUCKDB_PATH", "./data/processed/simutrader.duckdb")
    sql_path = Path(__file__).resolve().parent / "duckdb" / "002_calendar_views.sql"

    if not sql_path.exists():
        raise SystemExit(f"Missing SQL file: {sql_path}")

    con = duckdb.connect(duckdb_path)
    con.execute(sql_path.read_text())
    con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
