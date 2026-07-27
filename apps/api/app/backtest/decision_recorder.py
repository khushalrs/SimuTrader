"""Bounded, per-bar explainability capture for the backtest engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Protocol
from uuid import UUID, uuid4

from app.models.backtests import (
    RunConstraintEvent,
    RunOrderDecision,
    RunSignalSnapshot,
)

DEFAULT_MAX_EXPLAIN_RECORDS = 250_000
MAX_EXPLAIN_RECORDS_LIMIT = 1_000_000


@dataclass
class OrderDecisionDraft:
    symbol: str
    current_qty: float
    decision_id: UUID = field(default_factory=uuid4)
    order_id: UUID | None = None
    requested_target_weight: float | None = None
    target_weight: float | None = None
    target_qty: float | None = None
    delta_qty: float | None = None
    intended_side: str | None = None
    intended_qty: float | None = None
    executable_qty: float | None = None
    outcome: str = "PENDING"
    reason: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class ConstraintDraft:
    decision: OrderDecisionDraft
    constraint_name: str
    pre_clamp_value: float
    applied_value: float
    reason: str
    bound_value: float | None = None
    meta: dict[str, Any] = field(default_factory=dict)


class DecisionRecorder(Protocol):
    enabled: bool
    constraint_behavior: str
    truncated: bool
    signal_rows: list[RunSignalSnapshot]
    decision_rows: list[RunOrderDecision]
    constraint_rows: list[RunConstraintEvent]

    def begin_bar(self, bar_date: date, *, is_warmup: bool) -> None: ...

    def mark_decision_cycle(self, **meta: Any) -> None: ...

    def signal(
        self,
        symbol: str,
        signal_name: str,
        value: float,
        *,
        rank: int | None = None,
        selected: bool = False,
        meta: dict[str, Any] | None = None,
    ) -> None: ...

    def order_decision(self, **values: Any) -> OrderDecisionDraft | None: ...

    def constraint(
        self,
        decision: OrderDecisionDraft | None,
        constraint_name: str,
        *,
        pre_clamp_value: float,
        applied_value: float,
        reason: str,
        bound_value: float | None = None,
        meta: dict[str, Any] | None = None,
    ) -> None: ...

    def finish_bar(self) -> None: ...


class NullDecisionRecorder:
    enabled = False
    constraint_behavior = "FAIL"

    def __init__(self) -> None:
        self.truncated = False
        self.signal_rows: list[RunSignalSnapshot] = []
        self.decision_rows: list[RunOrderDecision] = []
        self.constraint_rows: list[RunConstraintEvent] = []

    def begin_bar(self, bar_date: date, *, is_warmup: bool) -> None:
        return None

    def mark_decision_cycle(self, **meta: Any) -> None:
        return None

    def signal(
        self,
        symbol: str,
        signal_name: str,
        value: float,
        *,
        rank: int | None = None,
        selected: bool = False,
        meta: dict[str, Any] | None = None,
    ) -> None:
        return None

    def order_decision(self, **values: Any) -> None:
        return None

    def constraint(
        self,
        decision: OrderDecisionDraft | None,
        constraint_name: str,
        *,
        pre_clamp_value: float,
        applied_value: float,
        reason: str,
        bound_value: float | None = None,
        meta: dict[str, Any] | None = None,
    ) -> None:
        return None

    def finish_bar(self) -> None:
        return None


class BufferedDecisionRecorder:
    enabled = True

    def __init__(
        self,
        run_id: UUID,
        *,
        capture: str = "REBALANCE_ONLY",
        max_records: int = DEFAULT_MAX_EXPLAIN_RECORDS,
        constraint_behavior: str = "RECORD_AND_CLAMP",
    ) -> None:
        self.run_id = run_id
        self.capture = capture
        self.constraint_behavior = constraint_behavior
        self.max_records = min(
            max(int(max_records), 1),
            MAX_EXPLAIN_RECORDS_LIMIT,
        )
        self.signal_rows: list[RunSignalSnapshot] = []
        self.decision_rows: list[RunOrderDecision] = []
        self.constraint_rows: list[RunConstraintEvent] = []
        self.truncated = False
        self._date: date | None = None
        self._is_warmup = False
        self._decision_cycle = False
        self._cycle_meta: dict[str, Any] = {}
        self._bar_signals: list[dict[str, Any]] = []
        self._bar_decisions: list[OrderDecisionDraft] = []
        self._bar_constraints: list[ConstraintDraft] = []

    def begin_bar(self, bar_date: date, *, is_warmup: bool) -> None:
        self._date = bar_date
        self._is_warmup = is_warmup
        self._decision_cycle = False
        self._cycle_meta = {}
        self._bar_signals = []
        self._bar_decisions = []
        self._bar_constraints = []

    def mark_decision_cycle(self, **meta: Any) -> None:
        self._decision_cycle = True
        self._cycle_meta.update(meta)

    def signal(
        self,
        symbol: str,
        signal_name: str,
        value: float,
        *,
        rank: int | None = None,
        selected: bool = False,
        meta: dict[str, Any] | None = None,
    ) -> None:
        if self.truncated or self._is_warmup:
            return
        self._bar_signals.append(
            {
                "symbol": symbol,
                "signal_name": signal_name,
                "value": float(value),
                "rank": rank,
                "selected": bool(selected),
                "meta": dict(meta or {}),
            }
        )

    def order_decision(self, **values: Any) -> OrderDecisionDraft | None:
        if self.truncated or self._is_warmup:
            return None
        draft = OrderDecisionDraft(**values)
        self._bar_decisions.append(draft)
        return draft

    def constraint(
        self,
        decision: OrderDecisionDraft | None,
        constraint_name: str,
        *,
        pre_clamp_value: float,
        applied_value: float,
        reason: str,
        bound_value: float | None = None,
        meta: dict[str, Any] | None = None,
    ) -> None:
        if (
            decision is None
            or self.truncated
            or self._is_warmup
        ):
            return
        self._bar_constraints.append(
            ConstraintDraft(
                decision=decision,
                constraint_name=constraint_name,
                bound_value=bound_value,
                pre_clamp_value=float(pre_clamp_value),
                applied_value=float(applied_value),
                reason=reason,
                meta=dict(meta or {}),
            )
        )

    def finish_bar(self) -> None:
        if self._date is None:
            return
        should_keep = (
            not self._is_warmup
            and (
                self.capture == "ALL_BARS"
                or self._decision_cycle
                or bool(self._bar_decisions)
            )
        )
        if should_keep and not self.truncated:
            cycle_meta = dict(self._cycle_meta)
            for signal in self._bar_signals:
                if not self._reserve_record():
                    break
                signal_meta = {**cycle_meta, **signal["meta"]}
                self.signal_rows.append(
                    RunSignalSnapshot(
                        signal_id=uuid4(),
                        run_id=self.run_id,
                        date=self._date,
                        symbol=signal["symbol"],
                        signal_name=signal["signal_name"],
                        value=signal["value"],
                        rank=signal["rank"],
                        selected=signal["selected"],
                        meta=signal_meta,
                    )
                )
            for decision in self._bar_decisions:
                if not self._reserve_record():
                    break
                self.decision_rows.append(
                    RunOrderDecision(
                        decision_id=decision.decision_id,
                        order_id=decision.order_id,
                        run_id=self.run_id,
                        date=self._date,
                        symbol=decision.symbol,
                        requested_target_weight=decision.requested_target_weight,
                        target_weight=decision.target_weight,
                        target_qty=decision.target_qty,
                        current_qty=decision.current_qty,
                        delta_qty=decision.delta_qty,
                        intended_side=decision.intended_side,
                        intended_qty=decision.intended_qty,
                        executable_qty=decision.executable_qty,
                        outcome=decision.outcome,
                        reason=decision.reason,
                        meta={**cycle_meta, **decision.meta},
                    )
                )
            persisted_decision_ids = {
                row.decision_id for row in self.decision_rows
            }
            for constraint in self._bar_constraints:
                if constraint.decision.decision_id not in persisted_decision_ids:
                    continue
                if not self._reserve_record():
                    break
                self.constraint_rows.append(
                    RunConstraintEvent(
                        constraint_id=uuid4(),
                        decision_id=constraint.decision.decision_id,
                        run_id=self.run_id,
                        date=self._date,
                        symbol=constraint.decision.symbol,
                        constraint_name=constraint.constraint_name,
                        bound_value=constraint.bound_value,
                        pre_clamp_value=constraint.pre_clamp_value,
                        applied_value=constraint.applied_value,
                        reason=constraint.reason,
                        meta={**cycle_meta, **constraint.meta},
                    )
                )
        self._date = None
        self._bar_signals = []
        self._bar_decisions = []
        self._bar_constraints = []

    def _reserve_record(self) -> bool:
        count = (
            len(self.signal_rows)
            + len(self.decision_rows)
            + len(self.constraint_rows)
        )
        if count >= self.max_records:
            self.truncated = True
            return False
        return True


def build_decision_recorder(
    run_id: UUID,
    explain_config: bool | dict[str, Any] | None,
) -> DecisionRecorder:
    if explain_config is True:
        return BufferedDecisionRecorder(run_id)
    if not isinstance(explain_config, dict) or not explain_config.get("enabled", False):
        return NullDecisionRecorder()
    capture = str(
        explain_config.get("capture") or "REBALANCE_ONLY"
    ).upper()
    if capture not in {"REBALANCE_ONLY", "ALL_BARS"}:
        capture = "REBALANCE_ONLY"
    constraint_behavior = str(
        explain_config.get("constraint_behavior") or "RECORD_AND_CLAMP"
    ).upper()
    if constraint_behavior not in {"FAIL", "RECORD_AND_CLAMP"}:
        constraint_behavior = "FAIL"
    return BufferedDecisionRecorder(
        run_id,
        capture=capture,
        constraint_behavior=constraint_behavior,
        max_records=int(
            explain_config.get("max_records") or DEFAULT_MAX_EXPLAIN_RECORDS
        ),
    )
