# SimuTrader

SimuTrader is a web app for running daily backtests over US stocks, Indian stocks, and FX using snapshot datasets. The current implementation focuses on a multi-symbol Buy & Hold baseline with a FastAPI backend, DuckDB for reading Parquet OHLCV, and Postgres for run metadata + results.

## Current State (What Works Today)

- Buy & Hold backtests for a basket of symbols with either explicit amounts or equal-weight default.
- Executes at the first available close in the date range and then holds.
- Missing bars on open-market days default to **FAIL**; optional **FORWARD_FILL** policy is available.
- Persists daily equity series and basic metrics.
- API endpoints for runs and assets (see API section).
- Docker Compose for API, worker, Postgres, Redis, and web container.

## MVP To-Do (Remaining)

- ~~Repo + Docker Compose skeleton (frontend, api, postgres, redis)~~
- ~~Data ingestion script v1: normalize snapshot data -> Parquet partitions + DuckDB views~~
- ~~Trading calendar alignment: deterministic weekday calendars + DuckDB calendar views~~
- Config validation: JSON Schema validation for strategy configs + server-side checks
- Backtest engine v1: add fills, positions, and cash flow persistence
- Add transaction costs: commission + slippage models
- Add shorting support: negative qty, borrow fee daily, cover events
- Add margin support: leverage constraints, borrowed cash tracking, margin interest
- Add taxes v1: FIFO lots + holding period buckets; US/India toggle parameters; generate `run_tax_events`
- Persist outputs: write `run_positions`, `run_fills`, `run_cash_flows` to Postgres
- Frontend MVP: strategy builder + run list + run detail dashboard (charts + ledger + cost decomposition)
- Compare runs UI: side-by-side metrics + equity/drawdown overlays
- Stretch: notable strategy presets gallery + seeded demo runs
- Stretch: report export (CSV trades + JSON config + HTML summary)
- Stretch: performance bench page (rows/sec, p95 runtime)

## System Overview

- Frontend: Next.js + Tailwind + Charts (Recharts/Plotly)
- Backend: FastAPI (Python)
- Compute/Data: DuckDB reading Parquet partitions for fast OHLCV access
- DB: Postgres for metadata, configs, runs, trades, daily portfolio values, and metrics
- Async: Celery + Redis for non-blocking backtests
- Local deployment: Docker Compose (frontend + api + postgres + redis)

## Data Model (High-Level)

- Parquet OHLCV partitions for price data (asset_class/symbol/year)
- Postgres for assets, strategies, backtest runs, metrics, daily equity, trades, taxes, and financing
- No FX conversion; multi-currency runs report `equity_by_currency` without a single total.

## API (Current)

- `GET /health`
- `GET /assets`
- `POST /backtests`, `GET /backtests/{run_id}`
- `GET /runs/{run_id}`
- `GET /runs/{run_id}/equity`
- `GET /runs/{run_id}/metrics`

## Backtest Config (Buy & Hold)

Amount-based allocation:
```json
{
  "universe": {
    "instruments": [
      { "symbol": "AAPL", "asset_class": "US_EQUITY", "amount": 4000 },
      { "symbol": "MSFT", "asset_class": "US_EQUITY", "amount": 6000 }
    ]
  },
  "start_date": "2024-01-02",
  "end_date": "2024-03-01",
  "initial_cash": 10000
}
```

Equal-weight default (no amounts or weights):
```json
{
  "universe": {
    "instruments": [
      { "symbol": "AAPL", "asset_class": "US_EQUITY" },
      { "symbol": "MSFT", "asset_class": "US_EQUITY" }
    ]
  },
  "start_date": "2024-01-02",
  "end_date": "2024-03-01",
  "initial_cash": 10000
}
```

## Local Dev

1) Copy env templates as needed.
2) Run `make up`.
3) API health: `http://localhost:8000/health`.
4) Prepare data (once per dataset):
   - Run `scripts/ingest/ingest_preprocess.py`
   - Run `scripts/create_calendar_views.py`
   - Run `scripts/seed_postgres_metadata.py`

## Required Next Steps

- Add holdings/fills/cashflow persistence in the backtest engine.
- Add strategy registry + validation (Pydantic).
- Build UI in `apps/web/app/` for strategy builder, run list, and dashboards.

## Quality Bar

- Unit tests for fill costs, borrow fees, margin interest, FIFO lots, and tax bucket classification.
- Deterministic reruns with fixed seed + fixed fill model.
