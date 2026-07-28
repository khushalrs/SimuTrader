from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from hashlib import sha256
from itertools import product
from typing import Any

from app.schemas.research import ResearchRangeSpec, ResearchSweepSpecIn
from app.services.config_paths import validate_sweep_path
from app.services.scenario import build_scenario_config


@dataclass(frozen=True)
class SweepPlan:
    ordinal: int
    params: dict[str, Any]
    config: dict[str, Any]
    config_hash: str


@dataclass(frozen=True)
class EvaluationWindow:
    start_date: date
    evaluation_start_date: date
    end_date: date


@dataclass(frozen=True)
class WalkForwardSegment:
    index: int
    train: EvaluationWindow
    test: EvaluationWindow


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )


def config_identity_hash(config: dict, data_snapshot_id: str, seed: int) -> str:
    identity = {
        "config": config,
        "data_snapshot_id": data_snapshot_id,
        "seed": seed,
    }
    return sha256(_canonical_json(identity).encode("utf-8")).hexdigest()


def _expand_range(spec: ResearchRangeSpec) -> list[float]:
    minimum = Decimal(str(spec.min_value))
    maximum = Decimal(str(spec.max_value))
    count = spec.count or spec.linspace
    if count is not None:
        if count == 2:
            return [float(minimum), float(maximum)]
        distance = maximum - minimum
        return [
            float(minimum + distance * Decimal(index) / Decimal(count - 1))
            for index in range(count)
        ]

    step = Decimal(str(spec.step))
    values: list[float] = []
    current = minimum
    while current <= maximum:
        values.append(float(current))
        current += step
        if len(values) > 100_000:
            raise ValueError("range expansion is too large")
    return values


def _deduplicate_values(values: list[Any]) -> list[Any]:
    unique: list[Any] = []
    seen: set[str] = set()
    for value in values:
        try:
            key = _canonical_json(value)
        except (TypeError, ValueError) as exc:
            raise ValueError("grid values must be valid finite JSON values") from exc
        if key not in seen:
            seen.add(key)
            unique.append(value)
    return unique


def expand_sweep_grid(
    spec: ResearchSweepSpecIn,
    *,
    max_points: int,
    base_config: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    strategy: str | None = None
    if base_config is not None:
        raw_strategy = base_config.get("strategy")
        strategy = (
            str(raw_strategy.get("type"))
            if isinstance(raw_strategy, dict) and raw_strategy.get("type")
            else str(raw_strategy or "")
        ) or "BUY_AND_HOLD"

    paths: list[str] = []
    canonical_paths: list[str] = []
    expanded_values: list[list[Any]] = []
    for dimension in spec.grid:
        requested_path = dimension.path.strip()
        if not requested_path or requested_path.startswith("_"):
            raise ValueError(f"Invalid research grid path '{dimension.path}'.")
        canonical_path = (
            validate_sweep_path(requested_path, strategy=strategy)
            if base_config is not None
            else requested_path
        )
        if canonical_path in canonical_paths:
            raise ValueError(
                f"Duplicate research grid path '{requested_path}' "
                f"(canonical path '{canonical_path}')."
            )
        canonical_paths.append(canonical_path)
        paths.append(requested_path)
        raw_values = (
            _expand_range(dimension.values)
            if isinstance(dimension.values, ResearchRangeSpec)
            else list(dimension.values)
        )
        values = _deduplicate_values(raw_values)
        if not values:
            raise ValueError(f"Research grid path '{requested_path}' has no values.")
        expanded_values.append(values)

    point_count = 1
    for values in expanded_values:
        point_count *= len(values)
        if point_count > max_points:
            raise ValueError(
                f"Research grid expands to {point_count} points; cap is {max_points}."
            )
    return [
        dict(zip(paths, combination))
        for combination in product(*expanded_values)
    ]


def build_sweep_plans(
    *,
    base_config: dict,
    base_run_id,
    spec: ResearchSweepSpecIn,
    data_snapshot_id: str,
    seed: int,
    max_points: int,
) -> list[SweepPlan]:
    patches = expand_sweep_grid(
        spec,
        max_points=max_points,
        base_config=base_config,
    )
    plans: list[SweepPlan] = []
    seen_hashes: set[str] = set()
    for patch in patches:
        config = build_scenario_config(base_config, base_run_id, patch)
        config_hash = config_identity_hash(config, data_snapshot_id, seed)
        if config_hash in seen_hashes:
            continue
        seen_hashes.add(config_hash)
        plans.append(
            SweepPlan(
                ordinal=len(plans),
                params=patch,
                config=config,
                config_hash=config_hash,
            )
        )
    if not plans:
        raise ValueError("Research grid did not produce any distinct configurations.")
    return plans


def split_evaluation_windows(
    dates: list[date],
    split_pct: float,
) -> tuple[EvaluationWindow, EvaluationWindow]:
    ordered_dates = sorted(set(dates))
    if len(ordered_dates) < 4:
        raise ValueError("IS/OOS research requires at least four equity observations.")
    split_index = int(len(ordered_dates) * split_pct)
    split_index = max(2, min(split_index, len(ordered_dates) - 2))
    is_dates = ordered_dates[:split_index]
    oos_dates = ordered_dates[split_index:]
    return (
        EvaluationWindow(is_dates[0], is_dates[0], is_dates[-1]),
        EvaluationWindow(ordered_dates[0], oos_dates[0], oos_dates[-1]),
    )


def generate_walk_forward_segments(
    dates: list[date],
    *,
    train_len: int,
    test_len: int,
    step: int,
    mode: str,
) -> list[WalkForwardSegment]:
    if step != test_len:
        raise ValueError(
            "walk-forward step must equal test_len so OOS segments do not overlap or gap"
        )
    ordered_dates = sorted(set(dates))
    segments: list[WalkForwardSegment] = []
    offset = 0
    while True:
        train_start_index = 0 if mode == "anchored" else offset
        train_end_index = offset + train_len - 1
        test_start_index = train_end_index + 1
        test_end_index = test_start_index + test_len - 1
        if test_end_index >= len(ordered_dates):
            break
        train_start = ordered_dates[train_start_index]
        train_end = ordered_dates[train_end_index]
        test_start = ordered_dates[test_start_index]
        test_end = ordered_dates[test_end_index]
        segments.append(
            WalkForwardSegment(
                index=len(segments),
                train=EvaluationWindow(train_start, train_start, train_end),
                test=EvaluationWindow(train_start, test_start, test_end),
            )
        )
        offset += step
    if not segments:
        required = train_len + test_len
        raise ValueError(
            "Walk-forward research has no complete segment; "
            f"at least {required} equity observations are required."
        )
    return segments


def build_windowed_plan(
    *,
    base_config: dict,
    base_run_id,
    params: dict[str, Any],
    window: EvaluationWindow,
    data_snapshot_id: str,
    seed: int,
    ordinal: int,
) -> SweepPlan:
    patch = {
        **params,
        "backtest.start_date": window.start_date.isoformat(),
        "backtest.evaluation_start_date": window.evaluation_start_date.isoformat(),
        "backtest.end_date": window.end_date.isoformat(),
    }
    config = build_scenario_config(base_config, base_run_id, patch)
    return SweepPlan(
        ordinal=ordinal,
        params=dict(params),
        config=config,
        config_hash=config_identity_hash(config, data_snapshot_id, seed),
    )
