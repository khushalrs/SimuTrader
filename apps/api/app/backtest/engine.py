"""Reusable backtest engine core."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from math import sqrt
from typing import Any, Callable, Dict, Iterable
from uuid import uuid4

from sqlalchemy.orm import Session

from app.data.duckdb import get_duckdb_conn
from app.backtest.errors import DataUnavailableError, NoTradingDaysError
from app.models.backtests import (
    BacktestRun,
    RunDailyEquity,
    RunFill,
    RunFinancing,
    RunMetric,
    RunOrder,
    RunPosition,
    RunTaxEvent,
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


@dataclass
class OrderSpec:
    symbol: str
    side: str
    qty: float
    price: float


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


TargetAllocator = Callable[[DayContext], Dict[str, float] | None]


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
          AND date BETWEEN ? AND ?
        ORDER BY date
        """,
        [start_date, end_date],
    ).fetchall()
    return {row_date: float(close) for row_date, close in rows if close is not None}


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
    return RiskSpec(max_gross_leverage=max_gross, max_net_leverage=max_net)


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

    candidate = max(qty_min_fee, qty_bps, 0.0)
    # Ensure strict affordability under the exact commission formula.
    notional = candidate * exec_price
    commission = max(notional * bps_rate, min_fee)
    total = notional + commission
    if total > cash_bucket:
        # Deterministic fallback when floating-point pushes just over budget.
        candidate *= 0.999999
    return max(candidate, 0.0)


def _compute_metrics(
    equity_series: list[float],
    fees_cum_series: list[float] | None = None,
    initial_cash: float | None = None,
) -> dict[str, float | None]:
    if len(equity_series) < 2:
        return {
            "cagr": None,
            "volatility": None,
            "sharpe": None,
            "max_drawdown": None,
            "gross_return": None,
            "net_return": None,
            "fee_drag": 0.0,
            "tax_drag": 0.0,
            "borrow_drag": 0.0,
            "margin_interest_drag": 0.0,
        }

    initial = initial_cash if initial_cash is not None else equity_series[0]
    final = equity_series[-1]
    net_return = final / initial - 1.0 if initial else None

    daily_returns: list[float] = []
    for prev, curr in zip(equity_series[:-1], equity_series[1:]):
        if prev != 0:
            daily_returns.append(curr / prev - 1.0)

    if daily_returns:
        mean_ret = sum(daily_returns) / len(daily_returns)
        if len(daily_returns) > 1:
            variance = sum((r - mean_ret) ** 2 for r in daily_returns) / (len(daily_returns) - 1)
        else:
            variance = 0.0
        std_ret = sqrt(variance)
        volatility = std_ret * sqrt(252.0) if std_ret else 0.0
        sharpe = (mean_ret * 252.0) / volatility if volatility else None
        if initial > 0 and final > 0:
            cagr = (final / initial) ** (252.0 / len(daily_returns)) - 1.0
        else:
            cagr = None
    else:
        volatility = None
        sharpe = None
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

    return {
        "cagr": cagr,
        "volatility": volatility,
        "sharpe": sharpe,
        "max_drawdown": max_drawdown,
        "gross_return": gross_return,
        "net_return": net_return,
        "fee_drag": fee_drag,
        "tax_drag": 0.0,
        "borrow_drag": 0.0,
        "margin_interest_drag": 0.0,
    }


def _targets_to_orders(
    state: PortfolioState,
    target_allocations: Dict[str, float],
    prices: Dict[str, float | None],
    market_open: Dict[str, bool],
) -> list[OrderSpec]:
    orders: list[OrderSpec] = []
    for symbol, target_value in target_allocations.items():
        if symbol not in state.positions:
            raise ValueError(f"Unknown symbol in target allocation: {symbol}")
        if not market_open.get(symbol):
            continue
        price = prices.get(symbol)
        if price is None:
            continue

        current_qty = state.positions[symbol].qty
        target_qty = target_value / price if price else 0.0
        if abs(target_qty - current_qty) < 1e-9:
            continue

        if current_qty >= 0 and target_qty >= 0:
            delta = target_qty - current_qty
            if delta > 1e-9:
                orders.append(OrderSpec(symbol=symbol, side="BUY", qty=delta, price=price))
            elif delta < -1e-9:
                orders.append(
                    OrderSpec(symbol=symbol, side="SELL", qty=abs(delta), price=price)
                )
        elif current_qty <= 0 and target_qty <= 0:
            if target_qty < current_qty - 1e-9:
                orders.append(
                    OrderSpec(
                        symbol=symbol,
                        side="SHORT",
                        qty=abs(target_qty - current_qty),
                        price=price,
                    )
                )
            elif target_qty > current_qty + 1e-9:
                orders.append(
                    OrderSpec(
                        symbol=symbol,
                        side="COVER",
                        qty=abs(target_qty - current_qty),
                        price=price,
                    )
                )
        elif current_qty > 0 and target_qty < 0:
            orders.append(OrderSpec(symbol=symbol, side="SELL", qty=current_qty, price=price))
            orders.append(OrderSpec(symbol=symbol, side="SHORT", qty=abs(target_qty), price=price))
        elif current_qty < 0 and target_qty > 0:
            orders.append(OrderSpec(symbol=symbol, side="COVER", qty=abs(current_qty), price=price))
            orders.append(OrderSpec(symbol=symbol, side="BUY", qty=target_qty, price=price))

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
) -> int:
    symbols = [inst["symbol"] for inst in instruments]
    policy = _normalize_missing_bar_policy(missing_bar_policy)
    _ = _normalize_fill_price_policy(fill_price_policy)
    config_snapshot = run.config_snapshot or {}
    base_currency = str(config_snapshot.get("base_currency") or "USD").upper()
    fx_policy = _normalize_missing_fx_policy(
        missing_fx_policy or (config_snapshot.get("data_policy") or {}).get("missing_fx")
    )
    financing = _parse_financing(config_snapshot.get("financing"))
    risk = _parse_risk(config_snapshot.get("risk"), financing)
    tax_spec = _parse_tax(config_snapshot.get("tax"))
    commission = _parse_commission(commission_cfg)
    slippage = _parse_slippage(slippage_cfg)
    allocation_mode = str(allocation_mode or "").upper()

    con = get_duckdb_conn()
    try:
        _ensure_calendar_views(con)
        symbol_currencies = _fetch_symbol_currencies(con, symbols)
        usd_inr_by_date = _fetch_usd_inr_rates(con, start_date, end_date)
        rows = _fetch_calendar_with_prices(con, symbols, start_date, end_date)
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
    multi_currency = len(currencies) > 1
    if len(instrument_currencies) > 1 and allocation_mode != "AMOUNT":
        raise ValueError(
            "Multi-currency runs require explicit amount allocations per instrument."
        )

    if initial_cash_by_currency:
        cash_by_currency = {
            currency: float(initial_cash_by_currency.get(currency, 0.0))
            for currency in currencies
        }
        missing_cash = [currency for currency in instrument_currencies if currency not in initial_cash_by_currency]
        if missing_cash:
            raise ValueError(
                f"initial_cash_by_currency missing values for currencies: {missing_cash}"
            )
    else:
        if len(instrument_currencies) > 1:
            raise ValueError(
                "initial_cash_by_currency is required when the universe spans multiple currencies."
            )
        currency = instrument_currencies[0] if instrument_currencies else base_currency
        cash_by_currency = {ccy: 0.0 for ccy in currencies}
        cash_by_currency[currency] = float(initial_cash)
    cash_by_currency.setdefault(base_currency, 0.0)

    db.query(RunDailyEquity).filter(RunDailyEquity.run_id == run.run_id).delete(
        synchronize_session=False
    )
    db.query(RunMetric).filter(RunMetric.run_id == run.run_id).delete(
        synchronize_session=False
    )
    db.query(RunOrder).filter(RunOrder.run_id == run.run_id).delete(
        synchronize_session=False
    )
    db.query(RunFill).filter(RunFill.run_id == run.run_id).delete(
        synchronize_session=False
    )
    db.query(RunPosition).filter(RunPosition.run_id == run.run_id).delete(
        synchronize_session=False
    )
    db.query(RunFinancing).filter(RunFinancing.run_id == run.run_id).delete(
        synchronize_session=False
    )
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
    fees_cum_by_currency: Dict[str, float] = {currency: 0.0 for currency in currencies}
    equity_series_base: list[float] = []
    fees_cum_series_base: list[float] = []
    taxes_cum_series_base: list[float] = []
    borrow_cum_series_base: list[float] = []
    margin_cum_series_base: list[float] = []
    taxes_cum_base = 0.0
    borrow_cum_base = 0.0
    margin_cum_base = 0.0
    peak_equity_base: float | None = None

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

    def realize_lots_and_accrue_tax(
        *,
        day: date,
        symbol: str,
        side: str,
        qty: float,
        exec_price: float,
        symbol_currency: str,
        usd_inr: float | None,
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
            bucket, tax_rate = _tax_bucket_and_rate(tax_spec, holding_days)
            tax_due_base = max(realized_base, 0.0) * tax_rate
            taxes_cum_base += tax_due_base
            state.cash_by_currency[base_currency] = (
                state.cash_by_currency.get(base_currency, 0.0) - tax_due_base
            )

            tax_event_rows.append(
                RunTaxEvent(
                    tax_event_id=uuid4(),
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
        if day is None:
            return
        if flags is None:
            flags = {"is_us_trading": False, "is_in_trading": False, "is_fx_trading": False}

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
        ctx = DayContext(
            date=day,
            flags=flags,
            prices=prices,
            market_open=market_open,
            state=state,
        )
        target_allocations = target_allocations_fn(ctx)

        if target_allocations:
            orders = _targets_to_orders(state, target_allocations, prices, market_open)
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
                if order.side in {"BUY", "COVER"}:
                    total_cost = notional + commission_native
                    if not financing.margin_enabled and total_cost > cash_bucket + 1e-9:
                        affordable_qty = _max_affordable_qty(
                            cash_bucket=cash_bucket,
                            exec_price=exec_price,
                            commission_bps=commission.bps,
                            min_fee_native=commission.min_fee_native,
                        )
                        if order.side == "COVER":
                            affordable_qty = min(affordable_qty, abs(pos.qty))
                        if affordable_qty <= 1e-9:
                            continue
                        trade_qty = affordable_qty
                        slippage_native = abs(exec_price - price) * trade_qty
                        notional = trade_qty * exec_price
                        commission_native = 0.0
                        if commission.bps or commission.min_fee_native:
                            commission_native = max(
                                notional * (commission.bps / 10000.0),
                                commission.min_fee_native,
                            )
                        total_cost = notional + commission_native
                        if total_cost > cash_bucket + 1e-9:
                            continue
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
                            TaxLot(qty=trade_qty, unit_cost_native=exec_price, opened_on=day)
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
                    )
                    if pos.qty <= 1e-9:
                        pos.qty = 0.0
                        pos.avg_cost_native = 0.0
                elif order.side == "SHORT":
                    if not financing.shorting_enabled:
                        raise ValueError(
                            f"shorting is disabled but strategy requested a SHORT for {order.symbol}"
                        )
                    if pos.qty > 1e-9:
                        raise ValueError("SHORT cannot be used while long inventory is open.")
                    prev_abs = abs(pos.qty)
                    new_abs = prev_abs + trade_qty
                    pos.avg_cost_native = (
                        ((pos.avg_cost_native * prev_abs) + notional) / new_abs if new_abs else 0.0
                    )
                    pos.qty -= trade_qty
                    state.cash_by_currency[currency] = cash_bucket + notional - commission_native
                    lots_by_symbol[order.symbol].append(
                        TaxLot(qty=trade_qty, unit_cost_native=exec_price, opened_on=day)
                    )
                else:
                    raise ValueError(f"Unsupported order side '{order.side}'")

                order_id = uuid4()
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
                        status="FILLED",
                        meta={},
                    )
                )

                fees_cum_by_currency[currency] += commission_native + slippage_native

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

        (
            equity_by_currency,
            equity,
            cash_value,
            gross_exposure,
            net_exposure,
            short_notional_base,
        ) = compute_portfolio_values(usd_inr)

        margin_borrowed_base = max(0.0, -cash_value)
        margin_interest_base = (
            margin_borrowed_base * (financing.daily_margin_interest_bps / 10000.0)
            if include_financing and financing.margin_enabled
            else 0.0
        )
        borrow_fee_base = (
            short_notional_base * (financing.daily_borrow_fee_bps / 10000.0)
            if include_financing and financing.shorting_enabled
            else 0.0
        )
        financing_total_base = margin_interest_base + borrow_fee_base
        if financing_total_base:
            state.cash_by_currency[base_currency] = (
                state.cash_by_currency.get(base_currency, 0.0) - financing_total_base
            )
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

    if any(ccy != base_currency for ccy in currencies) and first_observed_usd_inr is None:
        raise DataUnavailableError("Missing USDINR history for mixed-currency base conversion.")
    initial_cash_base = 0.0
    for currency, amount in initial_cash_snapshot.items():
        initial_cash_base += _convert_native_to_base(
            amount, currency, base_currency, first_observed_usd_inr
        )

    metrics = _compute_metrics(
        equity_series_base,
        fees_cum_series_base,
        initial_cash=initial_cash_base,
    )
    if initial_cash_base:
        metrics["tax_drag"] = taxes_cum_base / initial_cash_base
        metrics["borrow_drag"] = borrow_cum_base / initial_cash_base
        metrics["margin_interest_drag"] = margin_cum_base / initial_cash_base
    else:
        metrics["tax_drag"] = None
        metrics["borrow_drag"] = None
        metrics["margin_interest_drag"] = None
    metrics_meta = {"currencies": currencies, "base_currency": base_currency}

    metrics_meta.update(
        {
            "requested_start_date": requested_start_date.isoformat(),
            "requested_end_date": requested_end_date.isoformat(),
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
            sortino=None,
            max_drawdown=metrics["max_drawdown"],
            turnover=None,
            gross_return=metrics["gross_return"],
            net_return=metrics["net_return"],
            fee_drag=metrics["fee_drag"],
            tax_drag=metrics["tax_drag"],
            borrow_drag=metrics["borrow_drag"],
            margin_interest_drag=metrics["margin_interest_drag"],
            meta=metrics_meta,
        )
    )
    return len(equity_rows)
