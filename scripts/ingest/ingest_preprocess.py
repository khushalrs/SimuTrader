#!/usr/bin/env python3
"""SimuTrader snapshot ingestion (raw -> processed Parquet + DuckDB)

What this does
--------------
- Reads your 3 raw sources:
  1) FX Excel (.xls): wide table where each currency column is "<CCY per 1 USD>".
     USD column (if present) is 1.
  2) US equities: many *.us.txt files with rows:
     <TICKER>,<PER>,<DATE>,<TIME>,<OPEN>,<HIGH>,<LOW>,<CLOSE>,<VOL>,<OPENINT>
  3) India equities: BSE Yahoo CSV dumps: SYMBOL.BO__Company_Name.csv

- Normalizes everything into one daily OHLCV schema:
    date, symbol, asset_class, currency, open, high, low, close, volume
  plus helpful metadata columns: exchange, data_source, base_ccy, quote_ccy (FX).

- Writes partitioned Parquet:
    processed/prices/asset_class=.../symbol=.../year=.../ohlcv.parquet

- Writes assets metadata:
    processed/assets.parquet

- Writes simple calendars (weekday-based):
    processed/trading_calendars.parquet
    processed/calendar_days.parquet

- Creates a DuckDB file with a materialized prices table plus views for
  lighter metadata tables:
    processed/simutrader.duckdb

Install
-------
  pip install pandas numpy duckdb pyarrow tqdm
  pip install xlrd>=2.0.1 openpyxl   # for reading .xls/.xlsx

Run
---
  python ingest_snapshot.py \
    --processed-root /path/to/data/processed \
    --us-root "/path/to/data/raw/us" \
    --bse-root "/path/to/data/raw/bse_yahoo_download" \
    --fx-xls "/path/to/data/raw/fx.xls"

Quick test
----------
  python -c "import duckdb; con=duckdb.connect('/path/to/data/processed/simutrader.duckdb'); print(con.execute('select asset_class,count(*) from prices group by 1').fetchall())"

Notes
-----
- This is snapshot-oriented and overwrites (asset_class, symbol, year) partitions.
- Calendars are deterministic weekday calendars (Mon-Fri). Add holidays later if needed.
"""

from __future__ import annotations

import argparse
import os
import re
import json
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Tuple

import numpy as np
import pandas as pd
from tqdm import tqdm


# -----------------------------
# Config
# -----------------------------


@dataclass(frozen=True)
class IngestConfig:
    processed_root: Path
    us_root: Optional[Path] = None
    bse_root: Optional[Path] = None
    fx_xls: Optional[Path] = None

    strip_us_suffix: bool = True   # AACB.US -> AACB
    strip_bo_suffix: bool = True   # 3MINDIA.BO -> 3MINDIA

    prices_dirname: str = "prices"


# -----------------------------
# Helpers
# -----------------------------


def _ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def _safe_float(x) -> float:
    try:
        if pd.isna(x):
            return np.nan
        if isinstance(x, str):
            s = x.strip()
            if s == "" or s.upper() in {"NA", "N/A", "NULL", "-", "ND"}:
                return np.nan
            return float(s)
        return float(x)
    except Exception:
        return np.nan


def canonical_symbol_us(sym: str, strip_suffix: bool = True) -> str:
    s = str(sym).strip().upper()
    if strip_suffix and s.endswith(".US"):
        s = s[:-3]
    return s


def canonical_symbol_in(sym: str, strip_bo: bool = True) -> str:
    s = str(sym).strip().upper()
    if strip_bo and s.endswith(".BO"):
        s = s[:-3]
    return s


def _normalize_ohlcv(
    df: pd.DataFrame,
    *,
    symbol: str,
    asset_class: str,
    currency: str,
    exchange: str,
    data_source: str,
    base_ccy: Optional[str] = None,
    quote_ccy: Optional[str] = None,
) -> pd.DataFrame:
    """Return normalized dataframe with the common schema."""

    out = pd.DataFrame(
        {
            "date": pd.to_datetime(df["date"], errors="coerce").dt.date,
            "symbol": symbol,
            "asset_class": asset_class,
            "currency": currency,
            "open": pd.to_numeric(df["open"], errors="coerce"),
            "high": pd.to_numeric(df["high"], errors="coerce"),
            "low": pd.to_numeric(df["low"], errors="coerce"),
            "close": pd.to_numeric(df["close"], errors="coerce"),
            "volume": pd.to_numeric(df.get("volume", np.nan), errors="coerce"),
            "exchange": exchange,
            "data_source": data_source,
        }
    )

    if base_ccy is not None:
        out["base_ccy"] = base_ccy
    if quote_ccy is not None:
        out["quote_ccy"] = quote_ccy

    out = out.dropna(subset=["date", "open", "high", "low", "close"], how="any")
    out = out.sort_values("date")
    out = out.drop_duplicates(subset=["date"], keep="last")
    return out


def _write_symbol_year_partitions(df: pd.DataFrame, out_prices_root: Path) -> None:
    """Write 1 Parquet file per (asset_class, symbol, year). Overwrites deterministically."""

    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except Exception as e:
        raise RuntimeError("Parquet writing requires pyarrow. Install: pip install pyarrow") from e

    df = df.copy()
    df["year"] = pd.to_datetime(df["date"]).dt.year.astype(int)

    required_cols = [
        "date",
        "symbol",
        "asset_class",
        "currency",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "exchange",
        "data_source",
    ]
    optional_cols = [c for c in ["base_ccy", "quote_ccy"] if c in df.columns]

    for (asset_class, symbol, year), g in df.groupby(["asset_class", "symbol", "year"], sort=False):
        out_dir = out_prices_root / f"asset_class={asset_class}" / f"symbol={symbol}" / f"year={year}"
        _ensure_dir(out_dir)
        out_file = out_dir / "ohlcv.parquet"

        g = g[required_cols + optional_cols].sort_values("date")
        table = pa.Table.from_pandas(g, preserve_index=False)
        pq.write_table(table, out_file)


# -----------------------------
# US ingest (*.us.txt)
# -----------------------------


def _infer_us_exchange_from_path(p: Path) -> str:
    s = str(p).lower()
    if "nasdaq" in s:
        return "NASDAQ"
    if "nyse" in s:
        return "NYSE"
    return "US"


def iter_us_txt_files(us_root: Path) -> Iterator[Path]:
    for p in us_root.rglob("*.txt"):
        if p.is_file() and p.name.lower().endswith(".us.txt"):
            yield p


def load_us_txt(path: Path, strip_us_suffix: bool = True) -> Tuple[pd.DataFrame, Dict]:
    # Detect header line quickly
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        first = f.readline().strip()

    has_header = "TICKER" in first.upper()

    df = pd.read_csv(
        path,
        sep=",",
        engine="python",
        dtype=str,
        header=0 if has_header else None,
        on_bad_lines="skip",
    )

    if not has_header:
        df.columns = [
            "TICKER",
            "PER",
            "DATE",
            "TIME",
            "OPEN",
            "HIGH",
            "LOW",
            "CLOSE",
            "VOL",
            "OPENINT",
        ][: len(df.columns)]

    df.columns = [re.sub(r"[<>]", "", c).strip().upper() for c in df.columns]

    needed = {"TICKER", "PER", "DATE", "OPEN", "HIGH", "LOW", "CLOSE", "VOL"}
    missing = needed - set(df.columns)
    if missing:
        raise ValueError(f"{path.name}: missing columns: {missing}")

    df = df[df["PER"].astype(str).str.upper().eq("D")]
    if df.empty:
        raise ValueError(f"{path.name}: no daily rows")

    raw_sym = df["TICKER"].iloc[0]
    symbol = canonical_symbol_us(raw_sym, strip_suffix=strip_us_suffix)

    out = pd.DataFrame(
        {
            "date": pd.to_datetime(df["DATE"], format="%Y%m%d", errors="coerce"),
            "open": df["OPEN"].map(_safe_float),
            "high": df["HIGH"].map(_safe_float),
            "low": df["LOW"].map(_safe_float),
            "close": df["CLOSE"].map(_safe_float),
            "volume": df["VOL"].map(_safe_float),
        }
    )

    exchange = _infer_us_exchange_from_path(path)

    meta = {
        "symbol": symbol,
        "name": None,
        "asset_class": "US_EQUITY",
        "currency": "USD",
        "exchange": exchange,
        "data_source": "us_txt_snapshot",
        "meta": {"raw_symbol": str(raw_sym), "file": str(path)},
    }

    norm = _normalize_ohlcv(
        out,
        symbol=symbol,
        asset_class="US_EQUITY",
        currency="USD",
        exchange=exchange,
        data_source="us_txt_snapshot",
    )

    return norm, meta


# -----------------------------
# BSE Yahoo CSV ingest
# -----------------------------


def parse_bse_yahoo_filename(path: Path) -> Tuple[str, Optional[str]]:
    # Example: 3MINDIA.BO__3M_India_Limited.csv
    stem = path.stem
    if "__" in stem:
        sym_part, name_part = stem.split("__", 1)
        name = name_part.replace("_", " ").strip() or None
    else:
        sym_part, name = stem, None
    return sym_part.strip().upper(), name


def iter_bse_csv_files(bse_root: Path) -> Iterator[Path]:
    """Yield only BSE OHLCV CSVs with the expected naming pattern.

    Skips helper CSVs like bse_to_yahoo_mapping.csv.
    """
    for p in bse_root.rglob("*.csv"):
        if not p.is_file():
            continue
        stem_u = p.stem.upper()
        if "__" not in stem_u:
            continue
        sym_part = stem_u.split("__", 1)[0]
        if not sym_part.endswith(".BO"):
            continue
        yield p


def load_bse_yahoo_csv(path: Path, strip_bo_suffix: bool = True) -> Tuple[pd.DataFrame, Dict]:
    df = pd.read_csv(path)

    required = {"Date", "Open", "High", "Low", "Close"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"{path.name}: missing columns: {missing}")

    raw_sym, name = parse_bse_yahoo_filename(path)
    symbol = canonical_symbol_in(raw_sym, strip_bo=strip_bo_suffix)

    out = pd.DataFrame(
        {
            "date": pd.to_datetime(df["Date"], errors="coerce"),
            "open": df["Open"],
            "high": df["High"],
            "low": df["Low"],
            "close": df["Close"],
            "volume": df.get("Volume", np.nan),
        }
    )

    meta = {
        "symbol": symbol,
        "name": name,
        "asset_class": "IN_EQUITY",
        "currency": "INR",
        "exchange": "BSE",
        "data_source": "yahoo_bse_csv",
        "meta": {"raw_symbol": raw_sym, "file": str(path)},
    }

    norm = _normalize_ohlcv(
        out,
        symbol=symbol,
        asset_class="IN_EQUITY",
        currency="INR",
        exchange="BSE",
        data_source="yahoo_bse_csv",
    )

    return norm, meta


# -----------------------------
# FX ingest (.xls)
# -----------------------------


_CCY_CODE_RE = re.compile(r"\(([A-Z]{3})\)")
_SS_NS = {"ss": "urn:schemas-microsoft-com:office:spreadsheet"}
_SS_HEADER_ROW_INDEX = 2
_SS_DATE_COL_INDEX = 0


def _extract_ccy_code(col_name: str) -> Optional[str]:
    if col_name is None or (isinstance(col_name, float) and np.isnan(col_name)):
        return None
    s = str(col_name).strip().upper()
    m = _CCY_CODE_RE.search(s)
    if m:
        return m.group(1)
    # fallback: if the header itself is a 3-letter code
    if re.fullmatch(r"[A-Z]{3}", s):
        return s
    return None


def _read_excel_any_engine(path: Path) -> pd.DataFrame:
    # Try default, then xlrd (xls), then openpyxl (xlsx)
    try:
        return pd.read_excel(path, header=None)
    except Exception:
        try:
            return pd.read_excel(path, header=None, engine="xlrd")
        except Exception:
            return pd.read_excel(path, header=None, engine="openpyxl")


def _read_spreadsheetml_table(path: Path, worksheet_name: str | None = None) -> pd.DataFrame:
    """Read Excel 2003 XML Spreadsheet (SpreadsheetML) into a DataFrame."""
    xml_text = Path(path).read_text(encoding="utf-8-sig", errors="ignore")
    root = ET.fromstring(xml_text)

    worksheets = root.findall(".//ss:Worksheet", _SS_NS)
    if not worksheets:
        raise ValueError("No <Worksheet> found. Not a SpreadsheetML file?")

    ws = None
    if worksheet_name:
        for w in worksheets:
            name = w.get(f"{{{_SS_NS['ss']}}}Name")
            if name == worksheet_name:
                ws = w
                break
        if ws is None:
            raise ValueError(f"Worksheet '{worksheet_name}' not found.")
    else:
        ws = worksheets[0]

    table = ws.find(".//ss:Table", _SS_NS)
    if table is None:
        raise ValueError("No <Table> found in worksheet.")

    rows = table.findall("ss:Row", _SS_NS)
    data = []
    max_len = 0

    for r in rows:
        row = []
        col_idx = 1
        for cell in r.findall("ss:Cell", _SS_NS):
            idx = cell.get(f"{{{_SS_NS['ss']}}}Index")
            if idx is not None:
                idx = int(idx)
                while col_idx < idx:
                    row.append(None)
                    col_idx += 1

            d = cell.find("ss:Data", _SS_NS)
            if d is not None:
                text = "".join(d.itertext()).strip()
                row.append(text if text else None)
            else:
                row.append(None)
            col_idx += 1

        max_len = max(max_len, len(row))
        data.append(row)

    data = [r + [None] * (max_len - len(r)) for r in data]
    return pd.DataFrame(data)


def _make_unique_columns(cols: List) -> List[str]:
    seen: Dict[str, int] = {}
    out: List[str] = []
    for i, c in enumerate(cols):
        name = "" if c is None or (isinstance(c, float) and np.isnan(c)) else str(c)
        name = name.strip()
        if name == "":
            name = f"COL_{i}"
        if name in seen:
            seen[name] += 1
            name = f"{name}_{seen[name]}"
        else:
            seen[name] = 0
        out.append(name)
    return out


def load_fx_xls(path: Path) -> Tuple[pd.DataFrame, List[Dict]]:
    try:
        raw = _read_excel_any_engine(path)

        # Find header row: first column equals 'Date'
        first_col = raw.iloc[:, 0].astype(str).str.strip().str.lower()
        header_rows = raw.index[first_col.eq("date")].tolist()
        if not header_rows:
            raise ValueError("Could not find a header row with first column 'Date'.")
        header_idx = header_rows[0]

        header = _make_unique_columns(raw.iloc[header_idx].tolist())
        data = raw.iloc[header_idx + 1 :].copy()
        data.columns = header

        # Normalize date
        data = data.rename(columns={header[0]: "Date"})
        data["Date"] = pd.to_datetime(data["Date"], errors="coerce")
        data = data.dropna(subset=["Date"]).dropna(axis=1, how="all")

        long_rows: List[pd.DataFrame] = []
        assets: List[Dict] = []

        for col in data.columns:
            if col == "Date":
                continue
            ccy = _extract_ccy_code(col)
            if not ccy or ccy == "USD":
                continue

            s = pd.to_numeric(data[col], errors="coerce")
            if s.notna().sum() == 0:
                continue

            symbol = f"USD{ccy}"  # e.g. USDINR

            sub = pd.DataFrame(
                {
                    "date": data["Date"],
                    "open": s,
                    "high": s,
                    "low": s,
                    "close": s,
                    "volume": np.nan,
                }
            )

            norm = _normalize_ohlcv(
                sub,
                symbol=symbol,
                asset_class="FX",
                currency=ccy,  # quote currency
                exchange="FX",
                data_source="fx_xls_snapshot",
                base_ccy="USD",
                quote_ccy=ccy,
            )

            if norm.empty:
                continue

            long_rows.append(norm)
            assets.append(
                {
                    "symbol": symbol,
                    "name": f"USD/{ccy}",
                    "asset_class": "FX",
                    "currency": ccy,
                    "exchange": "FX",
                    "data_source": "fx_xls_snapshot",
                    "meta": {"raw_column": str(col), "file": str(path)},
                }
            )

        if not long_rows:
            raise ValueError("No FX columns produced data. Check header parsing / column names.")

        fx_all = pd.concat(long_rows, ignore_index=True)
        return fx_all, assets
    except Exception:
        # Fallback for SpreadsheetML (.xls saved as XML)
        wide = _read_spreadsheetml_table(path, worksheet_name="EXCHANGE_RATE_REPORT")

        header = wide.iloc[_SS_HEADER_ROW_INDEX, _SS_DATE_COL_INDEX:].tolist()
        data = wide.iloc[_SS_HEADER_ROW_INDEX + 1 :, _SS_DATE_COL_INDEX:].copy()
        data.columns = header

        date_series = data.iloc[:, 0]
        data = data.rename(columns={data.columns[0]: "Date"})
        data["Date"] = pd.to_datetime(date_series, errors="coerce")
        data = data.dropna(subset=["Date"]).dropna(axis=1, how="all")

        long_rows = []
        assets = []

        for col in data.columns:
            if col == "Date":
                continue
            ccy = _extract_ccy_code(col)
            if not ccy or ccy == "USD":
                continue

            s = pd.to_numeric(data[col], errors="coerce")
            if s.notna().sum() == 0:
                continue

            symbol = f"USD{ccy}"
            sub = pd.DataFrame(
                {
                    "date": data["Date"],
                    "open": s,
                    "high": s,
                    "low": s,
                    "close": s,
                    "volume": np.nan,
                }
            )

            norm = _normalize_ohlcv(
                sub,
                symbol=symbol,
                asset_class="FX",
                currency=ccy,
                exchange="FX",
                data_source="fx_spreadsheetml",
                base_ccy="USD",
                quote_ccy=ccy,
            )

            if norm.empty:
                continue

            long_rows.append(norm)
            assets.append(
                {
                    "symbol": symbol,
                    "name": f"USD/{ccy}",
                    "asset_class": "FX",
                    "currency": ccy,
                    "exchange": "FX",
                    "data_source": "fx_spreadsheetml",
                    "meta": {"raw_column": str(col), "file": str(path)},
                }
            )

        if not long_rows:
            raise ValueError("No FX columns parsed. Check headers contain currency codes like '(INR)'.")

        fx_all = pd.concat(long_rows, ignore_index=True)
        return fx_all, assets


# -----------------------------
# Calendars + DuckDB
# -----------------------------


def build_weekday_calendars(min_date: pd.Timestamp, max_date: pd.Timestamp) -> tuple[pd.DataFrame, pd.DataFrame]:
    import hashlib

    dates = pd.date_range(min_date.date(), max_date.date(), freq="D")
    cal = pd.DataFrame({"date": dates.date})
    cal["weekday"] = dates.weekday
    cal["is_weekday"] = cal["weekday"].between(0, 4)

    calendars = []
    days = []
    tz_map = {"US": "America/New_York", "IN": "Asia/Kolkata", "FX": "America/New_York"}
    for cal_name in ["US", "IN", "FX"]:
        calendar_id = hashlib.md5(cal_name.encode()).hexdigest()
        calendars.append(
            {
                "calendar_id": calendar_id,
                "name": cal_name,
                "timezone": tz_map.get(cal_name),
                # Store as JSON string to avoid pyarrow object dtype issues.
                "meta": json.dumps({}),
            }
        )
        tmp = cal.copy()
        tmp["calendar_id"] = calendar_id
        tmp["is_trading_day"] = tmp["is_weekday"]
        days.append(tmp[["calendar_id", "date", "is_trading_day"]])

    return pd.DataFrame(calendars), pd.concat(days, ignore_index=True)


def build_duckdb(processed_root: Path) -> None:
    import duckdb

    db_path = processed_root / "simutrader.duckdb"

    # No prepared parameters in CREATE VIEW in DuckDB; inline string paths.
    def _q(s: str) -> str:
        return s.replace("'", "''")

    prices_glob = str(
        processed_root
        / "prices"
        / "asset_class=*"
        / "symbol=*"
        / "year=*"
        / "ohlcv.parquet"
    )

    con = duckdb.connect(str(db_path))

    # Materialize prices into DuckDB storage so runtime queries do not need to
    # rescan the full partitioned parquet tree on every backtest.
    con.execute("DROP VIEW IF EXISTS prices;")
    con.execute("DROP TABLE IF EXISTS prices;")
    con.execute(
        f"""
        CREATE TABLE prices AS
        SELECT *
        FROM read_parquet('{_q(prices_glob)}', hive_partitioning=1);
        """
    )
    con.execute("ANALYZE prices;")

    assets_path = processed_root / "assets.parquet"
    if assets_path.exists():
        con.execute(
            f"""
            CREATE OR REPLACE VIEW assets AS
            SELECT *
            FROM read_parquet('{_q(str(assets_path))}');
            """
        )

    trading_calendars_path = processed_root / "trading_calendars.parquet"
    if trading_calendars_path.exists():
        con.execute(
            f"""
            CREATE OR REPLACE VIEW trading_calendars AS
            SELECT *
            FROM read_parquet('{_q(str(trading_calendars_path))}');
            """
        )

    calendar_days_path = processed_root / "calendar_days.parquet"
    if calendar_days_path.exists():
        con.execute(
            f"""
            CREATE OR REPLACE VIEW calendar_days AS
            SELECT *
            FROM read_parquet('{_q(str(calendar_days_path))}');
            """
        )

    con.execute(
        """
        CREATE OR REPLACE VIEW latest_close AS
        SELECT symbol, asset_class, max(date) AS date, arg_max(close, date) AS close
        FROM prices
        GROUP BY 1,2;
        """
    )

    con.close()


# -----------------------------
# Main ingest
# -----------------------------


def ingest_snapshot(cfg: IngestConfig) -> None:
    out_prices_root = cfg.processed_root / cfg.prices_dirname
    _ensure_dir(out_prices_root)

    assets: List[Dict] = []

    min_seen: Optional[pd.Timestamp] = None
    max_seen: Optional[pd.Timestamp] = None

    def update_minmax(df: pd.DataFrame) -> None:
        nonlocal min_seen, max_seen
        if df.empty:
            return
        dmin = pd.to_datetime(df["date"]).min()
        dmax = pd.to_datetime(df["date"]).max()
        min_seen = dmin if min_seen is None else min(min_seen, dmin)
        max_seen = dmax if max_seen is None else max(max_seen, dmax)

    # 1) US
    if cfg.us_root and cfg.us_root.exists():
        us_files = list(iter_us_txt_files(cfg.us_root))
        for p in tqdm(us_files, desc="Ingest US .txt", unit="file"):
            try:
                df, meta = load_us_txt(p, strip_us_suffix=cfg.strip_us_suffix)
                _write_symbol_year_partitions(df, out_prices_root)
                assets.append(meta)
                update_minmax(df)
            except Exception as e:
                print(f"[WARN] US skip {p}: {e}")

    # 2) India BSE Yahoo dumps
    if cfg.bse_root and cfg.bse_root.exists():
        bse_files = list(iter_bse_csv_files(cfg.bse_root))
        for p in tqdm(bse_files, desc="Ingest BSE CSV", unit="file"):
            try:
                df, meta = load_bse_yahoo_csv(p, strip_bo_suffix=cfg.strip_bo_suffix)
                _write_symbol_year_partitions(df, out_prices_root)
                assets.append(meta)
                update_minmax(df)
            except Exception as e:
                print(f"[WARN] BSE skip {p}: {e}")

    # 3) FX
    if cfg.fx_xls and cfg.fx_xls.exists():
        try:
            fx_all, fx_assets = load_fx_xls(cfg.fx_xls)
            for sym, g in tqdm(list(fx_all.groupby("symbol")), desc="Write FX", unit="sym"):
                _write_symbol_year_partitions(g, out_prices_root)
                update_minmax(g)
            assets.extend(fx_assets)
        except Exception as e:
            print(f"[WARN] FX skip {cfg.fx_xls}: {e}")

    # Assets table (dedup by symbol)
    if assets:
        assets_df = pd.DataFrame(assets)
        assets_df["name"] = assets_df.groupby("symbol")["name"].transform(lambda s: s.ffill().bfill())
        assets_df = assets_df.drop_duplicates(subset=["symbol"], keep="first")
        assets_df["meta"] = assets_df["meta"].apply(lambda x: x if isinstance(x, dict) else {})

        assets_out = cfg.processed_root / "assets.parquet"
        _ensure_dir(cfg.processed_root)
        try:
            import pyarrow as pa
            import pyarrow.parquet as pq

            pq.write_table(pa.Table.from_pandas(assets_df, preserve_index=False), assets_out)
        except Exception:
            assets_df.to_csv(cfg.processed_root / "assets.csv", index=False)

    # Calendars
    if min_seen is not None and max_seen is not None:
        trading_cal_df, calendar_days_df = build_weekday_calendars(min_seen, max_seen)
        trading_out = cfg.processed_root / "trading_calendars.parquet"
        days_out = cfg.processed_root / "calendar_days.parquet"
        try:
            import pyarrow as pa
            import pyarrow.parquet as pq

            pq.write_table(pa.Table.from_pandas(trading_cal_df, preserve_index=False), trading_out)
            pq.write_table(pa.Table.from_pandas(calendar_days_df, preserve_index=False), days_out)
        except Exception as e:
            print(f"[WARN] Calendar parquet write failed, falling back to CSV: {e}")
            trading_cal_df.to_csv(cfg.processed_root / "trading_calendars.csv", index=False)
            calendar_days_df.to_csv(cfg.processed_root / "calendar_days.csv", index=False)

    # DuckDB
    build_duckdb(cfg.processed_root)

    print("Done!")
    print(f"Processed root: {cfg.processed_root}")
    print(f"DuckDB:         {cfg.processed_root / 'simutrader.duckdb'}")
    print(f"Parquet prices: {cfg.processed_root / 'prices'}")


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser()

    ap.add_argument("--processed-root", type=str, required=True)
    ap.add_argument("--us-root", type=str, default=None)
    ap.add_argument("--bse-root", type=str, default=None)
    ap.add_argument("--fx-xls", type=str, default=None)

    ap.add_argument("--keep-us-suffix", action="store_true", help="Keep .US in US symbols")
    ap.add_argument("--keep-bo-suffix", action="store_true", help="Keep .BO in India symbols")

    return ap.parse_args()


def main() -> None:
    args = parse_args()

    cfg = IngestConfig(
        processed_root=Path(args.processed_root).expanduser().resolve(),
        us_root=Path(args.us_root).expanduser().resolve() if args.us_root else None,
        bse_root=Path(args.bse_root).expanduser().resolve() if args.bse_root else None,
        fx_xls=Path(args.fx_xls).expanduser().resolve() if args.fx_xls else None,
        strip_us_suffix=not args.keep_us_suffix,
        strip_bo_suffix=not args.keep_bo_suffix,
    )

    ingest_snapshot(cfg)


if __name__ == "__main__":
    main()
