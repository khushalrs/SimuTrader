from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from typing import Any

import numpy as np
from sqlalchemy.orm import Session

from app.models.backtests import BacktestRun, RunDailyEquity, RunMetric
from app.models.research import ResearchJob, ResearchJobRun
from app.schemas.research import ResearchSweepSpecIn
from app.services.monte_carlo import (
    daily_returns_from_equity,
    monte_carlo_identity,
    simulate_daily_returns,
)
from app.services.research import expand_sweep_grid
from app.services.research_analytics import build_stitched_walk_forward_equity

ROBUSTNESS_SUMMARY_VERSION = 1
ROBUSTNESS_MONTE_CARLO_N = 5000
MINIMIZE_METRICS = {"volatility", "tracking_error"}


def _json_key(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _metric_value(metric: RunMetric | None, name: str) -> float | None:
    value = getattr(metric, name, None) if metric is not None else None
    if value is None or not math.isfinite(float(value)):
        return None
    return float(value)


def _best_row(
    rows: list[tuple[ResearchJobRun, BacktestRun | None, RunMetric | None]],
    metric_name: str,
) -> tuple[ResearchJobRun, BacktestRun, RunMetric] | None:
    candidates: list[
        tuple[float, int, ResearchJobRun, BacktestRun, RunMetric]
    ] = []
    for plan, run, metric in rows:
        value = _metric_value(metric, metric_name)
        if run is None or run.status != "SUCCEEDED" or metric is None or value is None:
            continue
        score = -value if metric_name in MINIMIZE_METRICS else value
        candidates.append((score, -int(plan.ordinal), plan, run, metric))
    if not candidates:
        return None
    _score, _ordinal, plan, run, metric = max(
        candidates,
        key=lambda item: (item[0], item[1]),
    )
    return plan, run, metric


def _grid_coordinates(spec: dict[str, Any]) -> tuple[list[str], dict[str, list[Any]]]:
    grid = spec.get("grid")
    if not grid:
        return [], {}
    parsed = ResearchSweepSpecIn.model_validate(
        {
            "grid": grid,
            "optimize_metric": spec.get("optimize_metric", "sharpe"),
        }
    )
    points = expand_sweep_grid(parsed, max_points=100_000)
    paths = [dimension.path.strip() for dimension in parsed.grid]
    values_by_path: dict[str, list[Any]] = {path: [] for path in paths}
    seen_by_path: dict[str, set[str]] = {path: set() for path in paths}
    for point in points:
        for path in paths:
            value = point[path]
            key = _json_key(value)
            if key not in seen_by_path[path]:
                seen_by_path[path].add(key)
                values_by_path[path].append(value)
    return paths, values_by_path


def _is_immediate_neighbor(
    best_params: dict[str, Any],
    candidate_params: dict[str, Any],
    paths: list[str],
    values_by_path: dict[str, list[Any]],
) -> bool:
    distance = 0
    for path in paths:
        indexes = {
            _json_key(value): index
            for index, value in enumerate(values_by_path[path])
        }
        best_key = _json_key(best_params.get(path))
        candidate_key = _json_key(candidate_params.get(path))
        if best_key not in indexes or candidate_key not in indexes:
            return False
        distance += abs(indexes[best_key] - indexes[candidate_key])
    return distance == 1


def _sensitivity_for_rows(
    rows: list[tuple[ResearchJobRun, BacktestRun | None, RunMetric | None]],
    *,
    metric_name: str,
    paths: list[str],
    values_by_path: dict[str, list[Any]],
) -> dict[str, Any]:
    best = _best_row(rows, metric_name)
    if best is None:
        return {
            "metric": metric_name,
            "reason": "No successful point has the optimization metric.",
            "neighbor_count": 0,
        }
    best_plan, _best_run, best_metric = best
    best_value = float(getattr(best_metric, metric_name))
    neighbor_values: list[float] = []
    for plan, run, metric in rows:
        if plan.job_run_id == best_plan.job_run_id or run is None:
            continue
        value = _metric_value(metric, metric_name)
        if value is None:
            continue
        if _is_immediate_neighbor(
            best_plan.params_json or {},
            plan.params_json or {},
            paths,
            values_by_path,
        ):
            neighbor_values.append(value)
    local_values = [best_value, *neighbor_values]
    value_range = (
        max(local_values) - min(local_values) if len(local_values) > 1 else None
    )
    standard_deviation = (
        float(np.std(np.asarray(local_values, dtype=np.float64)))
        if len(local_values) > 1
        else None
    )
    normalized_range = (
        value_range / max(abs(best_value), 1e-12)
        if value_range is not None
        else None
    )
    return {
        "metric": metric_name,
        "best_params": best_plan.params_json or {},
        "best_value": best_value,
        "neighbor_count": len(neighbor_values),
        "local_point_count": len(local_values),
        "std": standard_deviation,
        "range": value_range,
        "normalized_range": normalized_range,
        "plateau_score": (
            1.0 / (1.0 + normalized_range)
            if normalized_range is not None
            else None
        ),
        "reason": (
            None
            if neighbor_values
            else "The best point has no completed immediate grid neighbors."
        ),
    }


def _parameter_sensitivity(
    job: ResearchJob,
    rows: list[tuple[ResearchJobRun, BacktestRun | None, RunMetric | None]],
    metric_name: str,
) -> dict[str, Any] | None:
    paths, values_by_path = _grid_coordinates(job.spec or {})
    if not paths:
        return {
            "metric": metric_name,
            "reason": "This research job has no parameter grid.",
            "neighbor_count": 0,
        }
    if job.type == "WALK_FORWARD":
        segment_indexes = sorted(
            {
                int(plan.segment_index)
                for plan, _run, _metric in rows
                if plan.role == "TRAIN" and plan.segment_index is not None
            }
        )
        segments = []
        for segment_index in segment_indexes:
            segment_rows = [
                row
                for row in rows
                if row[0].role == "TRAIN"
                and row[0].segment_index == segment_index
            ]
            item = _sensitivity_for_rows(
                segment_rows,
                metric_name=metric_name,
                paths=paths,
                values_by_path=values_by_path,
            )
            item["segment_index"] = segment_index
            segments.append(item)
        plateau_scores = [
            float(item["plateau_score"])
            for item in segments
            if item.get("plateau_score") is not None
        ]
        std_values = [
            float(item["std"])
            for item in segments
            if item.get("std") is not None
        ]
        range_values = [
            float(item["range"])
            for item in segments
            if item.get("range") is not None
        ]
        return {
            "metric": metric_name,
            "segments": segments,
            "aggregate": {
                "segment_count": len(segments),
                "mean_plateau_score": (
                    float(np.mean(plateau_scores)) if plateau_scores else None
                ),
                "mean_std": float(np.mean(std_values)) if std_values else None,
                "mean_range": (
                    float(np.mean(range_values)) if range_values else None
                ),
            },
        }
    role = "IS" if job.type == "IS_OOS" else "SWEEP"
    return _sensitivity_for_rows(
        [row for row in rows if row[0].role == role],
        metric_name=metric_name,
        paths=paths,
        values_by_path=values_by_path,
    )


def _is_oos_degradation(
    job: ResearchJob,
    rows: list[tuple[ResearchJobRun, BacktestRun | None, RunMetric | None]],
) -> dict[str, Any] | None:
    if job.type != "IS_OOS":
        return None
    selected = next(
        (
            metric
            for plan, run, metric in rows
            if plan.role == "IS"
            and plan.is_selected
            and run is not None
            and run.status == "SUCCEEDED"
        ),
        None,
    )
    oos = next(
        (
            metric
            for plan, run, metric in rows
            if plan.role == "OOS"
            and run is not None
            and run.status == "SUCCEEDED"
        ),
        None,
    )
    if selected is None or oos is None:
        return {"reason": "Selected IS or successful OOS metrics are unavailable."}
    output: dict[str, Any] = {}
    for name in ("sharpe", "cagr"):
        source = _metric_value(selected, name)
        target = _metric_value(oos, name)
        output[name] = {
            "is": source,
            "oos": target,
            "ratio": (
                target / source
                if source is not None
                and target is not None
                and abs(source) > 1e-12
                else None
            ),
            "delta": (
                target - source
                if source is not None and target is not None
                else None
            ),
        }
    return output


def _monte_carlo_tail_from_equity(
    *,
    equity_values: list[float],
    initial_cash: float,
    seed: int,
    source: str,
    source_run_id: str | None,
    risk_free_rate_annual: float = 0.0,
) -> dict[str, Any]:
    try:
        returns = daily_returns_from_equity(equity_values, initial_cash)
        method = "block_bootstrap" if returns.size >= 5 else "bootstrap"
        block_len = min(5, int(returns.size))
        _identity, effective_seed = monte_carlo_identity(
            run_seed=seed,
            method=method,
            n=ROBUSTNESS_MONTE_CARLO_N,
            block_len=block_len if method == "block_bootstrap" else None,
        )
        result = simulate_daily_returns(
            returns,
            method=method,
            n=ROBUSTNESS_MONTE_CARLO_N,
            block_len=block_len,
            seed=effective_seed,
            risk_free_rate_annual=risk_free_rate_annual,
            plot_path_limit=0,
        )
    except ValueError as exc:
        return {
            "source": source,
            "source_run_id": source_run_id,
            "reason": str(exc),
        }
    return {
        "source": source,
        "source_run_id": source_run_id,
        "method": method,
        "n": ROBUSTNESS_MONTE_CARLO_N,
        "block_len": block_len if method == "block_bootstrap" else None,
        "seed": effective_seed,
        "terminal_return_p05": result["terminal_return"]["p05"],
        "probability_positive": result["probability_positive"],
        "drawdown_at_risk_95": result["drawdown_at_risk_95"],
    }


def _run_monte_carlo_tail(
    db: Session,
    plan_row: tuple[ResearchJobRun, BacktestRun, RunMetric],
) -> dict[str, Any]:
    _plan, run, metric = plan_row
    equity_rows = (
        db.query(RunDailyEquity)
        .filter(RunDailyEquity.run_id == run.run_id)
        .order_by(RunDailyEquity.date.asc())
        .all()
    )
    initial_cash = float((metric.meta or {}).get("initial_cash_base") or 0.0)
    return _monte_carlo_tail_from_equity(
        equity_values=[float(row.equity_base) for row in equity_rows],
        initial_cash=initial_cash,
        seed=run.seed,
        source="child_run",
        source_run_id=str(run.run_id),
        risk_free_rate_annual=float(
            (metric.meta or {}).get("risk_free_rate_annual") or 0.0
        ),
    )


def compute_research_robustness(
    db: Session,
    job: ResearchJob,
) -> tuple[dict[str, Any], datetime]:
    rows = (
        db.query(ResearchJobRun, BacktestRun, RunMetric)
        .outerjoin(BacktestRun, BacktestRun.run_id == ResearchJobRun.run_id)
        .outerjoin(RunMetric, RunMetric.run_id == BacktestRun.run_id)
        .filter(ResearchJobRun.job_id == job.job_id)
        .order_by(ResearchJobRun.ordinal.asc())
        .all()
    )
    metric_name = str((job.spec or {}).get("optimize_metric") or "sharpe")
    sensitivity = _parameter_sensitivity(job, rows, metric_name)
    degradation = _is_oos_degradation(job, rows)
    walk_forward_efficiency = None
    monte_carlo_tail: dict[str, Any] | None = None

    if job.type == "WALK_FORWARD":
        stitched = build_stitched_walk_forward_equity(db, job)
        walk_forward_efficiency = stitched.walk_forward_efficiency
        if stitched.starting_capital is not None:
            monte_carlo_tail = _monte_carlo_tail_from_equity(
                equity_values=stitched.values,
                initial_cash=stitched.starting_capital,
                seed=job.seed,
                source="stitched_walk_forward_oos",
                source_run_id=None,
            )
    else:
        candidate_rows = [
            row
            for row in rows
            if row[0].role == ("OOS" if job.type == "IS_OOS" else "SWEEP")
        ]
        best = _best_row(candidate_rows, metric_name)
        if best is not None:
            monte_carlo_tail = _run_monte_carlo_tail(db, best)

    trial_role = {
        "SWEEP": "SWEEP",
        "IS_OOS": "IS",
        "WALK_FORWARD": "TRAIN",
    }.get(job.type)
    trial_count = sum(1 for plan, _run, _metric in rows if plan.role == trial_role)
    computed_at = datetime.now(timezone.utc)
    summary = {
        "summary_version": ROBUSTNESS_SUMMARY_VERSION,
        "optimize_metric": metric_name,
        "sensitivity": sensitivity,
        "is_oos_degradation": degradation,
        "walk_forward_efficiency": walk_forward_efficiency,
        "monte_carlo_tail": monte_carlo_tail,
        "deflated_sharpe": {
            "value": None,
            "status": "not_implemented",
            "n_trials": trial_count,
        },
    }
    return summary, computed_at
