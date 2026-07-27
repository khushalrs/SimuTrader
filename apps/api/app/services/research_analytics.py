from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy.orm import Session

from app.models.backtests import BacktestRun, RunDailyEquity, RunMetric
from app.models.research import ResearchJob, ResearchJobRun


@dataclass(frozen=True)
class StitchedEquity:
    dates: list[date]
    values: list[float]
    starting_capital: float | None
    is_return: float | None
    oos_return: float | None
    walk_forward_efficiency: float | None


def build_stitched_walk_forward_equity(
    db: Session,
    job: ResearchJob,
) -> StitchedEquity:
    tests = (
        db.query(ResearchJobRun, BacktestRun, RunMetric)
        .join(BacktestRun, BacktestRun.run_id == ResearchJobRun.run_id)
        .outerjoin(RunMetric, RunMetric.run_id == BacktestRun.run_id)
        .filter(
            ResearchJobRun.job_id == job.job_id,
            ResearchJobRun.role == "TEST",
            BacktestRun.status == "SUCCEEDED",
        )
        .order_by(ResearchJobRun.segment_index.asc())
        .all()
    )
    stitched_values: list[float] = []
    stitched_dates: list[date] = []
    starting_capital: float | None = None
    current_capital: float | None = None
    for _plan, run, metrics in tests:
        equity = (
            db.query(RunDailyEquity)
            .filter(RunDailyEquity.run_id == run.run_id)
            .order_by(RunDailyEquity.date.asc())
            .all()
        )
        if not equity:
            continue
        segment_initial = float(
            (metrics.meta or {}).get("initial_cash_base")
            if metrics is not None
            and (metrics.meta or {}).get("initial_cash_base") is not None
            else equity[0].equity_base
        )
        if abs(segment_initial) <= 1e-12:
            continue
        if starting_capital is None:
            starting_capital = segment_initial
            current_capital = starting_capital
        segment_base = float(current_capital)
        for point in equity:
            stitched_dates.append(point.date)
            stitched_values.append(
                segment_base * float(point.equity_base) / segment_initial
            )
        current_capital = stitched_values[-1]

    selected_train_metrics = [
        metrics
        for _plan, _run, metrics in (
            db.query(ResearchJobRun, BacktestRun, RunMetric)
            .join(BacktestRun, BacktestRun.run_id == ResearchJobRun.run_id)
            .outerjoin(RunMetric, RunMetric.run_id == BacktestRun.run_id)
            .filter(
                ResearchJobRun.job_id == job.job_id,
                ResearchJobRun.role == "TRAIN",
                ResearchJobRun.is_selected.is_(True),
                BacktestRun.status == "SUCCEEDED",
            )
            .order_by(ResearchJobRun.segment_index.asc())
            .all()
        )
        if metrics is not None and metrics.net_return is not None
    ]
    is_growth = 1.0
    for metrics in selected_train_metrics:
        is_growth *= 1.0 + float(metrics.net_return)
    is_return = is_growth - 1.0 if selected_train_metrics else None
    oos_return = (
        stitched_values[-1] / float(starting_capital) - 1.0
        if stitched_values and starting_capital
        else None
    )
    efficiency = (
        oos_return / is_return
        if oos_return is not None
        and is_return is not None
        and abs(is_return) > 1e-12
        else None
    )
    return StitchedEquity(
        dates=stitched_dates,
        values=stitched_values,
        starting_capital=starting_capital,
        is_return=is_return,
        oos_return=oos_return,
        walk_forward_efficiency=efficiency,
    )
