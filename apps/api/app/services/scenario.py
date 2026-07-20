from __future__ import annotations

from copy import deepcopy
from typing import Any
from uuid import UUID

from app.services.config_validation import validate_and_resolve_config


def _apply_dotted_path(config: dict[str, Any], path: str, value: Any) -> None:
    parts = [part.strip() for part in str(path or "").split(".")]
    if not parts or any(not part for part in parts):
        raise ValueError(f"Invalid scenario patch path '{path}'.")
    cursor = config
    for part in parts[:-1]:
        existing = cursor.get(part)
        if existing is None:
            existing = {}
            cursor[part] = existing
        if not isinstance(existing, dict):
            raise ValueError(
                f"Cannot apply scenario patch '{path}': '{part}' is not an object."
            )
        cursor = existing
    cursor[parts[-1]] = deepcopy(value)


def build_scenario_config(
    config_snapshot: dict[str, Any],
    parent_run_id: UUID | str,
    patch: dict[str, Any],
) -> dict[str, Any]:
    """Apply dotted-path overrides, validate, and attach direct UI lineage."""
    if not isinstance(patch, dict):
        raise ValueError("Scenario patch must be an object.")
    config = deepcopy(config_snapshot or {})
    config.pop("_scenario", None)
    for path, value in patch.items():
        _apply_dotted_path(config, str(path), value)
    resolved = validate_and_resolve_config(config)
    resolved["_scenario"] = {
        "parent_run_id": str(parent_run_id),
        "patch": deepcopy(patch),
    }
    return resolved


def build_clone_config(
    config_snapshot: dict[str, Any], parent_run_id: UUID | str
) -> dict[str, Any]:
    return build_scenario_config(config_snapshot, parent_run_id, {})
