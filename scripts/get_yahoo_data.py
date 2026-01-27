# pip install yfinance pandas requests lxml tqdm

from __future__ import annotations
import os, re, time
from io import StringIO

import pandas as pd
import requests
from tqdm import tqdm
import yfinance as yf

BSE_LIST_URL = "https://stockanalysis.com/list/bse-india/"
OUT_DIR = "bse_yahoo_download"
BATCH_SIZE = 20
SLEEP = 1.5

def safe_filename(s: str, maxlen: int = 80) -> str:
    s = re.sub(r"[^\w\- ]+", "", s).strip()
    s = re.sub(r"\s+", "_", s)
    return s[:maxlen]

def fetch_stockanalysis_bse_list() -> pd.DataFrame:
    r = requests.get(BSE_LIST_URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=60)
    r.raise_for_status()
    df = pd.read_html(StringIO(r.text))[0]
    df["Symbol"] = df["Symbol"].astype(str).str.strip()
    df = df[df["Symbol"].str.match(r"^\d+$", na=False)].copy()
    df = df.drop_duplicates(subset=["Symbol"]).reset_index(drop=True)
    return df[["Symbol", "Company Name"]].rename(columns={"Symbol": "bse_code", "Company Name": "company"})

def resolve_to_yahoo_bo(company: str) -> str | None:
    """
    Use Yahoo search via yfinance.Search to find the best .BO ticker for a company name.
    Docs: yfinance Search module. :contentReference[oaicite:7]{index=7}
    """
    try:
        s = yf.Search(company, max_results=8, news_count=0)
        quotes = s.quotes or []
    except Exception:
        return None

    # Prefer BSE tickers that end with .BO
    # yfinance search quote dict keys vary slightly by version; handle common ones.
    candidates = []
    for q in quotes:
        sym = q.get("symbol")
        exch = (q.get("exchange") or q.get("exchDisp") or "").upper()
        if not sym:
            continue
        if sym.endswith(".BO"):
            score = 0
            if "BSE" in exch:
                score += 10
            # Prefer equities
            if (q.get("quoteType") or "").upper() in ("EQUITY", "STOCK"):
                score += 3
            candidates.append((score, sym))

    if not candidates:
        return None

    candidates.sort(reverse=True)
    return candidates[0][1]

def chunk(xs, n):
    for i in range(0, len(xs), n):
        yield xs[i:i+n]

def main(limit: int | None = None):
    os.makedirs(OUT_DIR, exist_ok=True)

    # Avoid "database is locked": isolate cache per run (or delete the default cache dir).
    # yfinance cache docs: :contentReference[oaicite:8]{index=8}
    run_cache = os.path.abspath(f"./.py-yfinance-cache-{os.getpid()}")
    os.makedirs(run_cache, exist_ok=True)
    yf.set_tz_cache_location(run_cache)

    bse = fetch_stockanalysis_bse_list()
    if limit:
        bse = bse.head(limit)

    # Resolve each company -> Yahoo .BO ticker
    yahoo = []
    for _, row in tqdm(bse.iterrows(), total=len(bse), desc="Resolving Yahoo tickers"):
        t = resolve_to_yahoo_bo(row["company"])
        yahoo.append(t)

        # throttle Yahoo search a bit
        time.sleep(0.1)

    bse["yahoo"] = yahoo

    # Fallback: if search fails, keep numeric code .BO (less reliable)
    bse["yahoo"] = bse["yahoo"].fillna(bse["bse_code"] + ".BO")

    # Save mapping so you always know which company was which ticker
    mapping_path = os.path.join(OUT_DIR, "bse_to_yahoo_mapping.csv")
    bse.to_csv(mapping_path, index=False)
    print("Saved mapping:", mapping_path)

    # Download max data
    tickers = bse["yahoo"].unique().tolist()

    failed = []
    for batch in tqdm(list(chunk(tickers, BATCH_SIZE)), desc="Downloading batches"):
        try:
            df = yf.download(
                batch,
                period="max",
                interval="1d",
                group_by="ticker",
                threads=1,      # keep it 1 to reduce cache contention
                progress=False,
            )
        except Exception as e:
            failed.extend(batch)
            time.sleep(3)
            continue

        # Save per ticker CSV
        if isinstance(df.columns, pd.MultiIndex):
            for t in batch:
                if t not in df.columns.get_level_values(0):
                    failed.append(t)
                    continue
                sub = df[t].dropna(how="all")
                if sub.empty:
                    failed.append(t)
                    continue

                # attach identity in filename using mapping
                company = bse.loc[bse["yahoo"] == t, "company"].iloc[0] if (bse["yahoo"] == t).any() else t
                fname = f"{t}__{safe_filename(company)}.csv"
                sub.index.name = "Date"
                sub.to_csv(os.path.join(OUT_DIR, fname))
        else:
            # single-ticker case
            t = batch[0]
            sub = df.dropna(how="all")
            if sub.empty:
                failed.append(t)
            else:
                company = bse.loc[bse["yahoo"] == t, "company"].iloc[0] if (bse["yahoo"] == t).any() else t
                fname = f"{t}__{safe_filename(company)}.csv"
                sub.index.name = "Date"
                sub.to_csv(os.path.join(OUT_DIR, fname))

        time.sleep(SLEEP)

    if failed:
        fail_path = os.path.join(OUT_DIR, "failed_after_resolve.txt")
        pd.Series(sorted(set(failed))).to_csv(fail_path, index=False, header=False)
        print("Some tickers still failed (likely not on Yahoo / blocked):", fail_path)

if __name__ == "__main__":
    main(limit=None)  # set limit=200 to test
