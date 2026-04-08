# SimuTrader

SimuTrader is a local full-stack backtesting workspace with a FastAPI backend, a Next.js frontend, DuckDB market data access, and Postgres persistence for run results. The current repo already supports submitting runs, exploring market data, and viewing run dashboards from the web app.

## Current Repo State

What is implemented in this checkout:

- FastAPI backend with routes for `backtests`, `runs`, `assets`, and `market`
- Next.js frontend with:
  - landing page
  - strategy builder
  - preset playground
  - market explore page
  - run dashboard page
- Postgres for run metadata and persisted outputs
- DuckDB for querying processed OHLCV data
- Redis + Celery worker for async backtest execution
- Docker Compose setup for local development
- Backend tests covering config validation, calendar logic, market routes, asset routes, run routes, and backtest integration

The git worktree is currently clean.

## Tech Stack

- Frontend: Next.js 14, React 18, Tailwind CSS, Radix UI, Recharts, Framer Motion
- Backend: FastAPI, SQLAlchemy, Alembic
- Data: DuckDB + Parquet
- Queueing: Celery + Redis
- Database: Postgres 16
- Local orchestration: Docker Compose

## Repo Layout

```text
.
├── apps/
│   ├── api/          # FastAPI app, backtest engine, Alembic, tests
│   └── web/          # Next.js app
├── infra/
│   └── postgres/     # init SQL
├── scripts/
│   ├── ingest/       # data ingestion helpers
│   └── duckdb/       # DuckDB SQL helpers
├── docker-compose.yml
├── Makefile
└── README.md
```

## Backend Features

### Backtests

- `POST /backtests`
- `GET /backtests`
- `GET /backtests/{run_id}`
- `GET /backtests/{run_id}/taxes`
- `GET /backtests/{run_id}/compare?run_ids=<id1,id2,...>`

Backtests can run in:

- `sync` mode for immediate execution in the API process
- `async` mode via Celery worker

The current strategy builder and preset playground both submit runs through this API.

### Runs

- `GET /runs/{run_id}`
- `GET /runs/{run_id}/equity`
- `GET /runs/{run_id}/metrics`
- `GET /runs/{run_id}/positions`
- `GET /runs/{run_id}/fills`
- `GET /runs/{run_id}/costs_summary`

Persisted run data includes:

- daily equity
- run metrics
- orders
- fills
- positions
- financing rows
- tax events

### Structured Error Contract

Backtest public responses expose only structured error fields:

- `error_code`
- `error_message_public`
- `error_retryable`
- `error_id`

Internal stack traces are not returned in API responses.

### Compare & Tax Contracts

`GET /backtests/{run_id}/taxes` returns:

- `event_count`
- `total_realized_pnl_base`
- `total_tax_due_base`
- `by_bucket_tax_due_base`
- `events[]` with per-event realized P&L and tax details

`GET /backtests/{run_id}/compare` returns:

- `metric_rows[]` aligned by `run_id`
- `equity_series[]` as normalized time series (`value` starts at `1.0` per run)

### Explainability Metadata

Run metric metadata includes reproducibility/explainability keys such as:

- `run_id`
- `seed`
- `data_snapshot_id`
- `config_version`
- `universe_summary` (instrument count, symbols, asset classes)

### Assets

- `GET /assets`
- `GET /assets/{symbol}`

Supports search plus filters such as asset class, currency, exchange, and active status. Asset detail also includes DuckDB-derived coverage metadata when available.

### Market Data

- `GET /market/bars`
- `GET /market/coverage`
- `GET /market/snapshot`

Current market route capabilities include:

- multi-symbol queries
- field selection
- trading-calendar alignment
- missing-bar policies: `RAW`, `FORWARD_FILL`, `DROP`
- daily and weekly intervals
- in-memory and optional Redis-backed response caching

## Frontend Pages

Implemented app routes:

- `/` : landing page
- `/build_page` : multi-step strategy builder
- `/playground` : run presets without manual configuration
- `/explore` : market snapshot, asset search, and multi-symbol lab
- `/runs/[runId]` : run dashboard

The run dashboard consumes run summary, metrics, equity, positions, fills, and cost data from the API.

## Local Development

### 1. Create env files

Root:

```bash
cp .env.example .env
```

API:

```bash
cp apps/api/.env.example apps/api/.env
```

Web:

```bash
cp apps/web/.env.local.example apps/web/.env.local
```

### 2. Start the stack

```bash
make up
```

This starts:

- `postgres`
- `redis`
- `api`
- `worker`
- `web`

Default local endpoints:

- web: `http://localhost:3000`
- api: `http://localhost:8000`
- health: `http://localhost:8000/health`

Useful commands:

```bash
make down
make logs
make api
make web
```

## Environment Notes

Important root-level settings from `.env.example`:

- `WEB_PORT`, `API_PORT`, `POSTGRES_PORT`, `REDIS_PORT`
- `DATA_DIR`, `PARQUET_DIR`, `DUCKDB_PATH`
- `DATA_SNAPSHOT_ID`
- `BACKTEST_EXEC_MODE`

Important API settings from `apps/api/.env.example`:

- `DATABASE_URL`
- `REDIS_URL`
- `CELERY_BROKER_URL`
- `CELERY_RESULT_BACKEND`
- `CORS_ORIGINS`
- `BASE_CURRENCY`

Frontend settings from `apps/web/.env.local.example`:

- `NEXT_PUBLIC_API_BASE_URL`
- `API_BASE_URL`

## Data Preparation

The app expects processed market data under `./data` and a DuckDB database at the configured `DUCKDB_PATH`.

Helper scripts present in this repo:

- `scripts/ingest/ingest_preprocess.py`
- `scripts/ingest/ingest_fx.py`
- `scripts/create_calendar_views.py`
- `scripts/seed_postgres_metadata.py`
- `scripts/validate_data.py`
- `scripts/get_yahoo_data.py`

Typical preparation flow:

1. place or ingest raw data into the expected local data directory
2. run preprocessing to generate processed data
3. build calendar views in DuckDB
4. seed Postgres asset metadata

## Testing

Backend tests are located in `apps/api/tests` and currently cover:

- config validation
- trading calendar behavior
- market route behavior
- asset route behavior
- run route behavior
- backtest persistence and integration flows

## Deterministic E2E Smoke Runner

For backend runtime verification of strategy + policy behavior, use:

```bash
make smoke-backend
```

This runs `scripts/run_backend_smoke.sh`, which:

1. starts `postgres`, `redis`, and `api`
2. recreates `worker` with configurable concurrency
3. runs `python -m app.scripts.e2e_smoke_runner` inside the API container

Smoke scenarios include:

- valid single-currency strategy runs (BUY_AND_HOLD, FIXED_WEIGHT_REBALANCE, DCA, MOMENTUM, MEAN_REVERSION)
- valid mixed-currency run (BUY_AND_HOLD with explicit amounts + `initial_cash_by_currency`)
- expected mixed-currency failure (DCA, which is currently single-currency only)

The runner asserts:

- terminal run states with long polling
- expected status/error-code per scenario
- tax endpoint shape (`/backtests/{run_id}/taxes`)
- non-empty equity for succeeded runs
- compare contract shape and normalized series (`/backtests/{run_id}/compare`)
- run history visibility (`/backtests`)

Useful overrides:

```bash
WORKER_CONCURRENCY=3 \
SMOKE_EXECUTION_MODE=batch \
SMOKE_BATCH_SIZE=3 \
SMOKE_POLL_TIMEOUT_SECONDS=1200 \
SMOKE_WINDOW_DAYS=10 \
./scripts/run_backend_smoke.sh
```

Notes:

- Default execution mode is `sequential` for deterministic queue behavior.
- To speed up smoke in CI/local, increase `WORKER_CONCURRENCY` and use `batch` mode.

## Strategy Docs

- Runfile contract: [`docs/strategy_runfile_format.md`](docs/strategy_runfile_format.md)
- Debug/testing reference: [`docs/strategy_debug_reference.md`](docs/strategy_debug_reference.md)

## Notes on Current Behavior

- The README previously described the project as mostly roadmap-stage; the codebase is now beyond that and already includes a functioning UI and richer run persistence.
- `docker-data/` exists in this repo and is being used for local Postgres storage in Compose.
- `apps/web/.next` and `apps/web/node_modules` are present locally, which indicates the frontend has already been built/run in this checkout.
