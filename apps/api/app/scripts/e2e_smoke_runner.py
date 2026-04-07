from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass
from datetime import date, timedelta
from itertools import combinations
from typing import Any
from urllib import parse, request
import http.cookiejar


TERMINAL_STATUSES = {"SUCCEEDED", "FAILED", "ENQUEUE_FAILED"}


@dataclass(frozen=True)
class SymbolCoverage:
    symbol: str
    first_date: date
    last_date: date
    rows: int


@dataclass(frozen=True)
class Scenario:
    name: str
    config_snapshot: dict[str, Any]
    expect_status: str
    expect_error_code: str | None = None


class ApiClient:
    def __init__(self, base_url: str, timeout_seconds: int = 60) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.cookies = http.cookiejar.CookieJar()
        self.opener = request.build_opener(request.HTTPCookieProcessor(self.cookies))

    def call(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
    ) -> tuple[int, Any]:
        body = None
        headers = {"Content-Type": "application/json"}
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
        req = request.Request(
            f"{self.base_url}{path}",
            data=body,
            method=method.upper(),
            headers=headers,
        )
        try:
            with self.opener.open(req, timeout=self.timeout_seconds) as resp:
                raw = resp.read().decode("utf-8")
                return resp.status, json.loads(raw) if raw else None
        except request.HTTPError as exc:
            raw = exc.read().decode("utf-8") if exc.fp else ""
            parsed = None
            if raw:
                try:
                    parsed = json.loads(raw)
                except json.JSONDecodeError:
                    parsed = {"raw": raw}
            return exc.code, parsed


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Deterministic end-to-end smoke runner for backtest strategies."
    )
    parser.add_argument("--api-base-url", default="http://localhost:8000")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--data-snapshot-id", default="smoke_e2e_v1")
    parser.add_argument("--run-prefix", default="smoke-e2e")
    parser.add_argument("--window-days", type=int, default=10)
    parser.add_argument("--poll-interval-seconds", type=float, default=2.0)
    parser.add_argument("--poll-timeout-seconds", type=int, default=900)
    parser.add_argument("--request-timeout-seconds", type=int, default=180)
    parser.add_argument(
        "--execution-mode",
        choices=("sequential", "batch"),
        default="sequential",
    )
    parser.add_argument("--batch-size", type=int, default=2)
    return parser.parse_args()


def _iso(value: date) -> str:
    return value.isoformat()


def _coverage_for_symbols(
    client: ApiClient, symbols: list[str], calendar: str = "GLOBAL"
) -> dict[str, SymbolCoverage]:
    if not symbols:
        return {}

    chunk_size = 10
    result: dict[str, SymbolCoverage] = {}
    for i in range(0, len(symbols), chunk_size):
        chunk = symbols[i : i + chunk_size]
        query = parse.urlencode(
            {
                "symbols": ",".join(chunk),
                "calendar": calendar,
            }
        )
        status, payload = client.call("GET", f"/market/coverage?{query}")
        if status != 200 or not isinstance(payload, list):
            continue
        for row in payload:
            try:
                coverage = SymbolCoverage(
                    symbol=str(row["symbol"]).upper(),
                    first_date=date.fromisoformat(str(row["first_date"])),
                    last_date=date.fromisoformat(str(row["last_date"])),
                    rows=int(row["rows"]),
                )
            except Exception:
                continue
            result[coverage.symbol] = coverage
    return result


def _discover_symbols(client: ApiClient, window_days: int) -> tuple[str, str, str, date, date]:
    status_us, us_assets = client.call(
        "GET", "/assets?asset_class=US_EQUITY&is_active=true&limit=40"
    )
    status_in, in_assets = client.call(
        "GET", "/assets?asset_class=IN_EQUITY&is_active=true&limit=40"
    )
    if status_us != 200 or not isinstance(us_assets, list) or len(us_assets) < 2:
        raise RuntimeError("Unable to fetch enough US_EQUITY assets for smoke selection.")
    if status_in != 200 or not isinstance(in_assets, list) or len(in_assets) < 1:
        raise RuntimeError("Unable to fetch IN_EQUITY assets for smoke selection.")

    us_symbols = [str(row.get("symbol", "")).upper() for row in us_assets if row.get("symbol")]
    in_symbols = [str(row.get("symbol", "")).upper() for row in in_assets if row.get("symbol")]

    us_pick = [symbol for symbol in us_symbols if symbol.replace("-", "").isalnum()][:10]
    in_pick = [symbol for symbol in in_symbols if symbol.replace("-", "").isalnum()][:10]
    if len(us_pick) < 2 or len(in_pick) < 1:
        raise RuntimeError("Unable to select deterministic US/IN symbols from assets metadata.")

    us_a, us_b = us_pick[0], us_pick[1]
    in_a = in_pick[0]

    # Use a known short historical window used in integration checks to avoid
    # expensive discovery queries in smoke mode.
    return us_a, us_b, in_a, date(2024, 1, 2), date(2024, 1, 12)


def _base_config(
    start_date: date,
    end_date: date,
    initial_cash: float = 10000.0,
) -> dict[str, Any]:
    return {
        "version": 1,
        "base_currency": "USD",
        "data_policy": {
            "missing_bar": "FORWARD_FILL",
            "missing_fx": "FORWARD_FILL",
        },
        "backtest": {
            "start_date": _iso(start_date),
            "end_date": _iso(end_date),
            "initial_cash": float(initial_cash),
        },
    }


def _build_scenarios(
    us_a: str,
    us_b: str,
    in_a: str,
    start_date: date,
    end_date: date,
) -> list[Scenario]:
    base = _base_config(start_date, end_date)

    def merge(*parts: dict[str, Any]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for part in parts:
            for key, value in part.items():
                out[key] = value
        return out

    scenarios: list[Scenario] = [
        Scenario(
            name="buy_hold_single_us",
            expect_status="SUCCEEDED",
            config_snapshot=merge(
                base,
                {
                    "strategy": "BUY_AND_HOLD",
                    "universe": {
                        "instruments": [
                            {"symbol": us_a, "asset_class": "US_EQUITY", "amount": 9900.0},
                        ]
                    },
                },
            ),
        ),
        Scenario(
            name="fixed_weight_rebalance_single_us",
            expect_status="SUCCEEDED",
            config_snapshot=merge(
                base,
                {
                    "strategy": "FIXED_WEIGHT_REBALANCE",
                    "strategy_params": {
                        "target_weights": {us_a: 0.6, us_b: 0.4},
                        "rebalance_frequency": "DAILY",
                        "drift_threshold": 0.0,
                    },
                    "universe": {
                        "instruments": [
                            {"symbol": us_a, "asset_class": "US_EQUITY"},
                            {"symbol": us_b, "asset_class": "US_EQUITY"},
                        ]
                    },
                },
            ),
        ),
        Scenario(
            name="dca_single_us",
            expect_status="SUCCEEDED",
            config_snapshot=merge(
                _base_config(start_date, end_date, initial_cash=200.0),
                {
                    "strategy": "DCA",
                    "strategy_params": {"buy_frequency": "DAILY", "weighting": "EQUAL"},
                    "backtest": {
                        "start_date": _iso(start_date),
                        "end_date": _iso(end_date),
                        "initial_cash": 200.0,
                        "contributions": {
                            "enabled": True,
                            "amount": 1000.0,
                            "frequency": "WEEKLY",
                        },
                    },
                    "universe": {
                        "instruments": [
                            {"symbol": us_a, "asset_class": "US_EQUITY"},
                            {"symbol": us_b, "asset_class": "US_EQUITY"},
                        ]
                    },
                },
            ),
        ),
        Scenario(
            name="momentum_single_us",
            expect_status="SUCCEEDED",
            config_snapshot=merge(
                base,
                {
                    "strategy": "MOMENTUM",
                    "strategy_params": {
                        "lookback_days": 3,
                        "skip_days": 1,
                        "top_k": 1,
                        "rebalance_frequency": "WEEKLY",
                        "weighting": "EQUAL",
                    },
                    "universe": {
                        "instruments": [
                            {"symbol": us_a, "asset_class": "US_EQUITY"},
                            {"symbol": us_b, "asset_class": "US_EQUITY"},
                        ]
                    },
                },
            ),
        ),
        Scenario(
            name="mean_reversion_single_us",
            expect_status="SUCCEEDED",
            config_snapshot=merge(
                base,
                {
                    "strategy": "MEAN_REVERSION",
                    "strategy_params": {
                        "lookback_days": 5,
                        "entry_threshold": 0.5,
                        "hold_days": 3,
                        "rebalance_frequency": "DAILY",
                    },
                    "universe": {
                        "instruments": [
                            {"symbol": us_a, "asset_class": "US_EQUITY"},
                        ]
                    },
                },
            ),
        ),
        Scenario(
            name="buy_hold_mixed_currency_supported",
            expect_status="SUCCEEDED",
            config_snapshot=merge(
                base,
                {
                    "strategy": "BUY_AND_HOLD",
                    "backtest": {
                        "start_date": _iso(start_date),
                        "end_date": _iso(end_date),
                        "initial_cash": 1.0,
                        "initial_cash_by_currency": {
                            "USD": 10000.0,
                            "INR": 200000.0,
                        },
                    },
                    "universe": {
                        "instruments": [
                            {"symbol": us_a, "asset_class": "US_EQUITY", "amount": 8000.0},
                            {"symbol": in_a, "asset_class": "IN_EQUITY", "amount": 150000.0},
                        ]
                    },
                },
            ),
        ),
        Scenario(
            name="dca_mixed_currency_expected_fail",
            expect_status="FAILED",
            expect_error_code="E_CONFIG_INVALID",
            config_snapshot=merge(
                base,
                {
                    "strategy": "DCA",
                    "strategy_params": {"buy_frequency": "DAILY", "weighting": "EQUAL"},
                    "backtest": {
                        "start_date": _iso(start_date),
                        "end_date": _iso(end_date),
                        "initial_cash": 1.0,
                        "initial_cash_by_currency": {
                            "USD": 5000.0,
                            "INR": 100000.0,
                        },
                    },
                    "universe": {
                        "instruments": [
                            {"symbol": us_a, "asset_class": "US_EQUITY"},
                            {"symbol": in_a, "asset_class": "IN_EQUITY"},
                        ]
                    },
                },
            ),
        ),
    ]
    return scenarios


def _submit_run(
    client: ApiClient,
    scenario: Scenario,
    data_snapshot_id: str,
    seed: int,
    run_prefix: str,
) -> str:
    payload = {
        "name": f"{run_prefix}-{scenario.name}",
        "config_snapshot": scenario.config_snapshot,
        "data_snapshot_id": data_snapshot_id,
        "seed": seed,
    }
    status, body = client.call("POST", "/backtests", payload)
    if status not in {200, 201, 202} or not isinstance(body, dict):
        raise RuntimeError(
            f"Run create failed for scenario '{scenario.name}' with status={status} body={body}"
        )
    run_id = body.get("run_id")
    if not run_id:
        raise RuntimeError(f"Run create response missing run_id for scenario '{scenario.name}'.")
    return str(run_id)


def _poll_terminal_run(
    client: ApiClient,
    run_id: str,
    poll_interval_seconds: float,
    poll_timeout_seconds: int,
) -> dict[str, Any]:
    started = time.monotonic()
    while True:
        status, body = client.call("GET", f"/runs/{run_id}")
        if status == 200 and isinstance(body, dict):
            state = str(body.get("status", "")).upper()
            if state in TERMINAL_STATUSES:
                return body
        if (time.monotonic() - started) > poll_timeout_seconds:
            raise TimeoutError(
                f"Run {run_id} did not reach terminal status within {poll_timeout_seconds}s"
            )
        time.sleep(poll_interval_seconds)


def _assert_run_expectation(
    scenario: Scenario,
    run_out: dict[str, Any],
) -> list[str]:
    errors: list[str] = []
    status = str(run_out.get("status") or "").upper()
    if status != scenario.expect_status:
        errors.append(
            f"{scenario.name}: expected status={scenario.expect_status}, got status={status}"
        )
    expected_code = scenario.expect_error_code
    actual_code = run_out.get("error_code")
    if expected_code and actual_code != expected_code:
        errors.append(
            f"{scenario.name}: expected error_code={expected_code}, got error_code={actual_code}"
        )
    if expected_code is None and actual_code is not None and status == "SUCCEEDED":
        errors.append(
            f"{scenario.name}: expected no error_code for success, got error_code={actual_code}"
        )
    return errors


def _verify_tax_and_equity(
    client: ApiClient,
    scenario: Scenario,
    run_id: str,
    terminal: dict[str, Any],
) -> list[str]:
    errors: list[str] = []
    status_taxes, taxes = client.call("GET", f"/backtests/{run_id}/taxes")
    if status_taxes != 200 or not isinstance(taxes, dict):
        errors.append(f"{scenario.name}: taxes endpoint returned status={status_taxes}")
        return errors
    for key in ("event_count", "total_realized_pnl_base", "total_tax_due_base"):
        if key not in taxes:
            errors.append(f"{scenario.name}: taxes response missing key '{key}'")

    if str(terminal.get("status")).upper() == "SUCCEEDED":
        status_equity, equity = client.call("GET", f"/runs/{run_id}/equity?limit=20")
        if status_equity != 200 or not isinstance(equity, list):
            errors.append(f"{scenario.name}: equity endpoint returned status={status_equity}")
        elif len(equity) == 0:
            errors.append(f"{scenario.name}: expected non-empty equity series for succeeded run")
    return errors


def _verify_compare(
    client: ApiClient,
    succeeded_runs: list[str],
) -> list[str]:
    errors: list[str] = []
    if len(succeeded_runs) < 2:
        errors.append("compare check skipped: fewer than 2 succeeded runs")
        return errors

    base = succeeded_runs[0]
    peers = ",".join(succeeded_runs[1:])
    status, payload = client.call("GET", f"/backtests/{base}/compare?run_ids={peers}")
    if status != 200 or not isinstance(payload, dict):
        errors.append(f"compare endpoint returned status={status}")
        return errors

    metric_rows = payload.get("metric_rows", [])
    equity_series = payload.get("equity_series", [])
    if not isinstance(metric_rows, list) or len(metric_rows) != len(succeeded_runs):
        errors.append(
            f"compare metric_rows mismatch: expected {len(succeeded_runs)}, got {len(metric_rows) if isinstance(metric_rows, list) else 'invalid'}"
        )
    if not isinstance(equity_series, list) or len(equity_series) != len(succeeded_runs):
        errors.append(
            f"compare equity_series mismatch: expected {len(succeeded_runs)}, got {len(equity_series) if isinstance(equity_series, list) else 'invalid'}"
        )
    else:
        for series in equity_series:
            points = series.get("points") if isinstance(series, dict) else None
            if not isinstance(points, list) or len(points) == 0:
                errors.append("compare series contains empty normalized points")
                break
    return errors


def _verify_history_contains_runs(client: ApiClient, run_ids: list[str]) -> list[str]:
    errors: list[str] = []
    status, payload = client.call("GET", "/backtests?limit=200")
    if status != 200 or not isinstance(payload, list):
        return [f"history endpoint returned status={status}"]
    seen = {str(row.get("run_id")) for row in payload if isinstance(row, dict)}
    missing = [run_id for run_id in run_ids if run_id not in seen]
    if missing:
        errors.append(f"history missing run_ids: {missing}")
    return errors


def _run_batch(
    client: ApiClient,
    scenarios: list[Scenario],
    data_snapshot_id: str,
    seed: int,
    run_prefix: str,
    poll_interval_seconds: float,
    poll_timeout_seconds: int,
) -> tuple[dict[str, str], dict[str, dict[str, Any]]]:
    run_ids: dict[str, str] = {}
    terminal_by_name: dict[str, dict[str, Any]] = {}
    for scenario in scenarios:
        run_ids[scenario.name] = _submit_run(
            client, scenario, data_snapshot_id, seed, run_prefix
        )
    for scenario in scenarios:
        terminal_by_name[scenario.name] = _poll_terminal_run(
            client,
            run_ids[scenario.name],
            poll_interval_seconds=poll_interval_seconds,
            poll_timeout_seconds=poll_timeout_seconds,
        )
    return run_ids, terminal_by_name


def main() -> int:
    args = _parse_args()
    client = ApiClient(args.api_base_url, timeout_seconds=args.request_timeout_seconds)

    us_a, us_b, in_a, start_date, end_date = _discover_symbols(client, args.window_days)
    scenarios = _build_scenarios(us_a, us_b, in_a, start_date, end_date)

    all_run_ids: dict[str, str] = {}
    all_terminal: dict[str, dict[str, Any]] = {}
    errors: list[str] = []

    if args.execution_mode == "sequential":
        batches = [[scenario] for scenario in scenarios]
    else:
        size = max(1, int(args.batch_size))
        batches = [scenarios[i : i + size] for i in range(0, len(scenarios), size)]

    for batch in batches:
        run_ids, terminals = _run_batch(
            client=client,
            scenarios=batch,
            data_snapshot_id=args.data_snapshot_id,
            seed=args.seed,
            run_prefix=args.run_prefix,
            poll_interval_seconds=args.poll_interval_seconds,
            poll_timeout_seconds=args.poll_timeout_seconds,
        )
        all_run_ids.update(run_ids)
        all_terminal.update(terminals)

        for scenario in batch:
            run_id = run_ids[scenario.name]
            terminal = terminals[scenario.name]
            errors.extend(_assert_run_expectation(scenario, terminal))
            errors.extend(_verify_tax_and_equity(client, scenario, run_id, terminal))

    succeeded_run_ids = [
        all_run_ids[scenario.name]
        for scenario in scenarios
        if str(all_terminal[scenario.name].get("status")).upper() == "SUCCEEDED"
    ]

    errors.extend(_verify_compare(client, succeeded_run_ids))
    errors.extend(_verify_history_contains_runs(client, list(all_run_ids.values())))

    summary = {
        "symbols": {"us_a": us_a, "us_b": us_b, "in_a": in_a},
        "window": {"start_date": _iso(start_date), "end_date": _iso(end_date)},
        "execution_mode": args.execution_mode,
        "batch_size": args.batch_size,
        "run_count": len(scenarios),
        "succeeded_count": len(succeeded_run_ids),
        "runs": {
            scenario.name: {
                "run_id": all_run_ids[scenario.name],
                "expected_status": scenario.expect_status,
                "expected_error_code": scenario.expect_error_code,
                "actual_status": all_terminal[scenario.name].get("status"),
                "actual_error_code": all_terminal[scenario.name].get("error_code"),
                "error_message_public": all_terminal[scenario.name].get("error_message_public"),
            }
            for scenario in scenarios
        },
        "errors": errors,
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
