"""Seed Postgres metadata tables from processed Parquet files."""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path

try:
    import duckdb
except ImportError as exc:
    raise SystemExit("duckdb is required: pip install duckdb") from exc

try:
    import psycopg
    from psycopg.types.json import Json
except ImportError as exc:
    raise SystemExit("psycopg is required: pip install psycopg[binary]") from exc


def _q(path: Path) -> str:
    return str(path).replace("'", "''")


def _conninfo() -> str:
    raw = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://simu:simu_password_change_me@localhost:5432/simutrader",
    )
    if raw.startswith("postgresql+psycopg://"):
        return raw.replace("postgresql+psycopg://", "postgresql://", 1)
    return raw


def _json_value(value):
    if value is None:
        return Json({})
    if isinstance(value, str):
        try:
            return Json(json.loads(value))
        except json.JSONDecodeError:
            return Json({"raw": value})
    return Json(value)


def _coerce_uuid(value):
    if value is None:
        return uuid.uuid4()
    if isinstance(value, uuid.UUID):
        return value
    text = str(value)
    try:
        if len(text) == 32:
            return uuid.UUID(hex=text)
        return uuid.UUID(text)
    except ValueError:
        return uuid.uuid5(uuid.NAMESPACE_DNS, text)


def _fetch_rows(con, parquet_path: Path):
    cur = con.execute(f"SELECT * FROM read_parquet('{_q(parquet_path)}')")
    cols = [desc[0] for desc in cur.description]
    rows = cur.fetchall()
    return cols, rows


def seed_assets(pg, duckdb_con, parquet_dir: Path) -> int:
    path = parquet_dir / "assets.parquet"
    if not path.exists():
        print(f"Skipping assets: missing {path}")
        return 0

    cols, rows = _fetch_rows(duckdb_con, path)
    col_set = set(cols)
    required = {"symbol", "asset_class", "currency", "data_source"}
    missing = required - col_set
    if missing:
        raise SystemExit(f"assets.parquet missing columns: {sorted(missing)}")

    records = []
    for row in rows:
        data = dict(zip(cols, row))
        records.append(
            {
                "asset_id": _coerce_uuid(data.get("asset_id")),
                "symbol": data.get("symbol"),
                "name": data.get("name"),
                "asset_class": data.get("asset_class"),
                "currency": data.get("currency"),
                "exchange": data.get("exchange"),
                "is_active": bool(data.get("is_active", True)),
                "data_source": data.get("data_source"),
                "meta": _json_value(data.get("meta")),
            }
        )

    sql = """
        INSERT INTO assets (
            asset_id, symbol, name, asset_class, currency, exchange, is_active, data_source, meta
        )
        VALUES (
            %(asset_id)s, %(symbol)s, %(name)s, %(asset_class)s, %(currency)s,
            %(exchange)s, %(is_active)s, %(data_source)s, %(meta)s
        )
        ON CONFLICT (symbol) DO UPDATE SET
            name = EXCLUDED.name,
            asset_class = EXCLUDED.asset_class,
            currency = EXCLUDED.currency,
            exchange = EXCLUDED.exchange,
            is_active = EXCLUDED.is_active,
            data_source = EXCLUDED.data_source,
            meta = EXCLUDED.meta
    """

    with pg.cursor() as cur:
        cur.executemany(sql, records)
    return len(records)


def seed_trading_calendars(pg, duckdb_con, parquet_dir: Path) -> int:
    path = parquet_dir / "trading_calendars.parquet"
    if not path.exists():
        print(f"Skipping trading_calendars: missing {path}")
        return 0

    cols, rows = _fetch_rows(duckdb_con, path)
    col_set = set(cols)
    required = {"calendar_id", "name", "timezone"}
    missing = required - col_set
    if missing:
        raise SystemExit(f"trading_calendars.parquet missing columns: {sorted(missing)}")

    records = []
    for row in rows:
        data = dict(zip(cols, row))
        records.append(
            {
                "calendar_id": _coerce_uuid(data.get("calendar_id")),
                "name": data.get("name"),
                "timezone": data.get("timezone"),
                "meta": _json_value(data.get("meta")),
            }
        )

    sql = """
        INSERT INTO trading_calendars (calendar_id, name, timezone, meta)
        VALUES (%(calendar_id)s, %(name)s, %(timezone)s, %(meta)s)
        ON CONFLICT (name) DO UPDATE SET
            timezone = EXCLUDED.timezone,
            meta = EXCLUDED.meta
    """

    with pg.cursor() as cur:
        cur.executemany(sql, records)
    return len(records)


def seed_calendar_days(pg, duckdb_con, parquet_dir: Path) -> int:
    path = parquet_dir / "calendar_days.parquet"
    if not path.exists():
        print(f"Skipping calendar_days: missing {path}")
        return 0

    cols, rows = _fetch_rows(duckdb_con, path)
    col_set = set(cols)
    required = {"calendar_id", "date", "is_trading_day"}
    missing = required - col_set
    if missing:
        raise SystemExit(f"calendar_days.parquet missing columns: {sorted(missing)}")

    records = []
    for row in rows:
        data = dict(zip(cols, row))
        records.append(
            {
                "calendar_id": _coerce_uuid(data.get("calendar_id")),
                "date": data.get("date"),
                "is_trading_day": bool(data.get("is_trading_day")),
            }
        )

    sql = """
        INSERT INTO calendar_days (calendar_id, date, is_trading_day)
        VALUES (%(calendar_id)s, %(date)s, %(is_trading_day)s)
        ON CONFLICT (calendar_id, date) DO UPDATE SET
            is_trading_day = EXCLUDED.is_trading_day
    """

    with pg.cursor() as cur:
        cur.executemany(sql, records)
    return len(records)


def main() -> int:
    data_dir = Path(os.getenv("DATA_DIR", "./data"))
    parquet_dir = Path(os.getenv("PARQUET_DIR", data_dir / "processed"))
    duckdb_path = Path(
        os.getenv("DUCKDB_PATH", parquet_dir / "simutrader.duckdb")
    )

    if not parquet_dir.exists():
        raise SystemExit(f"Missing parquet directory: {parquet_dir}")

    duckdb_con = duckdb.connect(str(duckdb_path))
    pg = psycopg.connect(_conninfo())

    try:
        assets_count = seed_assets(pg, duckdb_con, parquet_dir)
        calendars_count = seed_trading_calendars(pg, duckdb_con, parquet_dir)
        days_count = seed_calendar_days(pg, duckdb_con, parquet_dir)
        pg.commit()
    finally:
        pg.close()
        duckdb_con.close()

    print(
        f"Seeded assets={assets_count}, trading_calendars={calendars_count}, calendar_days={days_count}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
