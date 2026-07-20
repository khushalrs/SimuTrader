from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import Response

from app.api.routes import backtests as backtests_routes
from app.api.routes import runs as runs_routes
from app.schemas.backtests import RunScenarioRequest
from app.security import ActorContext, ActorTier
from app.services.scenario import build_clone_config, build_scenario_config


def _config() -> dict:
    return {
        "version": 1,
        "strategy": "BUY_AND_HOLD",
        "base_currency": "USD",
        "tax": {"regime": "NONE"},
        "universe": {
            "instruments": [
                {"symbol": "AAPL", "asset_class": "US_EQUITY", "amount": 9000.0}
            ]
        },
        "backtest": {
            "start_date": "2024-01-02",
            "end_date": "2024-02-02",
            "initial_cash": 10000.0,
        },
    }


def test_scenario_applies_dotted_patch_without_mutating_parent() -> None:
    parent_id = uuid4()
    original = _config()
    before = deepcopy(original)

    result = build_scenario_config(
        original,
        parent_id,
        {"tax.regime": "INDIA", "tax.india.short_rate": 0.25},
    )

    assert original == before
    assert result["tax"]["regime"] == "INDIA"
    assert result["tax"]["india"]["short_rate"] == pytest.approx(0.25)
    assert result["_scenario"] == {
        "parent_run_id": str(parent_id),
        "patch": {"tax.regime": "INDIA", "tax.india.short_rate": 0.25},
    }


def test_scenario_execution_cost_patch_updates_engine_fields() -> None:
    config = _config()
    config["commission"] = {"model": "BPS", "bps": 5, "min_fee_native": 1}
    config["slippage"] = {"model": "BPS", "bps": 2}

    result = build_scenario_config(
        config,
        uuid4(),
        {
            "execution.commission.bps": 500,
            "execution.slippage.bps": 125,
        },
    )

    assert result["commission"]["bps"] == pytest.approx(500)
    assert result["commission"]["min_fee_native"] == pytest.approx(1)
    assert result["slippage"]["bps"] == pytest.approx(125)


def test_clone_replaces_inherited_lineage_with_direct_parent() -> None:
    config = _config()
    config["_scenario"] = {"parent_run_id": str(uuid4()), "patch": {"tax.regime": "US"}}
    parent_id = uuid4()

    result = build_clone_config(config, parent_id)

    assert result["_scenario"] == {"parent_run_id": str(parent_id), "patch": {}}


def test_scenario_rejects_invalid_path_and_invalid_config() -> None:
    with pytest.raises(ValueError, match="not an object"):
        build_scenario_config(_config(), uuid4(), {"strategy.type": "DCA"})
    with pytest.raises(ValueError, match="Invalid config"):
        build_scenario_config(_config(), uuid4(), {"base_currency": "EUR"})


def test_scenario_route_uses_shared_dispatcher(monkeypatch) -> None:
    parent_id = uuid4()
    parent = SimpleNamespace(
        run_id=parent_id,
        name="Baseline",
        config_snapshot=_config(),
        data_snapshot_id="snapshot-1",
        seed=7,
        strategy_id=uuid4(),
    )
    actor = ActorContext(tier=ActorTier.GUEST, actor_key="guest:test")
    captured = {}

    monkeypatch.setattr(runs_routes, "_get_actor_run", lambda *_args: parent)

    def fake_dispatch(db, config, dispatch_actor, name, **kwargs):
        captured.update(
            db=db,
            config=config,
            actor=dispatch_actor,
            name=name,
            kwargs=kwargs,
        )
        return "dispatched"

    monkeypatch.setattr(backtests_routes, "_dispatch_run", fake_dispatch)
    result = runs_routes.create_run_scenario(
        run_id=parent_id,
        payload=RunScenarioRequest(name="India taxes", patch={"tax.regime": "INDIA"}),
        response=Response(),
        idempotency_key="scenario-key",
        reuse_succeeded_run=False,
        actor=actor,
        db=object(),
    )

    assert result == "dispatched"
    assert captured["name"] == "India taxes"
    assert captured["config"]["tax"]["regime"] == "INDIA"
    assert captured["config"]["_scenario"]["parent_run_id"] == str(parent_id)
    assert captured["kwargs"]["idempotency_key"] == "scenario-key"
    assert captured["kwargs"]["data_snapshot_id"] == "snapshot-1"
    assert captured["kwargs"]["seed"] == 7


def test_clone_route_accepts_no_body_and_records_empty_patch(monkeypatch) -> None:
    parent_id = uuid4()
    parent = SimpleNamespace(
        run_id=parent_id,
        name="Baseline",
        config_snapshot=_config(),
        data_snapshot_id="snapshot-1",
        seed=7,
        strategy_id=None,
    )
    actor = ActorContext(tier=ActorTier.GUEST, actor_key="guest:test")
    captured = {}
    monkeypatch.setattr(runs_routes, "_get_actor_run", lambda *_args: parent)

    def fake_dispatch(_db, config, _actor, name, **_kwargs):
        captured.update(config=config, name=name)
        return "cloned"

    monkeypatch.setattr(backtests_routes, "_dispatch_run", fake_dispatch)
    result = runs_routes.clone_run(
        run_id=parent_id,
        response=Response(),
        payload=None,
        idempotency_key=None,
        reuse_succeeded_run=False,
        actor=actor,
        db=object(),
    )

    assert result == "cloned"
    assert captured["name"] == "Baseline (Clone)"
    assert captured["config"]["_scenario"] == {
        "parent_run_id": str(parent_id),
        "patch": {},
    }
