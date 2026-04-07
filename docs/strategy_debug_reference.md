# Strategy Debug & Test Reference

This guide is for quickly debugging strategy run issues and validating API/worker consistency.

## Quick Validation Commands

### 1) Full backend tests

```bash
docker compose run --rm -v "$(pwd)/apps/api/tests:/app/tests" api sh -lc "pip install -q pytest && python -m pytest /app/tests -q"
```

### 2) Deterministic smoke validation

```bash
make smoke-backend
```

Useful overrides:

```bash
WORKER_CONCURRENCY=3 \
SMOKE_EXECUTION_MODE=batch \
SMOKE_BATCH_SIZE=3 \
SMOKE_POLL_TIMEOUT_SECONDS=900 \
SMOKE_REQUEST_TIMEOUT_SECONDS=30 \
make smoke-backend
```

## API/Worker Consistency Checklist

1. API validates and normalizes `config_snapshot` via JSON Schema + cross-field checks.
2. API persists resolved config to `backtest_runs.config_snapshot`.
3. Worker reads that same persisted snapshot (no alternate schema).
4. Strategy routing uses `config_snapshot.strategy`.
5. Terminal statuses are one of:
   - `SUCCEEDED`
   - `FAILED`
   - `ENQUEUE_FAILED`
6. Public failures are structured:
   - `error_code`
   - `error_message_public`
   - `error_retryable`
   - `error_id`

## Common Failure Patterns

### `E_CONFIG_INVALID`

Usually strategy/runtime constraints, for example:

- mixed-currency payload on strategy that is single-currency only (`DCA`, `MOMENTUM`, `MEAN_REVERSION`, current `FIXED_WEIGHT_REBALANCE` behavior)
- invalid `strategy_params`
- inconsistent instrument allocation fields

### `E_DATA_UNAVAILABLE`

Typical causes:

- missing bars with `data_policy.missing_bar=FAIL`
- missing required FX/currency metadata for selected universe/date range

### `E_NO_TRADING_DAYS`

- date range + calendar combination produces zero trading days

## Current Currency Support Matrix

- `BUY_AND_HOLD`: supports mixed-currency with explicit `amount` per instrument + `initial_cash_by_currency`.
- `FIXED_WEIGHT_REBALANCE`: effectively single-currency at runtime.
- `DCA`: single-currency only.
- `MOMENTUM`: single-currency only.
- `MEAN_REVERSION`: single-currency only.

## Useful API Checks

### Create run

```bash
curl -X POST http://localhost:8000/backtests \
  -H "Content-Type: application/json" \
  -d @run_payload.json
```

### Poll run status

```bash
curl "http://localhost:8000/runs/<run_id>"
```

### Validate tax contract

```bash
curl "http://localhost:8000/backtests/<run_id>/taxes"
```

### Validate compare contract

```bash
curl "http://localhost:8000/backtests/<base_run_id>/compare?run_ids=<run_id_2>,<run_id_3>"
```

## DB Inspection Snippets (inside API container)

```bash
python - <<'PY'
from sqlalchemy import create_engine, text
import os
engine = create_engine(os.environ["DATABASE_URL"])
with engine.connect() as c:
    rows = c.execute(text("""
        select run_id, name, status, error_code, created_at, started_at, finished_at
        from backtest_runs
        order by created_at desc
        limit 20
    """)).fetchall()
for row in rows:
    print(row)
PY
```

## Worker Throughput Notes

- Smoke defaults to sequential mode for deterministic assertions.
- If smoke is slow:
  - increase `WORKER_CONCURRENCY`
  - use `SMOKE_EXECUTION_MODE=batch`
  - keep batch size small (2-3) to avoid long queue tails.

## Recommended Test Drafting Pattern

1. Start from canonical format in `docs/strategy_runfile_format.md`.
2. Keep all common fields unchanged unless needed.
3. Change only:
   - `strategy`
   - `strategy_params`
   - instrument allocation style
4. Use `data_policy.missing_bar=FORWARD_FILL` for stable smoke testing.
5. For mixed currency:
   - provide explicit `amount` allocations
   - provide `initial_cash_by_currency` for every instrument currency.

