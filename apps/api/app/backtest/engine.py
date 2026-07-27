"""Reusable backtest engine core."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from math import floor, sqrt
from typing import Any, Callable, Dict, Iterable, Literal
from uuid import uuid4

from sqlalchemy.orm import Session

from app.backtest.decision_recorder import (
    DecisionRecorder,
    OrderDecisionDraft,
    build_decision_recorder,
)
from app.backtest.errors import DataUnavailableError, NoTradingDaysError
from app.data.duckdb import get_duckdb_conn
from app.models.backtests import (
    BacktestRun,
    RunConstraintEvent,
    RunDailyEquity,
    RunFill,
    RunFinancing,
    RunMetric,
    RunOrder,
    RunOrderDecision,
    RunPosition,
    RunSignalSnapshot,
    RunTaxEvent,
    RunTaxLotConsumption,
)
from app.services import calendar_policy


@dataclass
class PositionState:
    qty: float = 0.0
    avg_cost_native: float = 0.0


@dataclass
class PortfolioState:
    cash_by_currency: Dict[str, float]
    positions: Dict[str, PositionState]
    last_price: Dict[str, float | None]


@dataclass
class DayContext:
    date: date
    flags: Dict[str, bool]
    prices: Dict[str, float | None]
    market_open: Dict[str, bool]
    state: PortfolioState
    equity_base: float
    cash_base_total: float
    position_value_base: Dict[str, float]
    fx_rate: Dict[str, float]
    recorder: DecisionRecorder
    is_warmup: bool = False


@dataclass
class OrderSpec:
    symbol: str
    side: str
    qty: float
    price: float
    decision: OrderDecisionDraft | None = None
    cash_buffer_trimmed: bool = False


@dataclass
class CommissionSpec:
    model: str
    bps: float
    min_fee_native: float


@dataclass
class SlippageSpec:
    model: str
    bps: float


@dataclass
class FinancingSpec:
    margin_enabled: bool
    max_leverage: float
    daily_margin_interest_bps: float
    shorting_enabled: bool
    daily_borrow_fee_bps: float


@dataclass
class RiskSpec:
    max_gross_leverage: float
    max_net_leverage: float
    max_weight: float | None = None


@dataclass
class TargetConstraint:
    symbol: str
    constraint_name: str
    bound_value: float | None
    pre_clamp_value: float
    applied_value: float
    reason: str
    meta: dict[str, Any]


@dataclass
class TaxSpec:
    regime: str
    short_term_days: int
    short_rate: float
    long_rate: float


@dataclass
class TaxLot:
    qty: float
    unit_cost_native: float
    opened_on: date
    opening_commission_native_per_unit: float = 0.0


TargetAllocator = Callable[[DayContext], Dict[str, float] | None]
AllocationKind = Literal["NATIVE_VALUE", "BASE_WEIGHT"]


def _ensure_calendar_views(con) -> None:
    try:
        con.execute("select 1 from global_calendar limit 1")
        con.execute("select 1 from global_trading_days limit 1")
    except Exception as exc:
        raise DataUnavailableError(
            "DuckDB calendar views missing. Run scripts/create_calendar_views.py first."
        ) from exc


def _fetch_calendar_with_prices(
    con, symbols: list[str], start_date: date, end_date: date
) -> Iterable[tuple]:
    if not symbols:
        raise ValueError("At least one symbol is required")
    placeholders = ",".join(["?"] * len(symbols))
    return con.execute(
        f"""
        SELECT
            g.date,
            g.is_us_trading,
            g.is_in_trading,
            g.is_fx_trading,
            p.symbol,
            p.close
        FROM global_trading_days d
        JOIN global_calendar g
            ON g.date = d.date
        LEFT JOIN prices p
            ON p.date = d.date
           AND p.symbol IN ({placeholders})
        WHERE d.date BETWEEN ? AND ?
        ORDER BY d.date, p.symbol
        """,
        [*symbols, start_date, end_date],
    ).fetchall()


def _fetch_symbol_currencies(con, symbols: list[str]) -> Dict[str, str]:
    placeholders = ",".join(["?"] * len(symbols))
    rows = con.execute(
        f"""
        SELECT symbol, min(currency) AS currency
        FROM prices
        WHERE symbol IN ({placeholders})
        GROUP BY symbol
        """,
        symbols,
    ).fetchall()
    mapping = {symbol: currency for symbol, currency in rows}
    missing = [symbol for symbol in symbols if symbol not in mapping]
    if missing:
        raise DataUnavailableError(f"Missing currency metadata for symbols: {missing}")
    return mapping


def _fetch_usd_inr_rates(con, start_date: date, end_date: date) -> Dict[date, float]:
    rows = con.execute(
        """
        SELECT date, close
        FROM prices
        WHERE symbol = 'USDINR'
          AND date <= ?
          AND (
              date >= ?
              OR date = (
                  SELECT max(date)
                  FROM prices
                  WHERE symbol = 'USDINR' AND date < ?
              )
          )
        ORDER BY date
        """,
        [end_date, start_date, start_date],
    ).fetchall()
    return {row_date: float(close) for row_date, close in rows if close is not None}


def _fetch_benchmark_prices(
    con, benchmark: str | None, start_date: date, end_date: date
) -> tuple[Dict[date, float], str | None]:
    if not benchmark:
        return {}, None
    rows = con.execute(
        """
        SELECT date, close, currency
        FROM prices
        WHERE upper(symbol) = ?
          AND date <= ?
          AND (
              date >= ?
              OR date = (
                  SELECT max(date)
                  FROM prices
                  WHERE upper(symbol) = ? AND date < ?
              )
          )
        ORDER BY date
        """,
        [
            benchmark.upper(),
            end_date,
            start_date,
            benchmark.upper(),
            start_date,
        ],
    ).fetchall()
    prices = {
        row_date: float(close)
        for row_date, close, _currency in rows
        if close is not None
    }
    currencies = {
        str(currency).upper()
        for _row_date, close, currency in rows
        if close is not None and currency
    }
    currency = next(iter(currencies)) if len(currencies) == 1 else None
    return prices, currency


def _align_benchmark_to_base(
    dates: list[date],
    prices_native: Dict[date, float],
    benchmark_currency: str | None,
    base_currency: str,
    usd_inr_by_date: Dict[date, float],
) -> list[float | None]:
    if not prices_native or not benchmark_currency:
        return [None for _date in dates]
    last_price: float | None = None
    last_usd_inr: float | None = None
    if dates:
        for price_date in sorted(prices_native):
            if price_date > dates[0]:
                break
            last_price = prices_native[price_date]
        for fx_date in sorted(usd_inr_by_date):
            if fx_date > dates[0]:
                break
            last_usd_inr = usd_inr_by_date[fx_date]
    first_usd_inr = next(iter(usd_inr_by_date.values()), None)
    aligned: list[float | None] = []
    for observation_date in dates:
        if observation_date in prices_native:
            last_price = prices_native[observation_date]
        if observation_date in usd_inr_by_date:
            last_usd_inr = usd_inr_by_date[observation_date]
        if last_price is None:
            aligned.append(None)
            continue
        try:
            aligned.append(
                _convert_native_to_base(
                    last_price,
                    benchmark_currency,
                    base_currency,
                    last_usd_inr if last_usd_inr is not None else first_usd_inr,
                )
            )
        except DataUnavailableError:
            aligned.append(None)
    return aligned


def _normalize_missing_bar_policy(policy: str) -> str:
    policy_norm = str(policy or "").strip().upper()
    if not policy_norm:
        return "FAIL"
    if policy_norm not in {"FAIL", "FORWARD_FILL"}:
        raise ValueError(f"Unsupported missing_bar policy '{policy}'.")
    return policy_norm


def _normalize_fill_price_policy(policy: str) -> str:
    policy_norm = str(policy or "").strip().upper()
    if not policy_norm:
        return "CLOSE"
    if policy_norm not in {"CLOSE"}:
        raise ValueError(f"Unsupported fill_price_policy '{policy}'.")
    return policy_norm


def _normalize_missing_fx_policy(policy: str) -> str:
    policy_norm = str(policy or "").strip().upper()
    if not policy_norm:
        return "FORWARD_FILL"
    if policy_norm not in {"FAIL", "FORWARD_FILL"}:
        raise ValueError(f"Unsupported missing_fx policy '{policy}'.")
    return policy_norm


def _parse_financing(config: Dict[str, Any] | None) -> FinancingSpec:
    config = config or {}
    margin = config.get("margin") or {}
    shorting = config.get("shorting") or {}
    max_leverage = float(margin.get("max_leverage") or 1.0)
    if max_leverage <= 0:
        raise ValueError("financing.margin.max_leverage must be > 0")
    daily_interest_bps = float(margin.get("daily_interest_bps") or 0.0)
    borrow_fee_bps = float(shorting.get("borrow_fee_daily_bps") or 0.0)
    if daily_interest_bps < 0 or borrow_fee_bps < 0:
        raise ValueError("financing rates must be >= 0")
    return FinancingSpec(
        margin_enabled=bool(margin.get("enabled")),
        max_leverage=max_leverage,
        daily_margin_interest_bps=daily_interest_bps,
        shorting_enabled=bool(shorting.get("enabled")),
        daily_borrow_fee_bps=borrow_fee_bps,
    )


def _parse_risk(config: Dict[str, Any] | None, financing: FinancingSpec) -> RiskSpec:
    config = config or {}
    max_gross = float(config.get("max_gross_leverage") or financing.max_leverage or 1.0)
    max_net = float(config.get("max_net_leverage") or max_gross)
    if max_gross <= 0:
        raise ValueError("risk.max_gross_leverage must be > 0")
    if max_net < 0:
        raise ValueError("risk.max_net_leverage must be >= 0")
    if max_net > max_gross + 1e-12:
        raise ValueError("risk.max_net_leverage cannot exceed risk.max_gross_leverage")
    max_weight_value = config.get("max_weight")
    max_weight = (
        float(max_weight_value)
        if max_weight_value is not None
        else None
    )
    if max_weight is not None and max_weight <= 0:
        raise ValueError("risk.max_weight must be > 0")
    return RiskSpec(
        max_gross_leverage=max_gross,
        max_net_leverage=max_net,
        max_weight=max_weight,
    )


def _clamp_target_weights(
    weights: Dict[str, float],
    risk: RiskSpec,
    financing: FinancingSpec,
) -> tuple[Dict[str, float], list[TargetConstraint]]:
    applied = {symbol: float(weight) for symbol, weight in weights.items()}
    constraints: list[TargetConstraint] = []

    if risk.max_weight is not None:
        for symbol, weight in list(applied.items()):
            clamped = max(-risk.max_weight, min(risk.max_weight, weight))
            if abs(clamped - weight) <= 1e-12:
                continue
            applied[symbol] = clamped
            constraints.append(
                TargetConstraint(
                    symbol=symbol,
                    constraint_name="max_weight",
                    bound_value=risk.max_weight,
                    pre_clamp_value=weight,
                    applied_value=clamped,
                    reason=(
                        f"Absolute target weight exceeded the configured "
                        f"{risk.max_weight:.6f} maximum."
                    ),
                    meta={},
                )
            )

    max_gross = risk.max_gross_leverage
    if financing.margin_enabled:
        max_gross = min(max_gross, financing.max_leverage)
    else:
        max_gross = min(max_gross, 1.0)
    gross = sum(abs(weight) for weight in applied.values())
    if gross > max_gross + 1e-12:
        scale = max_gross / gross
        before = dict(applied)
        applied = {
            symbol: weight * scale
            for symbol, weight in applied.items()
        }
        for symbol, weight in before.items():
            constraints.append(
                TargetConstraint(
                    symbol=symbol,
                    constraint_name="max_gross",
                    bound_value=max_gross,
                    pre_clamp_value=weight,
                    applied_value=applied[symbol],
                    reason=(
                        f"Portfolio gross target {gross:.6f} exceeded the "
                        f"{max_gross:.6f} leverage bound."
                    ),
                    meta={
                        "pre_clamp_portfolio_gross": gross,
                        "scale": scale,
                    },
                )
            )

    net = sum(applied.values())
    if abs(net) > risk.max_net_leverage + 1e-12:
        scale = risk.max_net_leverage / abs(net)
        before = dict(applied)
        applied = {
            symbol: weight * scale
            for symbol, weight in applied.items()
        }
        for symbol, weight in before.items():
            constraints.append(
                TargetConstraint(
                    symbol=symbol,
                    constraint_name="max_net",
                    bound_value=risk.max_net_leverage,
                    pre_clamp_value=weight,
                    applied_value=applied[symbol],
                    reason=(
                        f"Absolute portfolio net target {abs(net):.6f} exceeded "
                        f"the {risk.max_net_leverage:.6f} leverage bound."
                    ),
                    meta={
                        "pre_clamp_portfolio_net": net,
                        "scale": scale,
                    },
                )
            )

    return applied, constraints


def _convert_native_to_base(
    value: float,
    native_currency: str,
    base_currency: str,
    usd_inr: float | None,
) -> float:
    native = str(native_currency or "").upper()
    base = str(base_currency or "").upper()
    if native == base:
        return value
    if usd_inr is None or usd_inr <= 0:
        raise DataUnavailableError(
            f"Missing USDINR FX rate for {native}->{base} conversion."
        )
    if native == "INR" and base == "USD":
        return value / usd_inr
    if native == "USD" and base == "INR":
        return value * usd_inr
    raise DataUnavailableError(
        f"Unsupported FX conversion from {native} to base currency {base}."
    )


DEFAULT_CASH_BUFFER_PCT = 0.01


def _parse_cash_buffer_pct(config: Dict[str, Any] | None) -> float:
    """Fraction of equity held back from target allocations to cover trading costs."""
    value = (config or {}).get("cash_buffer_pct")
    if value is None:
        return DEFAULT_CASH_BUFFER_PCT
    buffer_pct = float(value)
    if not 0.0 <= buffer_pct <= 0.5:
        raise ValueError("execution.cash_buffer_pct must be between 0 and 0.5.")
    return buffer_pct


def _convert_base_to_native(
    value: float,
    native_currency: str,
    base_currency: str,
    usd_inr: float | None,
) -> float:
    """Inverse of native-to-base conversion at the same spot FX rate."""
    rate = _convert_native_to_base(1.0, native_currency, base_currency, usd_inr)
    if rate <= 0:
        raise DataUnavailableError(
            f"Invalid FX rate for {base_currency}->{native_currency} conversion."
        )
    return value / rate


def _parse_tax(config: Dict[str, Any] | None) -> TaxSpec:
    config = config or {}
    regime = str(config.get("regime") or "NONE").upper()
    if regime == "NONE":
        return TaxSpec(regime="NONE", short_term_days=365, short_rate=0.0, long_rate=0.0)
    if regime not in {"US", "INDIA"}:
        raise ValueError(f"Unsupported tax.regime '{regime}'.")
    if regime == "US":
        conf = config.get("us") or {}
        short_term_days = int(conf.get("short_term_days") or 365)
        # Simplified defaults: fixed blended rates (not slab-aware).
        short_rate = float(conf.get("short_rate") if "short_rate" in conf else 0.30)
        long_rate = float(conf.get("long_rate") if "long_rate" in conf else 0.15)
    else:
        conf = config.get("india") or {}
        short_term_days = int(conf.get("short_term_days") or 365)
        # Simplified defaults aligned to post-Jul-2024 listed-equity rates.
        short_rate = float(conf.get("short_rate") if "short_rate" in conf else 0.20)
        long_rate = float(conf.get("long_rate") if "long_rate" in conf else 0.125)
    if short_term_days <= 0:
        raise ValueError("tax short_term_days must be > 0")
    if short_rate < 0 or long_rate < 0:
        raise ValueError("tax rates must be >= 0")
    return TaxSpec(
        regime=regime,
        short_term_days=short_term_days,
        short_rate=short_rate,
        long_rate=long_rate,
    )


def _tax_bucket_and_rate(
    tax_spec: TaxSpec,
    holding_period_days: int,
) -> tuple[str, float]:
    if tax_spec.regime == "NONE":
        return "NONE", 0.0
    is_short = holding_period_days <= tax_spec.short_term_days
    region = "US" if tax_spec.regime == "US" else "INDIA"
    bucket = f"{region}_{'ST' if is_short else 'LT'}"
    rate = tax_spec.short_rate if is_short else tax_spec.long_rate
    return bucket, rate


def _parse_commission(config: Dict[str, Any] | None) -> CommissionSpec:
    config = config or {}
    model = str(config.get("model") or "BPS").upper()
    if model != "BPS":
        raise ValueError(f"Unsupported commission model '{model}'.")
    bps = float(config.get("bps") or 0.0)
    min_fee = float(config.get("min_fee_native") or 0.0)
    if bps < 0 or min_fee < 0:
        raise ValueError("commission bps and min_fee_native must be >= 0")
    return CommissionSpec(model=model, bps=bps, min_fee_native=min_fee)


def _parse_slippage(config: Dict[str, Any] | None) -> SlippageSpec:
    config = config or {}
    model = str(config.get("model") or "BPS").upper()
    if model != "BPS":
        raise ValueError(f"Unsupported slippage model '{model}'.")
    bps = float(config.get("bps") or 0.0)
    if bps < 0:
        raise ValueError("slippage bps must be >= 0")
    return SlippageSpec(model=model, bps=bps)


def _max_affordable_qty(
    *,
    cash_bucket: float,
    exec_price: float,
    commission_bps: float,
    min_fee_native: float,
) -> float:
    if exec_price <= 0 or cash_bucket <= 0:
        return 0.0
    bps_rate = max(0.0, commission_bps) / 10000.0
    min_fee = max(0.0, min_fee_native)

    # Regime 1: minimum fee dominates.
    qty_min_fee = 0.0
    if cash_bucket > min_fee:
        qty_min_fee = (cash_bucket - min_fee) / exec_price

    # Regime 2: bps fee dominates.
    qty_bps = cash_bucket / (exec_price * (1.0 + bps_rate))

    # The exact commission is max(bps fee, minimum fee), so both affordability
    # bounds must hold. The smaller quantity is the binding constraint.
    candidate = min(qty_min_fee, qty_bps)
    # Ensure strict affordability under the exact commission formula.
    notional = candidate * exec_price
    commission = max(notional * bps_rate, min_fee)
    total = notional + commission
    if total > cash_bucket:
        # Deterministic fallback when floating-point pushes just over budget.
        candidate *= 0.999999
    return max(candidate, 0.0)


def _sample_std(values: list[float]) -> float | None:
    if len(values) < 2:
        return None
    mean_value = sum(values) / len(values)
    variance = sum((value - mean_value) ** 2 for value in values) / (len(values) - 1)
    return sqrt(variance)


def _linear_percentile(values: list[float], percentile: float) -> float | None:
    """Return a linearly interpolated percentile, matching NumPy's default method."""
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * percentile
    lower = floor(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * weight


def _compute_metrics(
    equity_series: list[float],
    fees_cum_series: list[float] | None = None,
    initial_cash: float | None = None,
    turnover_notional_base: float = 0.0,
    benchmark_series_base: list[float | None] | None = None,
    risk_free_rate_annual: float = 0.0,
) -> dict[str, float | None]:
    """Compute metrics over every global-calendar observation, including flat days.

    Historical VaR uses linear interpolation on sorted daily returns (NumPy's default
    percentile method). VaR and CVaR are returned as positive loss magnitudes.
    """
    if len(equity_series) < 2:
        return {
            "cagr": None,
            "volatility": None,
            "sharpe": None,
            "sortino": None,
            "max_drawdown": None,
            "turnover": None,
            "gross_return": None,
            "net_return": None,
            "fee_drag": 0.0,
            "tax_drag": 0.0,
            "borrow_drag": 0.0,
            "margin_interest_drag": 0.0,
            "calmar": None,
            "var_95": None,
            "cvar_95": None,
            "best_day": None,
            "worst_day": None,
            "win_rate": None,
            "avg_win_day": None,
            "avg_loss_day": None,
            "beta": None,
            "alpha": None,
            "tracking_error": None,
            "information_ratio": None,
        }

    initial = initial_cash if initial_cash is not None else equity_series[0]
    final = equity_series[-1]
    net_return = final / initial - 1.0 if initial else None

    daily_returns: list[float] = []
    for prev, curr in zip(equity_series[:-1], equity_series[1:]):
        if prev != 0:
            daily_returns.append(curr / prev - 1.0)

    if daily_returns:
        risk_free_rate_daily = (1.0 + risk_free_rate_annual) ** (1.0 / 252.0) - 1.0
        excess_returns = [
            value - risk_free_rate_daily for value in daily_returns
        ]
        mean_ret = sum(daily_returns) / len(daily_returns)
        mean_excess_ret = sum(excess_returns) / len(excess_returns)
        std_ret = _sample_std(daily_returns) or 0.0
        volatility = std_ret * sqrt(252.0) if std_ret else 0.0
        sharpe = (mean_excess_ret * 252.0) / volatility if volatility else None
        negative_returns = [value for value in daily_returns if value < 0.0]
        downside_deviation = sqrt(
            sum(min(value, 0.0) ** 2 for value in daily_returns) / len(daily_returns)
        )
        sortino = (
            (mean_ret * 252.0) / (downside_deviation * sqrt(252.0))
            if len(negative_returns) >= 2 and downside_deviation > 0.0
            else None
        )
        if initial > 0 and final > 0:
            cagr = (final / initial) ** (252.0 / len(daily_returns)) - 1.0
        else:
            cagr = None
    else:
        volatility = None
        sharpe = None
        sortino = None
        cagr = None

    peak = equity_series[0]
    max_drawdown = 0.0
    for equity in equity_series:
        if equity > peak:
            peak = equity
        if peak:
            drawdown = equity / peak - 1.0
            if drawdown < max_drawdown:
                max_drawdown = drawdown

    gross_return = net_return
    fee_drag = None
    if fees_cum_series and len(fees_cum_series) == len(equity_series):
        gross_final = final + fees_cum_series[-1]
        if initial:
            gross_return = gross_final / initial - 1.0
        if gross_return is not None and net_return is not None:
            fee_drag = gross_return - net_return

    years = len(daily_returns) / 252.0
    average_equity = sum(equity_series) / len(equity_series)
    turnover = (
        turnover_notional_base / (average_equity * years)
        if years > 0.0 and average_equity > 0.0
        else None
    )
    calmar = (
        cagr / abs(max_drawdown)
        if cagr is not None and max_drawdown < 0.0
        else None
    )
    percentile_5 = _linear_percentile(daily_returns, 0.05)
    tail_returns = (
        [value for value in daily_returns if value <= percentile_5]
        if percentile_5 is not None
        else []
    )
    var_95 = max(0.0, -percentile_5) if percentile_5 is not None else None
    cvar_95 = max(0.0, -(sum(tail_returns) / len(tail_returns))) if tail_returns else None
    winning_days = [value for value in daily_returns if value > 0.0]
    losing_days = [value for value in daily_returns if value < 0.0]
    non_flat_days = winning_days + losing_days

    beta = None
    alpha = None
    tracking_error = None
    information_ratio = None
    if benchmark_series_base and len(benchmark_series_base) == len(equity_series):
        paired_returns: list[tuple[float, float]] = []
        for index in range(1, len(equity_series)):
            portfolio_previous = equity_series[index - 1]
            benchmark_previous = benchmark_series_base[index - 1]
            benchmark_current = benchmark_series_base[index]
            if (
                portfolio_previous == 0.0
                or benchmark_previous is None
                or benchmark_current is None
                or benchmark_previous == 0.0
            ):
                continue
            paired_returns.append(
                (
                    equity_series[index] / portfolio_previous - 1.0,
                    benchmark_current / benchmark_previous - 1.0,
                )
            )
        if len(paired_returns) >= 2:
            portfolio_returns = [row[0] for row in paired_returns]
            benchmark_returns = [row[1] for row in paired_returns]
            portfolio_mean = sum(portfolio_returns) / len(portfolio_returns)
            benchmark_mean = sum(benchmark_returns) / len(benchmark_returns)
            benchmark_variance = sum(
                (value - benchmark_mean) ** 2 for value in benchmark_returns
            ) / (len(benchmark_returns) - 1)
            if benchmark_variance > 0.0:
                covariance = sum(
                    (portfolio - portfolio_mean) * (benchmark - benchmark_mean)
                    for portfolio, benchmark in paired_returns
                ) / (len(paired_returns) - 1)
                beta = covariance / benchmark_variance
                risk_free_rate_daily = (
                    (1.0 + risk_free_rate_annual) ** (1.0 / 252.0) - 1.0
                )
                alpha = sum(
                    (portfolio - risk_free_rate_daily)
                    - beta * (benchmark - risk_free_rate_daily)
                    for portfolio, benchmark in paired_returns
                ) / len(paired_returns) * 252.0
            active_returns = [
                portfolio - benchmark for portfolio, benchmark in paired_returns
            ]
            tracking_error_daily = _sample_std(active_returns)
            if tracking_error_daily and tracking_error_daily > 0.0:
                tracking_error = tracking_error_daily * sqrt(252.0)
                information_ratio = (
                    (sum(active_returns) / len(active_returns)) * 252.0
                ) / tracking_error

    return {
        "cagr": cagr,
        "volatility": volatility,
        "sharpe": sharpe,
        "sortino": sortino,
        "max_drawdown": max_drawdown,
        "turnover": turnover,
        "gross_return": gross_return,
        "net_return": net_return,
        "fee_drag": fee_drag,
        "tax_drag": 0.0,
        "borrow_drag": 0.0,
        "margin_interest_drag": 0.0,
        "calmar": calmar,
        "var_95": var_95,
        "cvar_95": cvar_95,
        "best_day": max(daily_returns) if daily_returns else None,
        "worst_day": min(daily_returns) if daily_returns else None,
        "win_rate": len(winning_days) / len(non_flat_days) if non_flat_days else None,
        "avg_win_day": sum(winning_days) / len(winning_days) if winning_days else None,
        "avg_loss_day": sum(losing_days) / len(losing_days) if losing_days else None,
        "beta": beta,
        "alpha": alpha,
        "tracking_error": tracking_error,
        "information_ratio": information_ratio,
    }


def _targets_to_orders(
    state: PortfolioState,
    target_allocations: Dict[str, float],
    prices: Dict[str, float | None],
    market_open: Dict[str, bool],
    *,
    recorder: DecisionRecorder,
    requested_target_weights: Dict[str, float | None] | None = None,
    target_weights: Dict[str, float | None] | None = None,
    cash_buffer_trimmed: set[str] | None = None,
    constraint_specs_by_symbol: Dict[str, list[TargetConstraint]] | None = None,
) -> list[OrderSpec]:
    orders: list[OrderSpec] = []
    requested_target_weights = requested_target_weights or {}
    target_weights = target_weights or {}
    cash_buffer_trimmed = cash_buffer_trimmed or set()
    constraint_specs_by_symbol = constraint_specs_by_symbol or {}

    def decision_for(
        *,
        symbol: str,
        current_qty: float,
        target_qty: float | None,
        delta_qty: float | None,
        intended_side: str | None,
        intended_qty: float | None,
        outcome: str,
        reason: str | None = None,
    ) -> OrderDecisionDraft | None:
        adjustments = (
            ["TRIMMED_CASH_BUFFER"] if symbol in cash_buffer_trimmed else []
        )
        decision = recorder.order_decision(
            symbol=symbol,
            requested_target_weight=requested_target_weights.get(symbol),
            target_weight=target_weights.get(symbol),
            target_qty=target_qty,
            current_qty=current_qty,
            delta_qty=delta_qty,
            intended_side=intended_side,
            intended_qty=intended_qty,
            executable_qty=None,
            outcome=outcome,
            reason=reason,
            meta={"adjustments": adjustments} if adjustments else {},
        )
        for constraint in constraint_specs_by_symbol.get(symbol, []):
            recorder.constraint(
                decision,
                constraint.constraint_name,
                bound_value=constraint.bound_value,
                pre_clamp_value=constraint.pre_clamp_value,
                applied_value=constraint.applied_value,
                reason=constraint.reason,
                meta=constraint.meta,
            )
        return decision

    for symbol, target_value in target_allocations.items():
        if symbol not in state.positions:
            raise ValueError(f"Unknown symbol in target allocation: {symbol}")
        current_qty = state.positions[symbol].qty
        if not market_open.get(symbol):
            decision_for(
                symbol=symbol,
                current_qty=current_qty,
                target_qty=None,
                delta_qty=None,
                intended_side=None,
                intended_qty=None,
                outcome="SKIPPED_MARKET_CLOSED",
                reason="The instrument market was closed on the decision date.",
            )
            continue
        price = prices.get(symbol)
        if price is None:
            decision_for(
                symbol=symbol,
                current_qty=current_qty,
                target_qty=None,
                delta_qty=None,
                intended_side=None,
                intended_qty=None,
                outcome="SKIPPED_NO_PRICE",
                reason="No executable price was available for the instrument.",
            )
            continue

        target_qty = target_value / price if price else 0.0
        delta = target_qty - current_qty
        if abs(delta) < 1e-9:
            unchanged = abs(delta) <= 1e-12
            decision_for(
                symbol=symbol,
                current_qty=current_qty,
                target_qty=target_qty,
                delta_qty=delta,
                intended_side=None,
                intended_qty=abs(delta),
                outcome="HELD_NO_CHANGE" if unchanged else "BELOW_MIN_DELTA",
                reason=(
                    "Current quantity already matches the target."
                    if unchanged
                    else "The target delta was below the engine minimum quantity."
                ),
            )
            continue

        if current_qty >= 0 and target_qty >= 0:
            if delta > 1e-9:
                decision = decision_for(
                    symbol=symbol,
                    current_qty=current_qty,
                    target_qty=target_qty,
                    delta_qty=delta,
                    intended_side="BUY",
                    intended_qty=delta,
                    outcome="PENDING",
                )
                orders.append(
                    OrderSpec(
                        symbol=symbol,
                        side="BUY",
                        qty=delta,
                        price=price,
                        decision=decision,
                    )
                )
            elif delta < -1e-9:
                decision = decision_for(
                    symbol=symbol,
                    current_qty=current_qty,
                    target_qty=target_qty,
                    delta_qty=delta,
                    intended_side="SELL",
                    intended_qty=abs(delta),
                    outcome="PENDING",
                )
                orders.append(
                    OrderSpec(
                        symbol=symbol,
                        side="SELL",
                        qty=abs(delta),
                        price=price,
                        decision=decision,
                    )
                )
        elif current_qty <= 0 and target_qty <= 0:
            if target_qty < current_qty - 1e-9:
                decision = decision_for(
                    symbol=symbol,
                    current_qty=current_qty,
                    target_qty=target_qty,
                    delta_qty=delta,
                    intended_side="SHORT",
                    intended_qty=abs(delta),
                    outcome="PENDING",
                )
                orders.append(
                    OrderSpec(
                        symbol=symbol,
                        side="SHORT",
                        qty=abs(target_qty - current_qty),
                        price=price,
                        decision=decision,
                    )
                )
            elif target_qty > current_qty + 1e-9:
                decision = decision_for(
                    symbol=symbol,
                    current_qty=current_qty,
                    target_qty=target_qty,
                    delta_qty=delta,
                    intended_side="COVER",
                    intended_qty=abs(delta),
                    outcome="PENDING",
                )
                orders.append(
                    OrderSpec(
                        symbol=symbol,
                        side="COVER",
                        qty=abs(target_qty - current_qty),
                        price=price,
                        decision=decision,
                    )
                )
        elif current_qty > 0 and target_qty < 0:
            sell_decision = decision_for(
                symbol=symbol,
                current_qty=current_qty,
                target_qty=target_qty,
                delta_qty=delta,
                intended_side="SELL",
                intended_qty=current_qty,
                outcome="PENDING",
            )
            short_decision = decision_for(
                symbol=symbol,
                current_qty=0.0,
                target_qty=target_qty,
                delta_qty=target_qty,
                intended_side="SHORT",
                intended_qty=abs(target_qty),
                outcome="PENDING",
            )
            orders.append(
                OrderSpec(
                    symbol=symbol,
                    side="SELL",
                    qty=current_qty,
                    price=price,
                    decision=sell_decision,
                )
            )
            orders.append(
                OrderSpec(
                    symbol=symbol,
                    side="SHORT",
                    qty=abs(target_qty),
                    price=price,
                    decision=short_decision,
                )
            )
        elif current_qty < 0 and target_qty > 0:
            cover_decision = decision_for(
                symbol=symbol,
                current_qty=current_qty,
                target_qty=target_qty,
                delta_qty=delta,
                intended_side="COVER",
                intended_qty=abs(current_qty),
                outcome="PENDING",
            )
            buy_decision = decision_for(
                symbol=symbol,
                current_qty=0.0,
                target_qty=target_qty,
                delta_qty=target_qty,
                intended_side="BUY",
                intended_qty=target_qty,
                outcome="PENDING",
            )
            orders.append(
                OrderSpec(
                    symbol=symbol,
                    side="COVER",
                    qty=abs(current_qty),
                    price=price,
                    decision=cover_decision,
                )
            )
            orders.append(
                OrderSpec(
                    symbol=symbol,
                    side="BUY",
                    qty=target_qty,
                    price=price,
                    decision=buy_decision,
                )
            )

    for order in orders:
        order.cash_buffer_trimmed = order.symbol in cash_buffer_trimmed
    return orders


def run_engine(
    db: Session,
    run: BacktestRun,
    instruments: list[dict[str, str | float]],
    calendars_map: Dict[str, str] | None,
    start_date: date,
    end_date: date,
    initial_cash: float,
    initial_cash_by_currency: Dict[str, float] | None,
    target_allocations_fn: TargetAllocator,
    commission_cfg: Dict[str, Any] | None,
    slippage_cfg: Dict[str, Any] | None,
    fill_price_policy: str,
    allocation_mode: str,
    missing_bar_policy: str = "FAIL",
    missing_fx_policy: str | None = None,
    include_financing: bool = True,
    allocation_kind: AllocationKind = "NATIVE_VALUE",
    apply_cash_buffer: bool = True,
) -> int:
    symbols = [inst["symbol"] for inst in instruments]
    policy = _normalize_missing_bar_policy(missing_bar_policy)
    _ = _normalize_fill_price_policy(fill_price_policy)
    config_snapshot = run.config_snapshot or {}
    backtest_config = config_snapshot.get("backtest") or {}
    evaluation_start_value = backtest_config.get("evaluation_start_date")
    evaluation_start_date = (
        date.fromisoformat(str(evaluation_start_value))
        if evaluation_start_value is not None
        else start_date
    )
    if not start_date <= evaluation_start_date <= end_date:
        raise ValueError(
            "evaluation_start_date must be between start_date and end_date"
        )
    base_currency = str(config_snapshot.get("base_currency") or "USD").upper()
    benchmark_value = config_snapshot.get("benchmark")
    benchmark = str(benchmark_value).strip().upper() if benchmark_value else None
    fx_policy = _normalize_missing_fx_policy(
        missing_fx_policy or (config_snapshot.get("data_policy") or {}).get("missing_fx")
    )
    financing = _parse_financing(config_snapshot.get("financing"))
    risk = _parse_risk(config_snapshot.get("risk"), financing)
    tax_spec = _parse_tax(config_snapshot.get("tax"))
    commission = _parse_commission(commission_cfg)
    slippage = _parse_slippage(slippage_cfg)
    allocation_mode = str(allocation_mode or "").upper()
    allocation_kind = str(allocation_kind or "NATIVE_VALUE").upper()
    if allocation_kind not in {"NATIVE_VALUE", "BASE_WEIGHT"}:
        raise ValueError(f"Unsupported allocation_kind '{allocation_kind}'.")
    cash_buffer_pct = _parse_cash_buffer_pct(config_snapshot.get("execution"))
    recorder = build_decision_recorder(run.run_id, config_snapshot.get("explain"))

    con = get_duckdb_conn()
    try:
        _ensure_calendar_views(con)
        symbol_currencies = _fetch_symbol_currencies(con, symbols)
        usd_inr_by_date = _fetch_usd_inr_rates(con, start_date, end_date)
        rows = _fetch_calendar_with_prices(con, symbols, start_date, end_date)
        benchmark_prices_native, benchmark_currency = _fetch_benchmark_prices(
            con, benchmark, start_date, end_date
        )
    finally:
        con.close()

    if not rows:
        raise NoTradingDaysError(
            "No trading days found between "
            f"{start_date} and {end_date} for the selected calendars."
        )

    requested_start_date = start_date
    requested_end_date = end_date
    effective_start_date = rows[0][0]
    effective_end_date = rows[-1][0]
    date_shift_warnings: list[str] = []
    if effective_start_date != requested_start_date:
        date_shift_warnings.append(
            f"Start date shifted from {requested_start_date} to {effective_start_date} "
            "to align with the trading calendar."
        )
    if effective_end_date != requested_end_date:
        date_shift_warnings.append(
            f"End date shifted from {requested_end_date} to {effective_end_date} "
            "to align with the trading calendar."
        )

    symbol_calendars = {
        inst["symbol"]: calendar_policy.calendar_for_asset_class(
            inst["asset_class"], calendars_map
        )
        for inst in instruments
    }
    universe_summary = {
        "instrument_count": len(instruments),
        "symbols": sorted(str(inst["symbol"]) for inst in instruments),
        "asset_classes": sorted({str(inst.get("asset_class") or "") for inst in instruments}),
    }

    instrument_currencies = sorted({str(currency).upper() for currency in symbol_currencies.values()})
    currencies_set = set(instrument_currencies)
    currencies_set.add(base_currency)
    if initial_cash_by_currency:
        currencies_set.update(str(currency).upper() for currency in initial_cash_by_currency.keys())
    currencies = sorted(currencies_set)
    if (
        allocation_kind == "NATIVE_VALUE"
        and len(instrument_currencies) > 1
        and allocation_mode != "AMOUNT"
    ):
        raise ValueError(
            "Multi-currency runs require explicit amount allocations per instrument."
        )

    if initial_cash_by_currency:
        cash_by_currency = {
            currency: float(initial_cash_by_currency.get(currency, 0.0))
            for currency in currencies
        }
        missing_cash = [currency for currency in instrument_currencies if currency not in initial_cash_by_currency]
        if allocation_kind == "NATIVE_VALUE" and missing_cash:
            raise ValueError(
                f"initial_cash_by_currency missing values for currencies: {missing_cash}"
            )
    else:
        if allocation_kind == "NATIVE_VALUE" and len(instrument_currencies) > 1:
            raise ValueError(
                "initial_cash_by_currency is required when the universe spans multiple currencies."
            )
        currency = (
            base_currency
            if allocation_kind == "BASE_WEIGHT"
            else (instrument_currencies[0] if instrument_currencies else base_currency)
        )
        cash_by_currency = {ccy: 0.0 for ccy in currencies}
        cash_by_currency[currency] = float(initial_cash)
    cash_by_currency.setdefault(base_currency, 0.0)

    db.query(RunDailyEquity).filter(RunDailyEquity.run_id == run.run_id).delete(
        synchronize_session=False
    )
    db.query(RunMetric).filter(RunMetric.run_id == run.run_id).delete(
        synchronize_session=False
    )
    db.query(RunConstraintEvent).filter(
        RunConstraintEvent.run_id == run.run_id
    ).delete(synchronize_session=False)
    db.query(RunOrderDecision).filter(
        RunOrderDecision.run_id == run.run_id
    ).delete(synchronize_session=False)
    db.query(RunSignalSnapshot).filter(
        RunSignalSnapshot.run_id == run.run_id
    ).delete(synchronize_session=False)
    db.query(RunFill).filter(RunFill.run_id == run.run_id).delete(
        synchronize_session=False
    )
    db.query(RunOrder).filter(RunOrder.run_id == run.run_id).delete(
        synchronize_session=False
    )
    db.query(RunPosition).filter(RunPosition.run_id == run.run_id).delete(
        synchronize_session=False
    )
    db.query(RunFinancing).filter(RunFinancing.run_id == run.run_id).delete(
        synchronize_session=False
    )
    db.query(RunTaxLotConsumption).filter(
        RunTaxLotConsumption.run_id == run.run_id
    ).delete(synchronize_session=False)
    db.query(RunTaxEvent).filter(RunTaxEvent.run_id == run.run_id).delete(
        synchronize_session=False
    )

    state = PortfolioState(
        cash_by_currency=cash_by_currency,
        positions={symbol: PositionState() for symbol in symbols},
        last_price={symbol: None for symbol in symbols},
    )
    initial_cash_snapshot = dict(state.cash_by_currency)

    equity_rows: list[RunDailyEquity] = []
    order_rows: list[RunOrder] = []
    fill_rows: list[RunFill] = []
    position_rows: list[RunPosition] = []
    financing_rows: list[RunFinancing] = []
    tax_event_rows: list[RunTaxEvent] = []
    tax_lot_consumption_rows: list[RunTaxLotConsumption] = []
    fees_cum_by_currency: Dict[str, float] = {currency: 0.0 for currency in currencies}
    equity_series_base: list[float] = []
    fees_cum_series_base: list[float] = []
    taxes_cum_series_base: list[float] = []
    borrow_cum_series_base: list[float] = []
    margin_cum_series_base: list[float] = []
    equity_dates: list[date] = []
    taxes_cum_base = 0.0
    borrow_cum_base = 0.0
    margin_cum_base = 0.0
    turnover_notional_base = 0.0
    realized_trade_pnl_base: list[float] = []
    realized_trade_commissions_base: list[float] = []
    return_contribution_by_symbol: Dict[str, float] = {
        symbol: 0.0 for symbol in symbols
    }
    previous_attribution_qty: Dict[str, float] = {}
    previous_attribution_price_base: Dict[str, float] = {}
    previous_attribution_equity_base: float | None = None
    peak_equity_base: float | None = None
    initial_cash_base_at_evaluation: float | None = None

    first_observed_usd_inr = next(iter(usd_inr_by_date.values()), None)
    usd_inr_last: float | None = None
    lots_by_symbol: Dict[str, list[TaxLot]] = {symbol: [] for symbol in symbols}
    def resolve_usd_inr(day: date) -> float | None:
        nonlocal usd_inr_last
        direct = usd_inr_by_date.get(day)
        if direct is not None:
            usd_inr_last = direct
            return direct
        if fx_policy == "FORWARD_FILL":
            if usd_inr_last is not None:
                return usd_inr_last
            if first_observed_usd_inr is not None:
                return first_observed_usd_inr
        if any(ccy != base_currency for ccy in currencies):
            raise DataUnavailableError(
                f"Missing USDINR FX rate for {day}. Set data_policy.missing_fx=FORWARD_FILL to allow fallback."
            )
        return None

    def compute_portfolio_values(usd_inr: float | None) -> tuple[
        Dict[str, float],
        float,
        float,
        float,
        float,
        float,
    ]:
        equity_by_currency: Dict[str, float] = {
            currency: state.cash_by_currency.get(currency, 0.0) for currency in currencies
        }
        cash_base = 0.0
        for currency, amount in state.cash_by_currency.items():
            cash_base += _convert_native_to_base(amount, currency, base_currency, usd_inr)

        gross_exposure_base = 0.0
        net_exposure_base = 0.0
        short_notional_base = 0.0
        for symbol, pos in state.positions.items():
            price = state.last_price.get(symbol)
            if price is None:
                continue
            market_value_native = pos.qty * price
            symbol_currency = str(symbol_currencies[symbol]).upper()
            equity_by_currency[symbol_currency] = (
                equity_by_currency.get(symbol_currency, 0.0) + market_value_native
            )
            market_value_base = _convert_native_to_base(
                market_value_native, symbol_currency, base_currency, usd_inr
            )
            gross_exposure_base += abs(market_value_base)
            net_exposure_base += market_value_base
            if pos.qty < 0:
                short_notional_base += abs(market_value_base)
        equity_base = cash_base + net_exposure_base
        return (
            equity_by_currency,
            equity_base,
            cash_base,
            gross_exposure_base,
            net_exposure_base,
            short_notional_base,
        )

    def assert_risk_limits(usd_inr: float | None) -> None:
        (
            _equity_by_currency,
            equity_base,
            cash_base,
            gross_exposure_base,
            net_exposure_base,
            _short_notional_base,
        ) = compute_portfolio_values(usd_inr)
        if equity_base <= 1e-12:
            if gross_exposure_base > 1e-12:
                raise ValueError("Exposure exceeds limits: non-zero gross exposure with non-positive equity.")
            return

        max_gross = risk.max_gross_leverage
        if financing.margin_enabled:
            max_gross = min(max_gross, financing.max_leverage)
        else:
            max_gross = min(max_gross, 1.0)
        gross_lev = gross_exposure_base / equity_base
        net_lev = abs(net_exposure_base) / equity_base
        if gross_lev > max_gross + 1e-12:
            raise ValueError(
                f"Gross exposure limit breached: {gross_lev:.4f} > {max_gross:.4f}"
            )
        if net_lev > risk.max_net_leverage + 1e-12:
            raise ValueError(
                f"Net exposure limit breached: {net_lev:.4f} > {risk.max_net_leverage:.4f}"
            )
        if not financing.margin_enabled and cash_base < -1e-9:
            raise ValueError("Margin is disabled but cash would become negative.")

    def allocation_views(
        usd_inr: float | None,
    ) -> tuple[float, float, Dict[str, float], Dict[str, float]]:
        _, equity_base, cash_base, _, _, _ = compute_portfolio_values(usd_inr)
        position_value_base: Dict[str, float] = {}
        for symbol, position in state.positions.items():
            price = state.last_price.get(symbol)
            native_value = position.qty * price if price is not None else 0.0
            position_value_base[symbol] = _convert_native_to_base(
                native_value,
                symbol_currencies[symbol],
                base_currency,
                usd_inr,
            )
        fx_rate = {
            currency: _convert_native_to_base(1.0, currency, base_currency, usd_inr)
            for currency in currencies
        }
        return equity_base, cash_base, position_value_base, fx_rate

    def fund_native_cash_with_fx(
        *,
        day: date,
        native_currency: str,
        required_native: float,
        usd_inr: float | None,
    ) -> None:
        """Fund a native cash deficit from base cash and persist its audit fill."""
        if native_currency == base_currency:
            return
        available_native = state.cash_by_currency.get(native_currency, 0.0)
        deficit_native = max(0.0, required_native - available_native)
        if deficit_native <= 1e-9:
            return
        base_notional = _convert_native_to_base(
            deficit_native, native_currency, base_currency, usd_inr
        )
        friction_base = base_notional * (slippage.bps / 10000.0)
        state.cash_by_currency[base_currency] = (
            state.cash_by_currency.get(base_currency, 0.0)
            - base_notional
            - friction_base
        )
        state.cash_by_currency[native_currency] = available_native + deficit_native
        fees_cum_by_currency[base_currency] = (
            fees_cum_by_currency.get(base_currency, 0.0) + friction_base
        )

        order_id = uuid4()
        fx_meta = {
            "kind": "FX_SWEEP",
            "source_currency": base_currency,
            "destination_currency": native_currency,
        }
        order_rows.append(
            RunOrder(
                order_id=order_id,
                run_id=run.run_id,
                date=day,
                symbol="USDINR",
                side="FX",
                qty=deficit_native,
                order_type="MKT",
                limit_price=None,
                status="FILLED",
                meta=fx_meta,
            )
        )
        fill_rows.append(
            RunFill(
                fill_id=uuid4(),
                order_id=order_id,
                run_id=run.run_id,
                date=day,
                symbol="USDINR",
                qty=deficit_native,
                price_native=float(usd_inr or 1.0),
                commission_native=0.0,
                slippage_native=friction_base,
                notional_native=base_notional,
                meta=fx_meta,
            )
        )

    def settle_negative_native_cash(day: date, usd_inr: float | None) -> None:
        """Clear any negative non-base cash bucket back to zero via an FX sweep.

        Trade funding covers the order cost itself, but a tax accrual on a closing
        fill is debited afterwards and can leave a native bucket short. Without this
        pass that deficit is stranded: nothing else funds it, and per-currency margin
        interest would accrue on it indefinitely.
        """
        for currency in list(state.cash_by_currency.keys()):
            if currency == base_currency:
                continue
            if state.cash_by_currency.get(currency, 0.0) >= -1e-9:
                continue
            fund_native_cash_with_fx(
                day=day,
                native_currency=currency,
                required_native=0.0,
                usd_inr=usd_inr,
            )

    def realize_lots_and_accrue_tax(
        *,
        day: date,
        symbol: str,
        side: str,
        qty: float,
        exec_price: float,
        symbol_currency: str,
        usd_inr: float | None,
        closing_commission_native: float,
    ) -> None:
        nonlocal taxes_cum_base
        if qty <= 0:
            return
        if side not in {"SELL", "COVER"}:
            return
        lots = lots_by_symbol[symbol]
        remaining = qty
        if not lots:
            raise ValueError(f"No FIFO lots available for {side} {symbol}.")

        while remaining > 1e-12:
            if not lots:
                raise ValueError(f"Insufficient FIFO lots for {side} {symbol}.")
            lot = lots[0]
            consume = min(remaining, lot.qty)
            holding_days = max((day - lot.opened_on).days, 0)
            if side == "SELL":
                realized_native = (exec_price - lot.unit_cost_native) * consume
            else:
                # For short lots, unit_cost_native is short entry price.
                realized_native = (lot.unit_cost_native - exec_price) * consume
            realized_base = _convert_native_to_base(
                realized_native, symbol_currency, base_currency, usd_inr
            )
            realized_trade_pnl_base.append(realized_base)
            commission_native = (
                lot.opening_commission_native_per_unit * consume
                + closing_commission_native * (consume / qty)
            )
            realized_trade_commissions_base.append(
                _convert_native_to_base(
                    commission_native, symbol_currency, base_currency, usd_inr
                )
            )
            bucket, tax_rate = _tax_bucket_and_rate(tax_spec, holding_days)
            tax_due_base = max(realized_base, 0.0) * tax_rate
            taxes_cum_base += tax_due_base
            tax_due_native = _convert_base_to_native(
                tax_due_base, symbol_currency, base_currency, usd_inr
            )
            state.cash_by_currency[symbol_currency] = (
                state.cash_by_currency.get(symbol_currency, 0.0) - tax_due_native
            )

            tax_event_id = uuid4()
            tax_event_rows.append(
                RunTaxEvent(
                    tax_event_id=tax_event_id,
                    run_id=run.run_id,
                    date=day,
                    symbol=symbol,
                    quantity=consume,
                    realized_pnl_base=realized_base,
                    holding_period_days=holding_days,
                    bucket=bucket,
                    tax_rate=tax_rate,
                    tax_due_base=tax_due_base,
                    meta={
                        "side": side,
                        "regime": tax_spec.regime,
                        "realized_pnl_native": realized_native,
                        "currency": symbol_currency,
                    },
                )
            )
            tax_lot_consumption_rows.append(
                RunTaxLotConsumption(
                    consumption_id=uuid4(),
                    tax_event_id=tax_event_id,
                    run_id=run.run_id,
                    date=day,
                    symbol=symbol,
                    lot_opened_on=lot.opened_on,
                    lot_unit_cost_native=lot.unit_cost_native,
                    qty_consumed=consume,
                    holding_days=holding_days,
                    bucket=bucket,
                    realized_pnl_base=realized_base,
                )
            )

            lot.qty -= consume
            remaining -= consume
            if lot.qty <= 1e-12:
                lots.pop(0)
        assert_risk_limits(usd_inr)

    def process_day(
        day: date | None,
        flags: Dict[str, bool] | None,
        day_prices: Dict[str, float | None],
    ) -> None:
        nonlocal borrow_cum_base, margin_cum_base, peak_equity_base
        nonlocal turnover_notional_base
        nonlocal previous_attribution_equity_base, initial_cash_base_at_evaluation
        if day is None:
            return
        if flags is None:
            flags = {"is_us_trading": False, "is_in_trading": False, "is_fx_trading": False}
        is_warmup = day < evaluation_start_date
        recorder.begin_bar(day, is_warmup=is_warmup)

        market_open = {
            symbol: calendar_policy.is_market_open(flags, symbol_calendars[symbol])
            for symbol in symbols
        }

        prices: Dict[str, float | None] = {}
        for symbol in symbols:
            is_open = market_open.get(symbol)
            price = day_prices.get(symbol)
            if is_open:
                if price is None:
                    if policy == "FAIL":
                        raise DataUnavailableError(
                            f"Missing bar for {symbol} on {day}. "
                            "Set data_policy.missing_bar=FORWARD_FILL to allow forward fill."
                        )
                    if state.last_price[symbol] is None:
                        # Bootstrap start-of-range missing bars from the next observed in-range price.
                        bootstrap_price = first_observed_price.get(symbol)
                        if bootstrap_price is None:
                            raise DataUnavailableError(
                                f"Missing bar for {symbol} on {day} with no prior value to forward-fill."
                            )
                        price = bootstrap_price
                    else:
                        price = state.last_price[symbol]
                state.last_price[symbol] = price
                prices[symbol] = price
            else:
                prices[symbol] = None

        usd_inr = resolve_usd_inr(day)
        current_price_base_by_symbol = {
            symbol: _convert_native_to_base(
                float(state.last_price[symbol]),
                str(symbol_currencies[symbol]).upper(),
                base_currency,
                usd_inr,
            )
            for symbol in symbols
            if state.last_price[symbol] is not None
        }
        if (
            previous_attribution_equity_base is not None
            and abs(previous_attribution_equity_base) > 1e-12
        ):
            for symbol, previous_qty in previous_attribution_qty.items():
                previous_price = previous_attribution_price_base.get(symbol)
                current_price = current_price_base_by_symbol.get(symbol)
                if previous_price is None or current_price is None:
                    continue
                return_contribution_by_symbol[symbol] += (
                    previous_qty
                    * (current_price - previous_price)
                    / previous_attribution_equity_base
                )
        equity_base, cash_base_total, position_value_base, fx_rate = allocation_views(
            usd_inr
        )
        ctx = DayContext(
            date=day,
            flags=flags,
            prices=prices,
            market_open=market_open,
            state=state,
            equity_base=equity_base,
            cash_base_total=cash_base_total,
            position_value_base=position_value_base,
            fx_rate=fx_rate,
            recorder=recorder,
            is_warmup=is_warmup,
        )
        target_allocations = target_allocations_fn(ctx)
        if target_allocations is not None:
            recorder.mark_decision_cycle(source="strategy_allocation")
        if ctx.is_warmup:
            recorder.finish_bar()
            return
        if initial_cash_base_at_evaluation is None:
            initial_cash_base_at_evaluation = sum(
                _convert_native_to_base(
                    amount,
                    currency,
                    base_currency,
                    usd_inr,
                )
                for currency, amount in initial_cash_snapshot.items()
            )

        if target_allocations:
            requested_target_weights: Dict[str, float | None] = {}
            applied_target_weights: Dict[str, float | None] = {}
            cash_buffer_trimmed: set[str] = set()
            constraint_specs_by_symbol: Dict[str, list[TargetConstraint]] = {
                symbol: [] for symbol in target_allocations
            }
            # Allocators may add cash (DCA), so value targets after they return.
            _, target_equity_base, _, _, _, _ = compute_portfolio_values(usd_inr)
            if allocation_kind == "BASE_WEIGHT":
                requested_target_weights = {
                    symbol: float(weight)
                    for symbol, weight in target_allocations.items()
                }
                # Hold back a slice of equity so commission and slippage are payable
                # without every rebalance falling into partial-fill trimming.
                # Incremental strategies (DCA) opt out and buffer their own new cash
                # instead, so the buffer never trims positions they already hold.
                investable_base = target_equity_base * (
                    1.0 - cash_buffer_pct if apply_cash_buffer else 1.0
                )
                buffer_multiplier = (
                    1.0 - cash_buffer_pct if apply_cash_buffer else 1.0
                )
                applied_target_weights = {
                    symbol: float(weight) * buffer_multiplier
                    for symbol, weight in target_allocations.items()
                }
                if buffer_multiplier < 1.0:
                    cash_buffer_trimmed = {
                        symbol
                        for symbol, weight in target_allocations.items()
                        if abs(float(weight)) > 1e-12
                    }
                target_allocations = {
                    symbol: _convert_base_to_native(
                        float(weight) * investable_base,
                        symbol_currencies[symbol],
                        base_currency,
                        usd_inr,
                    )
                    for symbol, weight in target_allocations.items()
                }
            else:
                strategy_prebuffered_targets = (
                    allocation_mode in {"WEIGHT", "EQUAL_WEIGHT"}
                    and apply_cash_buffer
                    and cash_buffer_pct > 0.0
                )
                for symbol, target_value_native in target_allocations.items():
                    target_value_base = _convert_native_to_base(
                        float(target_value_native),
                        symbol_currencies[symbol],
                        base_currency,
                        usd_inr,
                    )
                    weight = (
                        target_value_base / equity_base
                        if abs(equity_base) > 1e-12
                        else None
                    )
                    requested_target_weights[symbol] = (
                        weight / (1.0 - cash_buffer_pct)
                        if strategy_prebuffered_targets and weight is not None
                        else weight
                    )
                    applied_target_weights[symbol] = weight
                    if (
                        strategy_prebuffered_targets
                        and abs(float(target_value_native)) > 1e-12
                    ):
                        cash_buffer_trimmed.add(symbol)

            for symbol in cash_buffer_trimmed:
                requested_weight = requested_target_weights.get(symbol)
                applied_weight = applied_target_weights.get(symbol)
                if requested_weight is None or applied_weight is None:
                    continue
                constraint_specs_by_symbol[symbol].append(
                    TargetConstraint(
                        symbol=symbol,
                        constraint_name="cash_buffer",
                        bound_value=cash_buffer_pct,
                        pre_clamp_value=requested_weight,
                        applied_value=applied_weight,
                        reason=(
                            f"The configured {cash_buffer_pct:.6f} cash buffer "
                            "reduced the investable target."
                        ),
                        meta={"cash_buffer_pct": cash_buffer_pct},
                    )
                )

            numeric_applied_weights = {
                symbol: float(weight)
                for symbol, weight in applied_target_weights.items()
                if weight is not None
            }
            clamped_weights, risk_constraints = _clamp_target_weights(
                numeric_applied_weights,
                risk,
                financing,
            )
            if recorder.constraint_behavior == "FAIL":
                # max_weight is a new explicit constraint and therefore has no
                # legacy execution-stage check. Gross/net keep their existing
                # post-fill hard-fail semantics when clamping is not opted into.
                max_weight_constraint = next(
                    (
                        constraint
                        for constraint in risk_constraints
                        if constraint.constraint_name == "max_weight"
                    ),
                    None,
                )
                if max_weight_constraint is not None:
                    raise ValueError(max_weight_constraint.reason)
            if recorder.constraint_behavior == "RECORD_AND_CLAMP":
                applied_target_weights.update(clamped_weights)
                for constraint in risk_constraints:
                    constraint_specs_by_symbol[constraint.symbol].append(
                        constraint
                    )
                target_allocations = {
                    symbol: _convert_base_to_native(
                        float(weight) * target_equity_base,
                        symbol_currencies[symbol],
                        base_currency,
                        usd_inr,
                    )
                    for symbol, weight in clamped_weights.items()
                }
            orders = _targets_to_orders(
                state,
                target_allocations,
                prices,
                market_open,
                recorder=recorder,
                requested_target_weights=requested_target_weights,
                target_weights=applied_target_weights,
                cash_buffer_trimmed=cash_buffer_trimmed,
                constraint_specs_by_symbol=constraint_specs_by_symbol,
            )
            priority = {"SELL": 0, "COVER": 0, "SHORT": 1, "BUY": 1}
            for order in sorted(orders, key=lambda item: priority.get(item.side, 10)):
                currency = str(symbol_currencies[order.symbol]).upper()
                price = order.price
                exec_price = price
                slippage_native = 0.0
                trade_qty = order.qty
                if slippage.bps:
                    slip_rate = slippage.bps / 10000.0
                    if order.side in {"BUY", "COVER"}:
                        exec_price = price * (1.0 + slip_rate)
                    else:
                        exec_price = price * (1.0 - slip_rate)
                    slippage_native = abs(exec_price - price) * trade_qty

                notional = trade_qty * exec_price
                commission_native = 0.0
                if commission.bps or commission.min_fee_native:
                    commission_native = max(
                        notional * (commission.bps / 10000.0),
                        commission.min_fee_native,
                    )

                pos = state.positions[order.symbol]
                cash_bucket = state.cash_by_currency[currency]
                was_partially_trimmed = False
                if order.side == "SHORT" and not financing.shorting_enabled:
                    if recorder.constraint_behavior == "FAIL":
                        raise ValueError(
                            f"shorting is disabled but strategy requested a SHORT "
                            f"for {order.symbol}"
                        )
                    if order.decision is not None:
                        order.decision.outcome = "REJECTED_CONSTRAINT"
                        order.decision.reason = (
                            "Shorting is disabled for this run."
                        )
                        order.decision.executable_qty = 0.0
                    recorder.constraint(
                        order.decision,
                        "shorting_enabled",
                        bound_value=0.0,
                        pre_clamp_value=order.qty,
                        applied_value=0.0,
                        reason="Shorting is disabled for this run.",
                        meta={"side": order.side},
                    )
                    continue
                if order.side in {"BUY", "COVER"}:
                    total_cost = notional + commission_native
                    if not financing.margin_enabled:
                        _, _, cash_base_available, _, _, _ = compute_portfolio_values(
                            usd_inr
                        )
                        destination_cash_base = _convert_native_to_base(
                            max(cash_bucket, 0.0), currency, base_currency, usd_inr
                        )
                        sweepable_base = max(
                            0.0, cash_base_available - destination_cash_base
                        )
                        sweepable_native = _convert_base_to_native(
                            sweepable_base / (1.0 + slippage.bps / 10000.0),
                            currency,
                            base_currency,
                            usd_inr,
                        )
                        affordable_cash_native = max(cash_bucket, 0.0) + sweepable_native
                    else:
                        affordable_cash_native = float("inf")
                    if total_cost > affordable_cash_native + 1e-9:
                        affordable_qty = _max_affordable_qty(
                            cash_bucket=affordable_cash_native,
                            exec_price=exec_price,
                            commission_bps=commission.bps,
                            min_fee_native=commission.min_fee_native,
                        )
                        if order.side == "COVER":
                            affordable_qty = min(affordable_qty, abs(pos.qty))
                        if affordable_qty <= 1e-9:
                            if order.decision is not None:
                                order.decision.outcome = "REJECTED_CONSTRAINT"
                                order.decision.reason = (
                                    "Insufficient available cash for the minimum "
                                    "executable quantity."
                                )
                                order.decision.executable_qty = 0.0
                            recorder.constraint(
                                order.decision,
                                "cash_available",
                                bound_value=affordable_cash_native,
                                pre_clamp_value=order.qty,
                                applied_value=0.0,
                                reason=(
                                    "Available cash could not fund the minimum "
                                    "executable quantity."
                                ),
                                meta={"value_unit": "quantity"},
                            )
                            continue
                        trade_qty = affordable_qty
                        was_partially_trimmed = trade_qty < order.qty - 1e-9
                        if was_partially_trimmed:
                            recorder.constraint(
                                order.decision,
                                "cash_available",
                                bound_value=affordable_cash_native,
                                pre_clamp_value=order.qty,
                                applied_value=trade_qty,
                                reason=(
                                    "Order quantity was clamped to available cash."
                                ),
                                meta={"value_unit": "quantity"},
                            )
                        slippage_native = abs(exec_price - price) * trade_qty
                        notional = trade_qty * exec_price
                        commission_native = 0.0
                        if commission.bps or commission.min_fee_native:
                            commission_native = max(
                                notional * (commission.bps / 10000.0),
                                commission.min_fee_native,
                            )
                        total_cost = notional + commission_native
                        if total_cost > affordable_cash_native + 1e-9:
                            if order.decision is not None:
                                order.decision.outcome = "REJECTED_CONSTRAINT"
                                order.decision.reason = (
                                    "The cash constraint still failed after quantity trimming."
                                )
                                order.decision.executable_qty = 0.0
                            recorder.constraint(
                                order.decision,
                                "cash_available",
                                bound_value=affordable_cash_native,
                                pre_clamp_value=order.qty,
                                applied_value=0.0,
                                reason=(
                                    "The cash constraint still failed after "
                                    "quantity trimming."
                                ),
                                meta={"value_unit": "quantity"},
                            )
                            continue
                    fund_native_cash_with_fx(
                        day=day,
                        native_currency=currency,
                        required_native=total_cost,
                        usd_inr=usd_inr,
                    )
                    cash_bucket = state.cash_by_currency[currency]
                    state.cash_by_currency[currency] = cash_bucket - total_cost
                    if order.side == "BUY":
                        if pos.qty < -1e-9:
                            raise ValueError("BUY cannot be used to close short inventory; use COVER.")
                        new_qty = pos.qty + trade_qty
                        pos.avg_cost_native = (
                            ((pos.avg_cost_native * pos.qty) + notional) / new_qty if new_qty else 0.0
                        )
                        pos.qty = new_qty
                        lots_by_symbol[order.symbol].append(
                            TaxLot(
                                qty=trade_qty,
                                unit_cost_native=exec_price,
                                opened_on=day,
                                opening_commission_native_per_unit=(
                                    commission_native / trade_qty if trade_qty else 0.0
                                ),
                            )
                        )
                    else:
                        if pos.qty >= -1e-9:
                            raise ValueError("No short inventory to cover.")
                        if trade_qty > abs(pos.qty) + 1e-9:
                            raise ValueError(
                                f"insufficient shares to cover {order.symbol}: want {trade_qty:.6f}, "
                                f"have {abs(pos.qty):.6f}"
                            )
                        realize_lots_and_accrue_tax(
                            day=day,
                            symbol=order.symbol,
                            side="COVER",
                            qty=trade_qty,
                            exec_price=exec_price,
                            symbol_currency=currency,
                            usd_inr=usd_inr,
                            closing_commission_native=commission_native,
                        )
                        pos.qty += trade_qty
                        if abs(pos.qty) <= 1e-9:
                            pos.qty = 0.0
                            pos.avg_cost_native = 0.0
                elif order.side == "SELL":
                    if pos.qty <= 1e-9:
                        raise ValueError("No long inventory to sell.")
                    if trade_qty > pos.qty + 1e-9:
                        raise ValueError(
                            f"insufficient shares to sell {order.symbol}: want {trade_qty:.6f}, "
                            f"have {pos.qty:.6f}"
                        )
                    pos.qty -= trade_qty
                    state.cash_by_currency[currency] = cash_bucket + notional - commission_native
                    realize_lots_and_accrue_tax(
                        day=day,
                        symbol=order.symbol,
                        side="SELL",
                        qty=trade_qty,
                        exec_price=exec_price,
                        symbol_currency=currency,
                        usd_inr=usd_inr,
                        closing_commission_native=commission_native,
                    )
                    if pos.qty <= 1e-9:
                        pos.qty = 0.0
                        pos.avg_cost_native = 0.0
                elif order.side == "SHORT":
                    if pos.qty > 1e-9:
                        if recorder.constraint_behavior == "FAIL":
                            raise ValueError(
                                "SHORT cannot be used while long inventory is open."
                            )
                        if order.decision is not None:
                            order.decision.outcome = "REJECTED_CONSTRAINT"
                            order.decision.reason = (
                                "Short inventory cannot be opened while long inventory remains."
                            )
                            order.decision.executable_qty = 0.0
                        recorder.constraint(
                            order.decision,
                            "inventory_side",
                            bound_value=0.0,
                            pre_clamp_value=pos.qty,
                            applied_value=pos.qty,
                            reason=(
                                "Short inventory cannot be opened while long "
                                "inventory remains."
                            ),
                            meta={"side": order.side},
                        )
                        continue
                    prev_abs = abs(pos.qty)
                    new_abs = prev_abs + trade_qty
                    pos.avg_cost_native = (
                        ((pos.avg_cost_native * prev_abs) + notional) / new_abs if new_abs else 0.0
                    )
                    pos.qty -= trade_qty
                    state.cash_by_currency[currency] = cash_bucket + notional - commission_native
                    lots_by_symbol[order.symbol].append(
                        TaxLot(
                            qty=trade_qty,
                            unit_cost_native=exec_price,
                            opened_on=day,
                            opening_commission_native_per_unit=(
                                commission_native / trade_qty if trade_qty else 0.0
                            ),
                        )
                    )
                else:
                    raise ValueError(f"Unsupported order side '{order.side}'")

                adjustments = (
                    ["TRIMMED_CASH_BUFFER"] if order.cash_buffer_trimmed else []
                )
                if was_partially_trimmed:
                    adjustments.append("TRIMMED_PARTIAL")
                    order_status = "TRIMMED_PARTIAL"
                    order_reason = "Order quantity was reduced to available cash."
                elif "TRIMMED_CASH_BUFFER" in adjustments:
                    order_status = "TRIMMED_CASH_BUFFER"
                    order_reason = (
                        "Target allocation was reduced by the configured cash buffer."
                    )
                else:
                    order_status = "FILLED"
                    order_reason = None
                if order.decision is not None:
                    order.decision.executable_qty = trade_qty
                    order.decision.outcome = order_status
                    order.decision.reason = order_reason
                    order.decision.meta["adjustments"] = adjustments
                    order.decision.meta["terminal_status"] = "FILLED"

                order_id = uuid4()
                if order.decision is not None:
                    order.decision.order_id = order_id
                order_rows.append(
                    RunOrder(
                        order_id=order_id,
                        run_id=run.run_id,
                        date=day,
                        symbol=order.symbol,
                        side=order.side,
                        qty=trade_qty,
                        order_type="MKT",
                        limit_price=None,
                        status=order_status,
                        meta={
                            "reason": order_reason,
                            "adjustments": adjustments,
                            "intended_qty": order.qty,
                            "executable_qty": trade_qty,
                            "terminal_status": "FILLED",
                        },
                    )
                )

                fees_cum_by_currency[currency] += commission_native + slippage_native

                # FX sweeps never reach this loop -- they are written directly by
                # fund_native_cash_with_fx -- so currency conversions stay out of turnover.
                turnover_notional_base += abs(
                    _convert_native_to_base(notional, currency, base_currency, usd_inr)
                )

                fill_rows.append(
                    RunFill(
                        fill_id=uuid4(),
                        order_id=order_id,
                        run_id=run.run_id,
                        date=day,
                        symbol=order.symbol,
                        qty=trade_qty,
                        price_native=exec_price,
                        commission_native=commission_native,
                        slippage_native=slippage_native,
                        notional_native=notional,
                        meta={},
                    )
                )
                assert_risk_limits(usd_inr)

        settle_negative_native_cash(day, usd_inr)

        (
            equity_by_currency,
            equity,
            cash_value,
            gross_exposure,
            net_exposure,
            short_notional_base,
        ) = compute_portfolio_values(usd_inr)

        margin_borrowed_base = sum(
            _convert_native_to_base(
                abs(amount), currency, base_currency, usd_inr
            )
            for currency, amount in state.cash_by_currency.items()
            if amount < 0.0
        )
        margin_interest_base = 0.0
        if include_financing and financing.margin_enabled:
            for currency, amount in list(state.cash_by_currency.items()):
                if amount >= 0.0:
                    continue
                interest_native = abs(amount) * (
                    financing.daily_margin_interest_bps / 10000.0
                )
                state.cash_by_currency[currency] -= interest_native
                margin_interest_base += _convert_native_to_base(
                    interest_native, currency, base_currency, usd_inr
                )

        borrow_fee_base = 0.0
        if include_financing and financing.shorting_enabled:
            for symbol, position in state.positions.items():
                price = state.last_price.get(symbol)
                if position.qty >= 0.0 or price is None:
                    continue
                currency = str(symbol_currencies[symbol]).upper()
                fee_native = abs(position.qty * price) * (
                    financing.daily_borrow_fee_bps / 10000.0
                )
                state.cash_by_currency[currency] -= fee_native
                borrow_fee_base += _convert_native_to_base(
                    fee_native, currency, base_currency, usd_inr
                )

        if margin_interest_base or borrow_fee_base:
            borrow_cum_base += borrow_fee_base
            margin_cum_base += margin_interest_base
            (
                equity_by_currency,
                equity,
                cash_value,
                gross_exposure,
                net_exposure,
                short_notional_base,
            ) = compute_portfolio_values(usd_inr)
            assert_risk_limits(usd_inr)

        fees_cum_value = 0.0
        for currency, fee_val in fees_cum_by_currency.items():
            fees_cum_value += _convert_native_to_base(fee_val, currency, base_currency, usd_inr)

        for symbol, pos in state.positions.items():
            price = state.last_price[symbol]
            if price is None:
                market_value_base = 0.0
                unrealized_base = 0.0
            else:
                market_value_native = pos.qty * price
                unrealized_native = (price - pos.avg_cost_native) * pos.qty
                currency = str(symbol_currencies[symbol]).upper()
                market_value_base = _convert_native_to_base(
                    market_value_native, currency, base_currency, usd_inr
                )
                unrealized_base = _convert_native_to_base(
                    unrealized_native, currency, base_currency, usd_inr
                )

            if pos.qty != 0:
                position_rows.append(
                    RunPosition(
                        run_id=run.run_id,
                        date=day,
                        symbol=symbol,
                        qty=pos.qty,
                        avg_cost_native=pos.avg_cost_native,
                        market_value_base=market_value_base,
                        unrealized_pnl_base=unrealized_base,
                    )
                )

        if peak_equity_base is None:
            peak_equity_base = equity
        elif equity > peak_equity_base:
            peak_equity_base = equity
        if peak_equity_base:
            drawdown = equity / peak_equity_base - 1.0
        else:
            drawdown = 0.0

        equity_series_base.append(equity)
        equity_dates.append(day)
        fees_cum_series_base.append(fees_cum_value)
        taxes_cum_series_base.append(taxes_cum_base)
        borrow_cum_series_base.append(borrow_cum_base)
        margin_cum_series_base.append(margin_cum_base)

        equity_rows.append(
            RunDailyEquity(
                run_id=run.run_id,
                date=day,
                equity_base=equity,
                cash_base=cash_value,
                gross_exposure_base=gross_exposure,
                net_exposure_base=net_exposure,
                drawdown=drawdown,
                fees_cum_base=fees_cum_value,
                taxes_cum_base=taxes_cum_base,
                borrow_fees_cum_base=borrow_cum_base,
                margin_interest_cum_base=margin_cum_base,
                equity_by_currency=equity_by_currency,
                cash_by_currency=dict(state.cash_by_currency),
                fees_cum_by_currency=dict(fees_cum_by_currency),
            )
        )

        previous_attribution_qty.clear()
        previous_attribution_qty.update(
            {
                symbol: float(position.qty)
                for symbol, position in state.positions.items()
                if abs(float(position.qty)) > 1e-12
            }
        )
        previous_attribution_price_base.clear()
        previous_attribution_price_base.update(current_price_base_by_symbol)
        previous_attribution_equity_base = equity

        if include_financing:
            financing_rows.append(
                RunFinancing(
                    run_id=run.run_id,
                    date=day,
                    margin_borrowed_base=margin_borrowed_base,
                    margin_interest_base=margin_interest_base,
                    short_notional_base=short_notional_base,
                    borrow_fee_base=borrow_fee_base,
                )
            )
        recorder.finish_bar()

    symbol_set = set(symbols)
    first_observed_price: Dict[str, float] = {}
    for _, _, _, _, row_symbol, row_close in rows:
        if row_symbol is None or row_symbol not in symbol_set or row_close is None:
            continue
        if row_symbol not in first_observed_price:
            first_observed_price[row_symbol] = float(row_close)
    missing_symbol_prices = sorted(symbol for symbol in symbols if symbol not in first_observed_price)
    if missing_symbol_prices:
        raise DataUnavailableError(
            "Missing price coverage for symbols in selected date range: "
            f"{missing_symbol_prices}"
        )

    current_date: date | None = None
    flags: Dict[str, bool] | None = None
    day_prices: Dict[str, float | None] = {symbol: None for symbol in symbols}

    for dt, is_us, is_in, is_fx, symbol, close in rows:
        if current_date is None:
            current_date = dt
        if dt != current_date:
            process_day(current_date, flags, day_prices)
            current_date = dt
            flags = None
            day_prices = {symbol: None for symbol in symbols}

        flags = {
            "is_us_trading": bool(is_us),
            "is_in_trading": bool(is_in),
            "is_fx_trading": bool(is_fx),
        }
        if symbol is not None and symbol in symbol_set:
            day_prices[symbol] = float(close) if close is not None else None

    process_day(current_date, flags, day_prices)

    if any(ccy != base_currency for ccy in currencies) and first_observed_usd_inr is None:
        raise DataUnavailableError("Missing USDINR history for mixed-currency base conversion.")
    initial_cash_base = initial_cash_base_at_evaluation
    if initial_cash_base is None:
        raise NoTradingDaysError(
            "No evaluation days found on or after evaluation_start_date."
        )

    benchmark_series_base = _align_benchmark_to_base(
        equity_dates,
        benchmark_prices_native,
        benchmark_currency,
        base_currency,
        usd_inr_by_date,
    )
    first_benchmark_value = next(
        (
            value
            for value in benchmark_series_base
            if value is not None and abs(value) > 1e-12
        ),
        None,
    )
    if first_benchmark_value is not None and initial_cash_base > 0.0:
        benchmark_scale = initial_cash_base / first_benchmark_value
        benchmark_series_base = [
            value * benchmark_scale if value is not None else None
            for value in benchmark_series_base
        ]
    else:
        benchmark_series_base = [None for _value in benchmark_series_base]

    for equity_row, benchmark_equity in zip(equity_rows, benchmark_series_base):
        equity_row.benchmark_equity_base = benchmark_equity

    if equity_rows:
        db.bulk_save_objects(equity_rows)
    if order_rows:
        db.bulk_save_objects(order_rows)
    if fill_rows:
        db.bulk_save_objects(fill_rows)
    if position_rows:
        db.bulk_save_objects(position_rows)
    if financing_rows:
        db.bulk_save_objects(financing_rows)
    if tax_event_rows:
        db.bulk_save_objects(tax_event_rows)
    if tax_lot_consumption_rows:
        db.bulk_save_objects(tax_lot_consumption_rows)
    if recorder.signal_rows:
        db.bulk_save_objects(recorder.signal_rows)
    if recorder.decision_rows:
        db.bulk_save_objects(recorder.decision_rows)
    if recorder.constraint_rows:
        db.bulk_save_objects(recorder.constraint_rows)

    risk_free_rate_annual = float(
        (config_snapshot.get("risk") or {}).get("risk_free_rate_annual") or 0.0
    )
    metrics = _compute_metrics(
        equity_series_base,
        fees_cum_series_base,
        initial_cash=initial_cash_base,
        turnover_notional_base=turnover_notional_base,
        benchmark_series_base=benchmark_series_base,
        risk_free_rate_annual=risk_free_rate_annual,
    )
    if initial_cash_base:
        metrics["tax_drag"] = taxes_cum_base / initial_cash_base
        metrics["borrow_drag"] = borrow_cum_base / initial_cash_base
        metrics["margin_interest_drag"] = margin_cum_base / initial_cash_base
    else:
        metrics["tax_drag"] = None
        metrics["borrow_drag"] = None
        metrics["margin_interest_drag"] = None
    winning_trades = [value for value in realized_trade_pnl_base if value > 0.0]
    losing_trades = [value for value in realized_trade_pnl_base if value < 0.0]
    metrics_meta = {
        "currencies": currencies,
        "base_currency": base_currency,
        "benchmark": benchmark,
        "calmar": metrics["calmar"],
        "var_95": metrics["var_95"],
        "cvar_95": metrics["cvar_95"],
        "best_day": metrics["best_day"],
        "worst_day": metrics["worst_day"],
        "win_rate": metrics["win_rate"],
        "avg_win_day": metrics["avg_win_day"],
        "avg_loss_day": metrics["avg_loss_day"],
        "beta": metrics["beta"],
        "alpha": metrics["alpha"],
        "tracking_error": metrics["tracking_error"],
        "information_ratio": metrics["information_ratio"],
        "risk_free_rate_annual": risk_free_rate_annual,
        "initial_cash_base": initial_cash_base,
        "return_contribution_by_symbol": return_contribution_by_symbol,
        "avg_winning_trade": (
            sum(winning_trades) / len(winning_trades) if winning_trades else None
        ),
        "avg_losing_trade": (
            sum(losing_trades) / len(losing_trades) if losing_trades else None
        ),
        "trade_win_rate": (
            len(winning_trades) / len(realized_trade_pnl_base)
            if realized_trade_pnl_base
            else None
        ),
        "avg_commission_per_trade": (
            sum(realized_trade_commissions_base) / len(realized_trade_commissions_base)
            if realized_trade_commissions_base
            else None
        ),
        "turnover_convention": "two_way_annualized",
        "explain_capture": {
            "enabled": recorder.enabled,
            "signal_records": len(recorder.signal_rows),
            "order_decision_records": len(recorder.decision_rows),
            "constraint_records": len(recorder.constraint_rows),
            "truncated": recorder.truncated,
        },
    }

    metrics_meta.update(
        {
            "requested_start_date": requested_start_date.isoformat(),
            "requested_end_date": requested_end_date.isoformat(),
            "evaluation_start_date": evaluation_start_date.isoformat(),
            "effective_start_date": effective_start_date.isoformat(),
            "effective_end_date": effective_end_date.isoformat(),
            "date_shift_warnings": date_shift_warnings,
            "run_id": str(run.run_id),
            "seed": run.seed,
            "data_snapshot_id": run.data_snapshot_id,
            "config_version": config_snapshot.get("version"),
            "universe_summary": universe_summary,
        }
    )

    db.add(
        RunMetric(
            run_id=run.run_id,
            cagr=metrics["cagr"],
            volatility=metrics["volatility"],
            sharpe=metrics["sharpe"],
            sortino=metrics["sortino"],
            max_drawdown=metrics["max_drawdown"],
            turnover=metrics["turnover"],
            gross_return=metrics["gross_return"],
            net_return=metrics["net_return"],
            fee_drag=metrics["fee_drag"],
            tax_drag=metrics["tax_drag"],
            borrow_drag=metrics["borrow_drag"],
            margin_interest_drag=metrics["margin_interest_drag"],
            beta=metrics["beta"],
            alpha=metrics["alpha"],
            tracking_error=metrics["tracking_error"],
            information_ratio=metrics["information_ratio"],
            meta=metrics_meta,
        )
    )
    return len(equity_rows)
