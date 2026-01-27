# SimuTrader

SimuTrader is a web app for running daily backtests over US stocks, Indian stocks, and FX using snapshot datasets. It supports long/short with margin, configurable financing costs, and a tax regime toggle (US vs India) that is parameter-driven. Results are presented in a clean dashboard with cost/tax decomposition and run comparisons.

## MVP To-Do

- ~~Repo + Docker Compose skeleton (frontend, api, postgres, redis)~~
- Data ingestion script v1: download/load snapshots -> normalize -> write Parquet partitions + insert `assets` metadata
- Trading calendar alignment: generate US/India calendars (weekday + deterministic holidays)
- Config validation: JSON Schema validation for strategy configs + server-side checks
- Backtest engine v1 (long-only): daily loop, orders, fills, portfolio accounting
- Add transaction costs: commission + slippage models
- Add shorting support: negative qty, borrow fee daily, cover events
- Add margin support: leverage constraints, borrowed cash tracking, margin interest
- Add taxes v1: FIFO lots + holding period buckets; US/India toggle parameters; generate `run_tax_events`
- Persist outputs: write `run_daily_equity`, `run_fills`, `run_metrics` to Postgres
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
- Base currency reporting with FX conversion (e.g., USDINR)

## API (MVP)

- `POST /strategies`, `GET /strategies`, `GET /strategies/{id}`
- `POST /backtests`, `GET /backtests`, `GET /backtests/{run_id}`
- `GET /backtests/{run_id}/equity`, `/trades`, `/taxes`
- `GET /backtests/{run_id}/compare?run_ids=...`
- `GET /assets`, `GET /assets/{symbol}`

## Local Dev

1) Copy env templates as needed.
2) Run `make up`.
3) API health: `http://localhost:8000/health`.

## Required Next Steps

- Implement data ingestion scripts in `scripts/ingest/` to produce normalized Parquet and seed `assets`.
- Define Postgres schema and migrations in `apps/api/alembic/`.
- Build core backtest engine + cost/tax logic in `apps/api/app/backtest/`.
- Implement API routers in `apps/api/app/api/`.
- Build UI in `apps/web/app/` for strategy builder, run list, and dashboards.

## Quality Bar

- Unit tests for fill costs, borrow fees, margin interest, FIFO lots, and tax bucket classification.
- Deterministic reruns with fixed seed + fixed fill model.
