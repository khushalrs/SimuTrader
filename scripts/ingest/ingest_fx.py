# fx_ingest_spreadsheetml.py
# pip install pandas numpy pyarrow

from pathlib import Path
import re
import numpy as np
import pandas as pd
import xml.etree.ElementTree as ET

SS_NS = {"ss": "urn:schemas-microsoft-com:office:spreadsheet"}
CCY_RE = re.compile(r"\(([A-Z]{3})\)")

# Fixed positions for this FX spreadsheet:
# header row is Excel row 3 (1-based), and Date is column A (0-based indices below).
HEADER_ROW_INDEX = 2
DATE_COL_INDEX = 0

def read_spreadsheetml_table(path: str | Path, worksheet_name: str | None = None) -> pd.DataFrame:
    """Read Excel 2003 XML Spreadsheet (SpreadsheetML) into a DataFrame (raw rows/cols)."""
    xml_text = Path(path).read_text(encoding="utf-8-sig", errors="ignore")
    root = ET.fromstring(xml_text)

    worksheets = root.findall(".//ss:Worksheet", SS_NS)
    if not worksheets:
        raise ValueError("No <Worksheet> found. Not a SpreadsheetML file?")

    ws = None
    if worksheet_name:
        for w in worksheets:
            name = w.get(f"{{{SS_NS['ss']}}}Name")
            if name == worksheet_name:
                ws = w
                break
        if ws is None:
            raise ValueError(f"Worksheet '{worksheet_name}' not found.")
    else:
        ws = worksheets[0]

    table = ws.find(".//ss:Table", SS_NS)
    if table is None:
        raise ValueError("No <Table> found in worksheet.")

    rows = table.findall("ss:Row", SS_NS)
    data = []
    max_len = 0

    for r in rows:
        row = []
        col_idx = 1
        for cell in r.findall("ss:Cell", SS_NS):
            idx = cell.get(f"{{{SS_NS['ss']}}}Index")  # sparse cell position
            if idx is not None:
                idx = int(idx)
                while col_idx < idx:
                    row.append(None)
                    col_idx += 1

            d = cell.find("ss:Data", SS_NS)
            if d is not None:
                # Data sometimes wraps text in <B> or other tags; itertext preserves it.
                text = "".join(d.itertext()).strip()
                row.append(text if text else None)
            else:
                row.append(None)
            col_idx += 1

        max_len = max(max_len, len(row))
        data.append(row)

    data = [r + [None] * (max_len - len(r)) for r in data]
    return pd.DataFrame(data)

def _extract_ccy(header_cell) -> str | None:
    if header_cell is None:
        return None
    s = str(header_cell).strip().upper()
    m = CCY_RE.search(s)
    if m:
        return m.group(1)
    # fallback: header itself is a 3-letter code
    if re.fullmatch(r"[A-Z]{3}", s):
        return s
    return None

def load_fx_xls_normalized(fx_path: str | Path, worksheet_name: str | None = None) -> pd.DataFrame:
    wide = read_spreadsheetml_table(fx_path, worksheet_name="EXCHANGE_RATE_REPORT")
    print("Loaded raw FX data shape:", wide.shape)
    h, date_col = HEADER_ROW_INDEX, DATE_COL_INDEX
    print("h, date_col:", h, date_col)

    header = wide.iloc[h, date_col:].tolist()
    data = wide.iloc[h + 1 :, date_col:].copy()
    data.columns = header

    # Normalize date column (first column is Date cell).
    # Some spreadsheets have duplicate header labels (e.g., repeated "Date"),
    # so use the first column positionally to avoid duplicate-key issues.
    date_series = data.iloc[:, 0]
    data = data.rename(columns={data.columns[0]: "Date"})
    data["Date"] = pd.to_datetime(date_series, errors="coerce")
    data = data.dropna(subset=["Date"]).dropna(axis=1, how="all")

    out = []
    for col in data.columns:
        if col == "Date":
            continue

        ccy = _extract_ccy(col)
        if not ccy or ccy == "USD":
            continue

        s = pd.to_numeric(data[col], errors="coerce")
        if s.notna().sum() == 0:
            continue

        symbol = f"USD{ccy}"  # all quoted as CCY per 1 USD

        tmp = pd.DataFrame({
            "date": data["Date"].dt.date,
            "symbol": symbol,
            "asset_class": "FX",
            "currency": ccy,        # quote currency
            "open": s, "high": s, "low": s, "close": s,
            "volume": np.nan,
            "exchange": "FX",
            "data_source": "fx_spreadsheetml",
        }).dropna(subset=["date", "close"])

        tmp = tmp.sort_values("date").drop_duplicates(["date"], keep="last")
        out.append(tmp)

    if not out:
        raise ValueError("No FX columns parsed. Check headers contain currency codes like '(INR)'.")

    return pd.concat(out, ignore_index=True)

def write_fx_parquet_partitions(fx: pd.DataFrame, processed_root: str | Path) -> None:
    import pyarrow as pa
    import pyarrow.parquet as pq

    processed_root = Path(processed_root)
    prices_root = processed_root / "prices"

    fx = fx.copy()
    fx["year"] = pd.to_datetime(fx["date"]).dt.year.astype(int)

    for (symbol, year), g in fx.groupby(["symbol", "year"], sort=False):
        out_dir = prices_root / "asset_class=FX" / f"symbol={symbol}" / f"year={year}"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_file = out_dir / "ohlcv.parquet"

        g = g.drop(columns=["year"]).sort_values("date")
        pq.write_table(pa.Table.from_pandas(g, preserve_index=False), out_file)

if __name__ == "__main__":
    fx_path = "/Users/khushalsharma/Documents/Random_Shitz/SimuTrader/data/raw/fx.xls"
    processed_root = "/Users/khushalsharma/Documents/Random_Shitz/SimuTrader/data/processed"

    fx = load_fx_xls_normalized(fx_path)
    print(fx.head())
    print("FX symbols:", fx["symbol"].nunique(), "rows:", len(fx))

    write_fx_parquet_partitions(fx, processed_root)
    print("Wrote FX partitions under:", Path(processed_root) / "prices" / "asset_class=FX")
