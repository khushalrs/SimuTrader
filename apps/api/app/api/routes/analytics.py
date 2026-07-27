from __future__ import annotations

from collections import defaultdict
from datetime import date
from math import sqrt
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.routes.runs import _get_actor_run, _is_terminal_status
from app.db import get_db
from app.models.backtests import RunDailyEquity, RunMetric, RunPosition
from app.schemas.backtests import (
    RunAnnualReturnOut,
    RunBenchmarkPointOut,
    RunCostAttributionOut,
    RunCostWaterfallItemOut,
    RunMonthlyReturnOut,
    RunPeriodicReturnsOut,
    RunPeriodReturnSummaryOut,
    RunReturnAttributionRowOut,
    RunRollingMetaOut,
    RunRollingOut,
    RunRollingPointOut,
)
from app.security import ActorContext, get_current_actor

router = APIRouter(prefix="/runs", tags=["run analytics"])

_ALLOWED_WINDOWS = {21, 63, 126, 252}
_ALLOWED_ROLLING_METRICS = {"sharpe", "vol", "beta"}


def _equity_rows(run_id: UUID, db: Session) -> list[RunDailyEquity]:
    return (
        db.query(RunDailyEquity)
        .filter(RunDailyEquity.run_id == run_id)
        .order_by(RunDailyEquity.date.asc())
        .all()
    )


def _initial_capital_base(
    run,
    rows: list[RunDailyEquity],
    metrics: RunMetric | None,
) -> float:
    meta_value = (metrics.meta or {}).get("initial_cash_base") if metrics else None
    if meta_value is not None and float(meta_value) > 0.0:
        return float(meta_value)

    config = run.config_snapshot or {}
    backtest = config.get("backtest") or {}
    if not backtest.get("initial_cash_by_currency"):
        configured = backtest.get("initial_cash")
        if configured is not None and float(configured) > 0.0:
            return float(configured)

    if not rows:
        return 0.0
    first = rows[0]
    # Existing mixed-currency runs did not persist their converted initial capital.
    # Adding back first-day costs is the closest reproducible stored approximation.
    return float(first.equity_base) + sum(
        float(value or 0.0)
        for value in (
            first.fees_cum_base,
            first.taxes_cum_base,
            first.borrow_fees_cum_base,
            first.margin_interest_cum_base,
        )
    )


def _safe_return(end_value: float | None, start_value: float | None) -> float | None:
    if end_value is None or start_value is None or abs(start_value) <= 1e-12:
        return None
    return end_value / start_value - 1.0


def _sample_std(values: list[float]) -> float | None:
    if len(values) < 2:
        return None
    mean_value = sum(values) / len(values)
    return sqrt(
        sum((value - mean_value) ** 2 for value in values) / (len(values) - 1)
    )


@router.get("/{run_id}/benchmark", response_model=list[RunBenchmarkPointOut])
def get_run_benchmark(
    run_id: UUID,
    actor: ActorContext = Depends(get_current_actor),
    db: Session = Depends(get_db),
) -> list[RunBenchmarkPointOut]:
    run = _get_actor_run(run_id, actor, db)
    if not _is_terminal_status(run.status) or not (run.config_snapshot or {}).get(
        "benchmark"
    ):
        return []
    rows = _equity_rows(run_id, db)
    benchmark_rows = [
        row for row in rows if row.benchmark_equity_base is not None
    ]
    if not benchmark_rows:
        return []
    initial = float(benchmark_rows[0].benchmark_equity_base)
    return [
        RunBenchmarkPointOut(
            date=row.date,
            benchmark_equity_base=float(row.benchmark_equity_base),
            benchmark_return=float(row.benchmark_equity_base) / initial - 1.0,
        )
        for row in benchmark_rows
        if abs(initial) > 1e-12
    ]


def _period_boundaries(
    rows: list[RunDailyEquity],
    key_fn,
) -> list[RunDailyEquity]:
    latest: dict[object, RunDailyEquity] = {}
    for row in rows:
        latest[key_fn(row.date)] = row
    return [latest[key] for key in sorted(latest)]


@router.get(
    "/{run_id}/returns/periodic",
    response_model=RunPeriodicReturnsOut,
)
def get_run_periodic_returns(
    run_id: UUID,
    freq: str = Query(default="monthly", pattern="^(monthly|annual)$"),
    actor: ActorContext = Depends(get_current_actor),
    db: Session = Depends(get_db),
) -> RunPeriodicReturnsOut:
    run = _get_actor_run(run_id, actor, db)
    rows = _equity_rows(run_id, db) if _is_terminal_status(run.status) else []
    metrics = (
        db.query(RunMetric).filter(RunMetric.run_id == run_id).first()
        if rows
        else None
    )
    if not rows:
        empty = RunPeriodReturnSummaryOut(return_value=None)
        return RunPeriodicReturnsOut(
            monthly=[],
            annual=[],
            ytd=empty,
            full_period=empty,
        )

    initial_capital = _initial_capital_base(run, rows, metrics)
    first_benchmark = next(
        (
            float(row.benchmark_equity_base)
            for row in rows
            if row.benchmark_equity_base is not None
        ),
        None,
    )
    month_ends = _period_boundaries(rows, lambda value: (value.year, value.month))
    year_ends = _period_boundaries(rows, lambda value: value.year)

    monthly: list[RunMonthlyReturnOut] = []
    prior_equity = initial_capital
    prior_benchmark = first_benchmark
    for row in month_ends:
        benchmark_value = (
            float(row.benchmark_equity_base)
            if row.benchmark_equity_base is not None
            else None
        )
        monthly.append(
            RunMonthlyReturnOut(
                year=row.date.year,
                month=row.date.month,
                return_value=_safe_return(float(row.equity_base), prior_equity) or 0.0,
                benchmark_return=_safe_return(benchmark_value, prior_benchmark),
            )
        )
        prior_equity = float(row.equity_base)
        if benchmark_value is not None:
            prior_benchmark = benchmark_value

    annual: list[RunAnnualReturnOut] = []
    prior_equity = initial_capital
    prior_benchmark = first_benchmark
    for row in year_ends:
        benchmark_value = (
            float(row.benchmark_equity_base)
            if row.benchmark_equity_base is not None
            else None
        )
        annual.append(
            RunAnnualReturnOut(
                year=row.date.year,
                return_value=_safe_return(float(row.equity_base), prior_equity) or 0.0,
                benchmark_return=_safe_return(benchmark_value, prior_benchmark),
            )
        )
        prior_equity = float(row.equity_base)
        if benchmark_value is not None:
            prior_benchmark = benchmark_value

    final = rows[-1]
    prior_year_rows = [row for row in rows if row.date.year < final.date.year]
    ytd_base_equity = (
        float(prior_year_rows[-1].equity_base)
        if prior_year_rows
        else initial_capital
    )
    ytd_base_benchmark = (
        next(
            (
                float(row.benchmark_equity_base)
                for row in reversed(prior_year_rows)
                if row.benchmark_equity_base is not None
            ),
            first_benchmark,
        )
        if first_benchmark is not None
        else None
    )
    final_benchmark = (
        float(final.benchmark_equity_base)
        if final.benchmark_equity_base is not None
        else None
    )
    return RunPeriodicReturnsOut(
        monthly=monthly if freq == "monthly" else [],
        annual=annual if freq == "annual" else [],
        ytd=RunPeriodReturnSummaryOut(
            return_value=_safe_return(float(final.equity_base), ytd_base_equity),
            benchmark_return=_safe_return(final_benchmark, ytd_base_benchmark),
        ),
        full_period=RunPeriodReturnSummaryOut(
            return_value=_safe_return(float(final.equity_base), initial_capital),
            benchmark_return=_safe_return(final_benchmark, first_benchmark),
        ),
    )


@router.get("/{run_id}/rolling", response_model=RunRollingOut)
def get_run_rolling_metrics(
    run_id: UUID,
    window: int = 63,
    metrics: str = Query(default="sharpe,vol,beta"),
    actor: ActorContext = Depends(get_current_actor),
    db: Session = Depends(get_db),
) -> RunRollingOut:
    run = _get_actor_run(run_id, actor, db)
    if window not in _ALLOWED_WINDOWS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"window must be one of {sorted(_ALLOWED_WINDOWS)}",
        )
    requested = [item.strip().lower() for item in metrics.split(",") if item.strip()]
    unknown = sorted(set(requested) - _ALLOWED_ROLLING_METRICS)
    if not requested or unknown:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"metrics must contain values from {sorted(_ALLOWED_ROLLING_METRICS)}"
                + (f"; unknown values: {unknown}" if unknown else "")
            ),
        )
    requested = list(dict.fromkeys(requested))
    rows = _equity_rows(run_id, db) if _is_terminal_status(run.status) else []
    meta = RunRollingMetaOut(
        window=window,
        metrics=requested,
        required_observations=window + 1,
        available_observations=len(rows),
        reason=None,
    )
    if len(rows) < window + 1:
        meta.reason = "insufficient_observations"
        return RunRollingOut(data=[], meta=meta)

    portfolio_returns = [
        float(current.equity_base) / float(previous.equity_base) - 1.0
        for previous, current in zip(rows[:-1], rows[1:])
    ]
    benchmark_returns: list[float | None] = []
    for previous, current in zip(rows[:-1], rows[1:]):
        previous_value = previous.benchmark_equity_base
        current_value = current.benchmark_equity_base
        benchmark_returns.append(
            (
                float(current_value) / float(previous_value) - 1.0
                if previous_value is not None
                and current_value is not None
                and abs(float(previous_value)) > 1e-12
                else None
            )
        )

    risk_free_annual = float(
        ((run.config_snapshot or {}).get("risk") or {}).get(
            "risk_free_rate_annual", 0.0
        )
        or 0.0
    )
    risk_free_daily = (1.0 + risk_free_annual) ** (1.0 / 252.0) - 1.0
    result: list[RunRollingPointOut] = []
    for end_index in range(window - 1, len(portfolio_returns)):
        portfolio_window = portfolio_returns[end_index - window + 1 : end_index + 1]
        std_daily = _sample_std(portfolio_window)
        volatility = std_daily * sqrt(252.0) if std_daily is not None else None
        sharpe = (
            (
                sum(value - risk_free_daily for value in portfolio_window)
                / len(portfolio_window)
                * 252.0
            )
            / volatility
            if volatility is not None and volatility > 0.0
            else None
        )
        beta = None
        benchmark_window = benchmark_returns[
            end_index - window + 1 : end_index + 1
        ]
        if all(value is not None for value in benchmark_window):
            benchmark_values = [float(value) for value in benchmark_window]
            benchmark_mean = sum(benchmark_values) / len(benchmark_values)
            portfolio_mean = sum(portfolio_window) / len(portfolio_window)
            variance = sum(
                (value - benchmark_mean) ** 2 for value in benchmark_values
            ) / (len(benchmark_values) - 1)
            if variance > 0.0:
                covariance = sum(
                    (portfolio - portfolio_mean) * (benchmark - benchmark_mean)
                    for portfolio, benchmark in zip(
                        portfolio_window, benchmark_values
                    )
                ) / (len(portfolio_window) - 1)
                beta = covariance / variance
        result.append(
            RunRollingPointOut(
                date=rows[end_index + 1].date,
                sharpe=sharpe if "sharpe" in requested else None,
                volatility=volatility if "vol" in requested else None,
                beta=beta if "beta" in requested else None,
            )
        )
    return RunRollingOut(data=result, meta=meta)


@router.get(
    "/{run_id}/attribution/returns",
    response_model=list[RunReturnAttributionRowOut],
)
def get_run_return_attribution(
    run_id: UUID,
    actor: ActorContext = Depends(get_current_actor),
    db: Session = Depends(get_db),
) -> list[RunReturnAttributionRowOut]:
    run = _get_actor_run(run_id, actor, db)
    rows = _equity_rows(run_id, db) if _is_terminal_status(run.status) else []
    if len(rows) < 2:
        return []
    metrics = db.query(RunMetric).filter(RunMetric.run_id == run_id).first()
    initial_capital = _initial_capital_base(run, rows, metrics)
    positions = (
        db.query(RunPosition)
        .filter(RunPosition.run_id == run_id)
        .order_by(RunPosition.date.asc(), RunPosition.symbol.asc())
        .all()
    )
    positions_by_date: dict[date, dict[str, RunPosition]] = defaultdict(dict)
    all_symbols: set[str] = set()
    price_observations: dict[str, list[float]] = defaultdict(list)
    weight_sums: dict[str, float] = defaultdict(float)
    for position in positions:
        symbol = str(position.symbol)
        all_symbols.add(symbol)
        positions_by_date[position.date][symbol] = position
        if abs(float(position.qty)) > 1e-12:
            price_observations[symbol].append(
                float(position.market_value_base) / float(position.qty)
            )

    equity_by_date = {row.date: float(row.equity_base) for row in rows}
    for row in rows:
        equity = equity_by_date[row.date]
        if abs(equity) <= 1e-12:
            continue
        for symbol, position in positions_by_date.get(row.date, {}).items():
            weight_sums[symbol] += float(position.market_value_base) / equity

    contributions: dict[str, float] = defaultdict(float)
    last_prices: dict[str, float] = {}
    for index, row in enumerate(rows):
        current_positions = positions_by_date.get(row.date, {})
        current_prices = dict(last_prices)
        for symbol, position in current_positions.items():
            if abs(float(position.qty)) > 1e-12:
                current_prices[symbol] = (
                    float(position.market_value_base) / float(position.qty)
                )
        if index > 0:
            previous_row = rows[index - 1]
            previous_positions = positions_by_date.get(previous_row.date, {})
            previous_equity = float(previous_row.equity_base)
            if abs(previous_equity) > 1e-12:
                for symbol, previous_position in previous_positions.items():
                    previous_price = last_prices.get(symbol)
                    current_price = current_prices.get(symbol)
                    if previous_price is None or current_price is None:
                        continue
                    contributions[symbol] += (
                        float(previous_position.qty)
                        * (current_price - previous_price)
                        / previous_equity
                    )
        last_prices = current_prices

    persisted_contributions = (
        (metrics.meta or {}).get("return_contribution_by_symbol")
        if metrics is not None
        else None
    )
    if isinstance(persisted_contributions, dict):
        contributions = defaultdict(
            float,
            {
                str(symbol): float(value or 0.0)
                for symbol, value in persisted_contributions.items()
            },
        )
        all_symbols.update(contributions)

    result = [
        RunReturnAttributionRowOut(
            symbol=symbol,
            contribution=contributions.get(symbol, 0.0),
            avg_weight=weight_sums.get(symbol, 0.0) / len(rows),
            total_return=(
                price_observations[symbol][-1] / price_observations[symbol][0] - 1.0
                if len(price_observations[symbol]) >= 2
                and abs(price_observations[symbol][0]) > 1e-12
                else None
            ),
        )
        for symbol in sorted(all_symbols)
    ]
    portfolio_return = _safe_return(float(rows[-1].equity_base), initial_capital) or 0.0
    residual = portfolio_return - sum(item.contribution for item in result)
    average_cash_weight = sum(
        (
            float(row.cash_base) / float(row.equity_base)
            if abs(float(row.equity_base)) > 1e-12
            else 0.0
        )
        for row in rows
    ) / len(rows)
    result.append(
        RunReturnAttributionRowOut(
            symbol="CASH_RESIDUAL",
            contribution=residual,
            avg_weight=average_cash_weight,
            total_return=0.0,
        )
    )
    return result


@router.get(
    "/{run_id}/attribution/costs",
    response_model=RunCostAttributionOut,
)
def get_run_cost_attribution(
    run_id: UUID,
    actor: ActorContext = Depends(get_current_actor),
    db: Session = Depends(get_db),
) -> RunCostAttributionOut:
    run = _get_actor_run(run_id, actor, db)
    rows = _equity_rows(run_id, db) if _is_terminal_status(run.status) else []
    metrics = db.query(RunMetric).filter(RunMetric.run_id == run_id).first()
    initial_capital = _initial_capital_base(run, rows, metrics)
    base_currency = str(
        (run.config_snapshot or {}).get("base_currency") or "USD"
    ).upper()
    if not rows or not metrics or initial_capital <= 0.0:
        return RunCostAttributionOut(
            base_currency=base_currency,
            initial_capital_base=max(initial_capital, 0.0),
            items=[],
        )
    latest = rows[-1]
    net_return = (
        float(metrics.net_return)
        if metrics.net_return is not None
        else float(latest.equity_base) / initial_capital - 1.0
    )
    costs = [
        ("fees", float(latest.fees_cum_base or 0.0)),
        ("taxes", float(latest.taxes_cum_base or 0.0)),
        ("borrow", float(latest.borrow_fees_cum_base or 0.0)),
        ("margin_interest", float(latest.margin_interest_cum_base or 0.0)),
    ]
    total_cost = sum(amount for _key, amount in costs)
    gross_return = net_return + total_cost / initial_capital
    items = [
        RunCostWaterfallItemOut(
            key="gross_return",
            amount_base=gross_return * initial_capital,
            return_drag_bps=gross_return * 10_000.0,
        )
    ]
    items.extend(
        RunCostWaterfallItemOut(
            key=key,
            amount_base=-amount,
            return_drag_bps=-(amount / initial_capital) * 10_000.0,
        )
        for key, amount in costs
    )
    items.append(
        RunCostWaterfallItemOut(
            key="net_return",
            amount_base=net_return * initial_capital,
            return_drag_bps=net_return * 10_000.0,
        )
    )
    return RunCostAttributionOut(
        base_currency=base_currency,
        initial_capital_base=initial_capital,
        items=items,
    )
