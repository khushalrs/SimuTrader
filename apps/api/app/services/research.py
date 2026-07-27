from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from hashlib import sha256
from itertools import product
import json
from typing import Any

from app.schemas.research import ResearchRangeSpec, ResearchSweepSpecIn
from app.services.scenario import build_scenario_config


@dataclass(frozen=True)
class SweepPlan:
    ordinal: int
    params: dict[str, Any]
    config: dict[str, Any]
    config_hash: str


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
) -> list[dict[str, Any]]:
    paths: list[str] = []
    expanded_values: list[list[Any]] = []
    for dimension in spec.grid:
        path = dimension.path.strip()
        if not path or path.startswith("_"):
            raise ValueError(f"Invalid research grid path '{dimension.path}'.")
        if path in paths:
            raise ValueError(f"Duplicate research grid path '{path}'.")
        paths.append(path)
        raw_values = (
            _expand_range(dimension.values)
            if isinstance(dimension.values, ResearchRangeSpec)
            else list(dimension.values)
        )
        values = _deduplicate_values(raw_values)
        if not values:
            raise ValueError(f"Research grid path '{path}' has no values.")
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
    patches = expand_sweep_grid(spec, max_points=max_points)
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
