#!/usr/bin/env bash
set -euo pipefail

# Deterministic backend smoke run:
# 1) bring core services up
# 2) optionally recreate worker with higher concurrency
# 3) run app.scripts.e2e_smoke_runner inside API container

WORKER_CONCURRENCY="${WORKER_CONCURRENCY:-2}"
EXECUTION_MODE="${SMOKE_EXECUTION_MODE:-sequential}"
BATCH_SIZE="${SMOKE_BATCH_SIZE:-2}"
POLL_TIMEOUT_SECONDS="${SMOKE_POLL_TIMEOUT_SECONDS:-900}"
POLL_INTERVAL_SECONDS="${SMOKE_POLL_INTERVAL_SECONDS:-2}"
REQUEST_TIMEOUT_SECONDS="${SMOKE_REQUEST_TIMEOUT_SECONDS:-120}"
API_BASE_URL="${SMOKE_API_BASE_URL:-http://localhost:8000}"
DATA_SNAPSHOT_ID="${SMOKE_DATA_SNAPSHOT_ID:-smoke_e2e_v1}"
SEED="${SMOKE_SEED:-42}"
WINDOW_DAYS="${SMOKE_WINDOW_DAYS:-10}"
RUN_PREFIX="${SMOKE_RUN_PREFIX:-smoke-e2e}"

echo "Starting backend services..."
docker compose up -d postgres redis api

echo "Recreating worker with concurrency=${WORKER_CONCURRENCY}..."
WORKER_CONCURRENCY="${WORKER_CONCURRENCY}" docker compose up -d --force-recreate worker

echo "Running deterministic backend smoke runner..."
docker compose exec -T api sh -lc "python -m app.scripts.e2e_smoke_runner \
  --api-base-url '${API_BASE_URL}' \
  --execution-mode '${EXECUTION_MODE}' \
  --batch-size '${BATCH_SIZE}' \
  --poll-timeout-seconds '${POLL_TIMEOUT_SECONDS}' \
  --poll-interval-seconds '${POLL_INTERVAL_SECONDS}' \
  --request-timeout-seconds '${REQUEST_TIMEOUT_SECONDS}' \
  --data-snapshot-id '${DATA_SNAPSHOT_ID}' \
  --seed '${SEED}' \
  --window-days '${WINDOW_DAYS}' \
  --run-prefix '${RUN_PREFIX}'"
