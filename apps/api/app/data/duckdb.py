"""DuckDB connection helper."""

from __future__ import annotations

import os

import duckdb


def get_duckdb_conn():
    duckdb_path = os.getenv("DUCKDB_PATH", "./data/processed/simutrader.duckdb")
    return duckdb.connect(duckdb_path)
