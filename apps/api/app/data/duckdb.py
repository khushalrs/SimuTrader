"""DuckDB connection helper."""

from __future__ import annotations

import os

import duckdb


def get_duckdb_conn():
    data_dir = os.getenv("DATA_DIR", "./data")
    duckdb_path = os.getenv(
        "DUCKDB_PATH", os.path.join(data_dir, "processed", "simutrader.duckdb")
    )
    read_only_env = os.getenv("DUCKDB_READ_ONLY", "true").strip().lower()
    read_only = read_only_env in {"1", "true", "yes", "on"}
    return duckdb.connect(duckdb_path, read_only=read_only)
