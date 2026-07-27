from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest

from app.backtest.decision_recorder import (
    BufferedDecisionRecorder,
    NullDecisionRecorder,
    build_decision_recorder,
)
from app.backtest.engine import (
    FinancingSpec,
    PortfolioState,
    PositionState,
    RiskSpec,
    _clamp_target_weights,
    _targets_to_orders,
)


def test_recorder_defaults_to_noop_and_true_uses_rebalance_capture() -> None:
    assert isinstance(build_decision_recorder(uuid4(), None), NullDecisionRecorder)

    recorder = build_decision_recorder(uuid4(), True)
    assert isinstance(recorder, BufferedDecisionRecorder)
    assert recorder.capture == "REBALANCE_ONLY"


def test_rebalance_capture_discards_unmarked_bar_and_keeps_marked_records() -> None:
    recorder = BufferedDecisionRecorder(uuid4(), max_records=10)

    recorder.begin_bar(date(2024, 1, 2), is_warmup=False)
    recorder.signal("AAPL", "momentum_return", 0.1)
    recorder.finish_bar()
    assert recorder.signal_rows == []

    recorder.begin_bar(date(2024, 1, 3), is_warmup=False)
    recorder.mark_decision_cycle(strategy="MOMENTUM")
    recorder.signal(
        "AAPL",
        "momentum_return",
        0.2,
        rank=1,
        selected=True,
    )
    decision = recorder.order_decision(
        symbol="AAPL",
        requested_target_weight=1.0,
        target_weight=0.99,
        target_qty=10.0,
        current_qty=0.0,
        delta_qty=10.0,
        intended_side="BUY",
        intended_qty=10.0,
        executable_qty=None,
        outcome="PENDING",
        reason=None,
        meta={"adjustments": ["TRIMMED_CASH_BUFFER"]},
    )
    assert decision is not None
    decision.outcome = "TRIMMED_CASH_BUFFER"
    decision.executable_qty = 10.0
    recorder.constraint(
        decision,
        "cash_buffer",
        bound_value=0.01,
        pre_clamp_value=1.0,
        applied_value=0.99,
        reason="Cash buffer reduced the target.",
    )
    recorder.finish_bar()

    assert len(recorder.signal_rows) == 1
    assert recorder.signal_rows[0].meta["strategy"] == "MOMENTUM"
    assert len(recorder.decision_rows) == 1
    assert recorder.decision_rows[0].outcome == "TRIMMED_CASH_BUFFER"
    assert len(recorder.constraint_rows) == 1
    assert (
        recorder.constraint_rows[0].decision_id
        == recorder.decision_rows[0].decision_id
    )


def test_recorder_ignores_warmup_and_enforces_hard_record_cap() -> None:
    recorder = BufferedDecisionRecorder(uuid4(), max_records=1)
    recorder.begin_bar(date(2024, 1, 2), is_warmup=True)
    recorder.mark_decision_cycle()
    recorder.signal("AAPL", "signal", 1.0)
    recorder.finish_bar()
    assert recorder.signal_rows == []

    recorder.begin_bar(date(2024, 1, 3), is_warmup=False)
    recorder.mark_decision_cycle()
    recorder.signal("AAPL", "signal", 1.0)
    recorder.signal("MSFT", "signal", 2.0)
    recorder.finish_bar()

    assert len(recorder.signal_rows) == 1
    assert recorder.truncated is True


def test_order_planner_records_non_filled_decision_outcomes() -> None:
    recorder = BufferedDecisionRecorder(uuid4(), max_records=10)
    recorder.begin_bar(date(2024, 1, 2), is_warmup=False)
    recorder.mark_decision_cycle()
    state = PortfolioState(
        cash_by_currency={"USD": 1_000.0},
        positions={
            "CLOSED": PositionState(),
            "NO_PRICE": PositionState(),
            "UNCHANGED": PositionState(qty=10.0),
        },
        last_price={},
    )

    orders = _targets_to_orders(
        state,
        {
            "CLOSED": 100.0,
            "NO_PRICE": 100.0,
            "UNCHANGED": 1_000.0,
        },
        {"CLOSED": None, "NO_PRICE": None, "UNCHANGED": 100.0},
        {"CLOSED": False, "NO_PRICE": True, "UNCHANGED": True},
        recorder=recorder,
    )
    recorder.finish_bar()

    assert orders == []
    assert [row.outcome for row in recorder.decision_rows] == [
        "SKIPPED_MARKET_CLOSED",
        "SKIPPED_NO_PRICE",
        "HELD_NO_CHANGE",
    ]


def test_target_weight_clamping_records_each_binding_risk_bound() -> None:
    applied, constraints = _clamp_target_weights(
        {"AAPL": 0.8, "MSFT": 0.2},
        RiskSpec(
            max_gross_leverage=0.7,
            max_net_leverage=0.5,
            max_weight=0.6,
        ),
        FinancingSpec(
            margin_enabled=False,
            max_leverage=1.0,
            daily_margin_interest_bps=0.0,
            shorting_enabled=False,
            daily_borrow_fee_bps=0.0,
        ),
    )

    assert sum(abs(value) for value in applied.values()) == pytest.approx(0.5)
    assert max(abs(value) for value in applied.values()) <= 0.6
    assert {constraint.constraint_name for constraint in constraints} == {
        "max_weight",
        "max_gross",
        "max_net",
    }
