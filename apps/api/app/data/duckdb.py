"""DuckDB connection helper."""

from __future__ import annotations

import os

import duckdb


def get_duckdb_conn():
    data_dir = os.getenv("DATA_DIR", "./data")
    duckdb_path = os.getenv(
        "DUCKDB_PATH", os.path.join(data_dir, "processed", "simutrader.duckdb")
    )
    return duckdb.connect(duckdb_path)
