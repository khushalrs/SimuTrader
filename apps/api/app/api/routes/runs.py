import csv
import io
from datetime import date, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response, status
from fastapi.responses import HTMLResponse, StreamingResponse
from jinja2 import BaseLoader, Environment, select_autoescape
from jinja2.exceptions import UndefinedError
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db import get_db
from app.data.duckdb import get_duckdb_conn
from app.models.backtests import (
    BacktestRun,
    RunDailyEquity,
    RunFill,
    RunMetric,
    RunOrder,
    RunPosition,
    RunTaxEvent,
)
from app.models.assets import Asset
from app.security import ActorContext, get_current_actor
from app.services.capabilities import country_for_asset_class, currency_for_asset_class
from app.services.redis_store import (
    get_cached_run_status,
    get_cached_top_holdings,
    set_cached_run_status,
    set_cached_run_summary,
    set_cached_top_holdings,
)
from app.schemas.backtests import (
    BacktestOut,
    BacktestStatusOut,
    RunCostsSummaryOut,
    RunDailyEquityOut,
    RunExplainOut,
    RunExposureBreakdownOut,
    RunExposurePointOut,
    RunFillOut,
    RunMetricOut,
    RunPositionOut,
    RunCloneRequest,
    RunScenarioRequest,
    RunTaxEventOut,
)
from app.services.scenario import build_clone_config, build_scenario_config
from app.services.preflight import _query_symbol_coverage

router = APIRouter(prefix="/runs", tags=["runs"])
GLOBAL_PRESET_ACTOR_PREFIX = "preset:global:"

_REPORT_HTML_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{{ run.name or "Backtest report" }} · SimuTrader</title>
  <style>
    :root { color-scheme: light; --ink:#172033; --muted:#667085; --line:#d8dee9; --panel:#f7f9fc; --brand:#3157d5; --negative:#b42318; }
    * { box-sizing:border-box; }
    body { margin:0; color:var(--ink); background:#fff; font:14px/1.45 Inter, ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif; }
    main { max-width:980px; margin:0 auto; padding:36px; }
    header { display:flex; justify-content:space-between; gap:24px; align-items:flex-start; border-bottom:2px solid var(--ink); padding-bottom:20px; }
    .brand { display:flex; align-items:center; gap:12px; }
    h1 { font-size:26px; margin:0 0 4px; } h2 { font-size:16px; margin:26px 0 10px; }
    p { margin:5px 0; } .muted { color:var(--muted); } .right { text-align:right; }
    .badge { display:inline-block; padding:4px 9px; border:1px solid var(--line); border-radius:999px; font-size:12px; font-weight:700; }
    .summary { margin:22px 0; padding:16px 18px; border-left:4px solid var(--brand); background:var(--panel); font-size:16px; }
    .grid { display:grid; grid-template-columns:repeat(4, 1fr); gap:10px; }
    .two { display:grid; grid-template-columns:repeat(2, 1fr); gap:12px; }
    .card { border:1px solid var(--line); border-radius:8px; padding:12px; break-inside:avoid; }
    .label { color:var(--muted); font-size:11px; text-transform:uppercase; letter-spacing:.06em; }
    .value { margin-top:4px; font-size:19px; font-weight:750; font-variant-numeric:tabular-nums; }
    table { width:100%; border-collapse:collapse; font-variant-numeric:tabular-nums; }
    th, td { padding:8px 10px; border-bottom:1px solid var(--line); text-align:left; }
    th { color:var(--muted); font-size:11px; text-transform:uppercase; letter-spacing:.05em; }
    td:last-child, th:last-child { text-align:right; }
    .chart { width:100%; height:auto; border:1px solid var(--line); border-radius:8px; background:#fff; }
    footer { margin-top:30px; padding-top:12px; border-top:1px solid var(--line); color:var(--muted); font-size:11px; }
    @page { size:A4; margin:14mm; }
    @media print { main { max-width:none; padding:0; } .card, table, .chart { break-inside:avoid; } }
    @media (max-width:700px) { main { padding:20px; } .grid, .two { grid-template-columns:repeat(2, 1fr); } }
  </style>
</head>
<body><main>
  <header>
    <div>
      <div class="brand">
        <svg width="34" height="34" viewBox="0 0 34 34" role="img" aria-label="SimuTrader logo" xmlns="http://www.w3.org/2000/svg">
          <rect width="34" height="34" rx="8" fill="#3157d5"/><path d="M7 23l6-7 5 4 9-11" fill="none" stroke="#fff" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
        <div><h1>{{ run.name or "Backtest report" }}</h1><div class="muted">Run {{ run.run_id }}</div></div>
      </div>
    </div>
    <div class="right"><span class="badge">{{ run.status }}</span><p class="muted">Snapshot {{ run.data_snapshot_id }}</p></div>
  </header>

  {% if explanation %}<div class="summary"><strong>{{ explanation.headline }}</strong><br>{{ explanation.summary }}</div>{% endif %}

  <section><h2>Performance</h2><div class="grid">
    <div class="card"><div class="label">Net return</div><div class="value">{{ metrics.net_return|pct }}</div></div>
    <div class="card"><div class="label">CAGR</div><div class="value">{{ metrics.cagr|pct }}</div></div>
    <div class="card"><div class="label">Sharpe</div><div class="value">{{ metrics.sharpe|num }}</div></div>
    <div class="card"><div class="label">Max drawdown</div><div class="value">{{ metrics.max_drawdown|pct }}</div></div>
    <div class="card"><div class="label">Sortino</div><div class="value">{{ metrics.sortino|num }}</div></div>
    <div class="card"><div class="label">Volatility</div><div class="value">{{ metrics.volatility|pct }}</div></div>
    <div class="card"><div class="label">Turnover</div><div class="value">{{ metrics.turnover|num }}</div></div>
    <div class="card"><div class="label">Latest equity</div><div class="value">{{ latest_equity.equity_base|money }}</div></div>
  </div></section>

  <section><h2>Risk</h2><div class="grid">
    <div class="card"><div class="label">Volatility</div><div class="value">{{ risk.volatility|pct }}</div></div>
    <div class="card"><div class="label">Value at Risk 95%</div><div class="value">{{ risk.var_95|pct }}</div></div>
    <div class="card"><div class="label">Conditional VaR 95%</div><div class="value">{{ risk.cvar_95|pct }}</div></div>
    <div class="card"><div class="label">Calmar</div><div class="value">{{ risk.calmar|num }}</div></div>
    <div class="card"><div class="label">Beta</div><div class="value">{{ risk.beta|num }}</div></div>
    <div class="card"><div class="label">Alpha</div><div class="value">{{ risk.alpha|pct }}</div></div>
    <div class="card"><div class="label">Information ratio</div><div class="value">{{ risk.information_ratio|num }}</div></div>
    <div class="card"><div class="label">Sortino</div><div class="value">{{ risk.sortino|num }}</div></div>
  </div></section>

  {% if equity_points %}<section><h2>Portfolio path</h2><div class="two">
    <div><div class="label">Equity curve</div><svg class="chart" viewBox="0 0 760 190" role="img" aria-label="Equity curve" xmlns="http://www.w3.org/2000/svg"><line x1="20" y1="170" x2="740" y2="170" stroke="#d8dee9"/><polyline points="{{ equity_points }}" fill="none" stroke="#3157d5" stroke-width="3" vector-effect="non-scaling-stroke"/></svg></div>
    <div><div class="label">Drawdown</div><svg class="chart" viewBox="0 0 760 190" role="img" aria-label="Drawdown curve" xmlns="http://www.w3.org/2000/svg"><line x1="20" y1="20" x2="740" y2="20" stroke="#d8dee9"/><polyline points="{{ drawdown_points }}" fill="none" stroke="#b42318" stroke-width="3" vector-effect="non-scaling-stroke"/></svg></div>
  </div><p class="muted">{{ equity_curve|length }} daily observations from {{ equity_curve[0].date }} through {{ equity_curve[-1].date }}.</p></section>{% endif %}

  {% if drag_rows %}<section><h2>Return drag</h2>
    <svg class="chart" viewBox="0 0 760 {{ 34 + drag_rows|length * 42 }}" role="img" aria-label="Return drag chart" xmlns="http://www.w3.org/2000/svg">
      {% for item in drag_rows %}<text x="16" y="{{ 31 + loop.index0 * 42 }}" font-size="12" fill="#667085">{{ item.label }}</text>
      <rect x="150" y="{{ 17 + loop.index0 * 42 }}" width="{{ item.width }}" height="18" rx="3" fill="#b42318" opacity=".82"/>
      <text x="{{ 160 + item.width }}" y="{{ 31 + loop.index0 * 42 }}" font-size="12" fill="#172033">{{ item.value|pct }}</text>{% endfor %}
    </svg>
  </section>{% endif %}

  <section><h2>Costs and taxes</h2><table><thead><tr><th>Item</th><th>Base amount</th></tr></thead><tbody>
    <tr><td>Fees</td><td>{{ costs.fees_total_base|money }}</td></tr>
    <tr><td>Taxes</td><td>{{ costs.taxes_total_base|money }}</td></tr>
    <tr><td>Borrow fees</td><td>{{ costs.borrow_fees_base|money }}</td></tr>
    <tr><td>Margin interest</td><td>{{ costs.margin_interest_base|money }}</td></tr>
    <tr><td>Tax events</td><td>{{ taxes.event_count }}</td></tr>
  </tbody></table></section>

  {% if explanation %}<section><h2>Explanation</h2><table><tbody>
    <tr><td>Dominant drag</td><td>{{ explanation.dominant_drag or "None" }}</td></tr>
    <tr><td>Trade count</td><td>{{ explanation.trade_count }}</td></tr>
    <tr><td>Tax regime</td><td>{{ explanation.tax_regime }}</td></tr>
    <tr><td>Best rolling month</td><td>{% if explanation.best_period %}{{ explanation.best_period.start_date }} – {{ explanation.best_period.end_date }} ({{ explanation.best_period.return_value|pct }}){% else %}—{% endif %}</td></tr>
    <tr><td>Worst rolling month</td><td>{% if explanation.worst_period %}{{ explanation.worst_period.start_date }} – {{ explanation.worst_period.end_date }} ({{ explanation.worst_period.return_value|pct }}){% else %}—{% endif %}</td></tr>
    <tr><td>Largest position</td><td>{% if explanation.largest_position %}{{ explanation.largest_position.symbol }} · {{ explanation.largest_position.market_value_base|money }}{% else %}—{% endif %}</td></tr>
    <tr><td>Largest trade</td><td>{% if explanation.largest_trade %}{{ explanation.largest_trade.symbol }} · {{ explanation.largest_trade.notional_base|money }}{% else %}—{% endif %}</td></tr>
    <tr><td>Largest tax event</td><td>{% if explanation.largest_tax_event %}{{ explanation.largest_tax_event.symbol }} · {{ explanation.largest_tax_event.tax_due_base|money }}{% else %}—{% endif %}</td></tr>
  </tbody></table></section>{% endif %}

  <section><h2>Trades ({{ trades|length }})</h2>
    {% if trades %}<table><thead><tr><th>Date</th><th>Symbol</th><th>Side</th><th>Quantity</th><th>Notional</th><th>Costs</th></tr></thead><tbody>
    {% for trade in trades %}<tr><td>{{ trade.date }}</td><td>{{ trade.symbol }}</td><td>{{ trade.side or "—" }}</td><td>{{ trade.qty|num }}</td><td>{{ trade.notional|money }}</td><td>{{ (trade.commission + trade.slippage)|money }}</td></tr>{% endfor %}
    </tbody></table>{% else %}<p class="muted">No fills were recorded.</p>{% endif %}
  </section>

  <section><h2>Tax events ({{ tax_events|length }})</h2>
    {% if tax_events %}<table><thead><tr><th>Date</th><th>Symbol</th><th>Bucket</th><th>Realized P&amp;L</th><th>Tax due</th></tr></thead><tbody>
    {% for event in tax_events %}<tr><td>{{ event.date }}</td><td>{{ event.symbol }}</td><td>{{ event.bucket }}</td><td>{{ event.realized_pnl_base|money }}</td><td>{{ event.tax_due_base|money }}</td></tr>{% endfor %}
    </tbody></table>{% else %}<p class="muted">No taxable realization events were recorded.</p>{% endif %}
  </section>

  <section><h2>Data snapshot</h2><p><strong>{{ data_snapshot.id }}</strong></p>
    {% if data_snapshot.coverage %}<table><thead><tr><th>Symbol</th><th>Asset class</th><th>Exchange</th><th>Currency</th><th>First bar</th><th>Last bar</th><th>Rows</th></tr></thead><tbody>
    {% for item in data_snapshot.coverage %}<tr><td>{{ item.symbol }}</td><td>{{ item.asset_class or "—" }}</td><td>{{ item.exchange or "—" }}</td><td>{{ item.currency or "—" }}</td><td>{{ item.first_date or "—" }}</td><td>{{ item.last_date or "—" }}</td><td>{{ item.rows }}</td></tr>{% endfor %}
    </tbody></table>{% else %}<p class="muted">Coverage metadata was unavailable.</p>{% endif %}
  </section>

  <section><h2>Run configuration</h2><table><tbody>
    <tr><td>Strategy</td><td>{{ run.config_snapshot.strategy or "BUY_AND_HOLD" }}</td></tr>
    <tr><td>Base currency</td><td>{{ run.config_snapshot.base_currency or "USD" }}</td></tr>
    <tr><td>Start date</td><td>{{ run.config_snapshot.backtest.start_date }}</td></tr>
    <tr><td>End date</td><td>{{ run.config_snapshot.backtest.end_date }}</td></tr>
    <tr><td>Seed</td><td>{{ run.seed }}</td></tr>
  </tbody></table></section>
  <footer>Generated by SimuTrader. This self-contained report has no external fonts, stylesheets, scripts, or images.</footer>
</main></body></html>"""


def _report_percent(value) -> str:
    try:
        return f"{float(value) * 100:.2f}%"
    except (TypeError, ValueError, UndefinedError):
        return "—"


def _report_number(value) -> str:
    try:
        return f"{float(value):,.2f}"
    except (TypeError, ValueError, UndefinedError):
        return "—"


_REPORT_ENV = Environment(
    loader=BaseLoader(),
    autoescape=select_autoescape(default=True),
)
_REPORT_ENV.filters.update(pct=_report_percent, num=_report_number, money=_report_number)
_REPORT_TEMPLATE = _REPORT_ENV.from_string(_REPORT_HTML_TEMPLATE)


def _parse_datetime(value: str | None):
    if value is None:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _to_backtest_out(run: BacktestRun) -> BacktestOut:
    # Explicitly map only safe/public run fields.
    return BacktestOut(
        run_id=run.run_id,
        strategy_id=run.strategy_id,
        name=run.name,
        status=run.status,
        error_code=run.error_code,
        error_message_public=run.error_message_public,
        error_retryable=run.error_retryable,
        error_id=run.error_id,
        created_at=run.created_at,
        started_at=run.started_at,
        finished_at=run.finished_at,
        config_snapshot=run.config_snapshot,
        data_snapshot_id=run.data_snapshot_id,
        seed=run.seed,
    )


def _get_actor_run(run_id: UUID, actor: ActorContext, db: Session) -> BacktestRun:
    run = db.query(BacktestRun).filter(BacktestRun.run_id == run_id).first()
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    if run.actor_key != actor.actor_key and not str(run.actor_key or "").startswith(
        GLOBAL_PRESET_ACTOR_PREFIX
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    return run


def _is_terminal_status(status_value: str) -> bool:
    return status_value in {"SUCCEEDED", "FAILED", "ENQUEUE_FAILED"}


def _strategy_type(config: dict | None) -> str:
    strategy = (config or {}).get("strategy") or "BUY_AND_HOLD"
    if isinstance(strategy, dict):
        return str(strategy.get("type") or "BUY_AND_HOLD").upper()
    return str(strategy).upper()


def _tax_regime(config: dict | None) -> str:
    return str(((config or {}).get("tax") or {}).get("regime") or "NONE").upper()


def _metric_value(metrics: RunMetric | None, field: str) -> float | None:
    value = getattr(metrics, field, None) if metrics is not None else None
    return None if value is None else float(value)


def _latest_equity(run_id: UUID, db: Session) -> RunDailyEquity | None:
    return (
        db.query(RunDailyEquity)
        .filter(RunDailyEquity.run_id == run_id)
        .order_by(RunDailyEquity.date.desc())
        .first()
    )


def _rolling_month_extremes(
    equity_rows: list[RunDailyEquity],
) -> tuple[dict | None, dict | None]:
    """Return best/worst 21-return windows (22 global-calendar observations)."""
    ordered = sorted(equity_rows, key=lambda row: row.date)
    periods: list[dict] = []
    for index in range(21, len(ordered)):
        start_row = ordered[index - 21]
        end_row = ordered[index]
        start_equity = float(start_row.equity_base or 0.0)
        if abs(start_equity) <= 1e-12:
            continue
        periods.append(
            {
                "start_date": start_row.date,
                "end_date": end_row.date,
                "return_value": float(end_row.equity_base) / start_equity - 1.0,
            }
        )
    if not periods:
        return None, None
    return (
        max(periods, key=lambda period: period["return_value"]),
        min(periods, key=lambda period: period["return_value"]),
    )


def _usd_inr_rates(start_date: date, end_date: date) -> dict[date, float]:
    try:
        con = get_duckdb_conn()
        try:
            rows = con.execute(
                """
                SELECT date, close
                FROM prices
                WHERE upper(symbol) = 'USDINR'
                  AND date <= ?
                ORDER BY date
                """,
                [end_date],
            ).fetchall()
        finally:
            con.close()
    except Exception:
        return {}
    rates: dict[date, float] = {}
    last_rate: float | None = None
    rate_at_start: float | None = None
    for rate_date, close in rows:
        if close is not None:
            last_rate = float(close)
        if rate_date <= start_date and last_rate is not None:
            rate_at_start = last_rate
        if rate_date >= start_date and last_rate is not None:
            rates[rate_date] = last_rate
    if rate_at_start is not None:
        rates.setdefault(start_date, rate_at_start)
    return rates


def _native_notional_to_base(
    notional: float,
    currency: str | None,
    base_currency: str,
    usd_inr: float | None,
) -> float | None:
    native = str(currency or "").upper()
    base = str(base_currency or "").upper()
    if not native:
        return None
    if native == base:
        return notional
    if usd_inr is None or usd_inr <= 0.0:
        return None
    if native == "INR" and base == "USD":
        return notional / usd_inr
    if native == "USD" and base == "INR":
        return notional * usd_inr
    return None


def _run_explanation(run: BacktestRun, db: Session) -> RunExplainOut:
    metrics = db.query(RunMetric).filter(RunMetric.run_id == run.run_id).first()
    if not metrics:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Metrics not found")

    gross_return = _metric_value(metrics, "gross_return")
    net_return = _metric_value(metrics, "net_return")
    total_drag = (
        net_return - gross_return
        if gross_return is not None and net_return is not None
        else None
    )
    drag_breakdown = {
        "fees": -abs(float(metrics.fee_drag or 0.0)),
        "taxes": -abs(float(metrics.tax_drag or 0.0)),
        "borrow": -abs(float(metrics.borrow_drag or 0.0)),
        "margin_interest": -abs(float(metrics.margin_interest_drag or 0.0)),
    }
    dominant_drag = max(drag_breakdown, key=lambda key: abs(drag_breakdown[key]))
    if abs(drag_breakdown[dominant_drag]) <= 1e-12:
        dominant_drag = None

    trade_count = (
        db.query(func.count(RunFill.fill_id))
        .filter(
            RunFill.run_id == run.run_id,
            func.coalesce(RunFill.meta["kind"].astext, "") != "FX_SWEEP",
        )
        .scalar()
        or 0
    )
    tax_regime = _tax_regime(run.config_snapshot)

    equity_rows = (
        db.query(RunDailyEquity)
        .filter(RunDailyEquity.run_id == run.run_id)
        .order_by(RunDailyEquity.date.asc())
        .all()
    )
    best_period, worst_period = _rolling_month_extremes(equity_rows)

    position_rows = db.query(RunPosition).filter(RunPosition.run_id == run.run_id).all()
    largest_position = None
    if position_rows:
        latest_position_date = max(row.date for row in position_rows)
        latest_positions = [row for row in position_rows if row.date == latest_position_date]
        position = max(latest_positions, key=lambda row: abs(float(row.market_value_base)))
        largest_position = {
            "date": position.date,
            "symbol": position.symbol,
            "qty": float(position.qty),
            "market_value_base": float(position.market_value_base),
        }

    fill_rows = db.query(RunFill).filter(RunFill.run_id == run.run_id).all()
    security_fills = [
        fill
        for fill in fill_rows
        if str((getattr(fill, "meta", None) or {}).get("kind") or "").upper()
        != "FX_SWEEP"
        and getattr(fill, "date", None) is not None
        and getattr(fill, "symbol", None)
        and getattr(fill, "qty", None) is not None
    ]
    largest_trade = None
    if security_fills:
        config = run.config_snapshot or {}
        base_currency = str(config.get("base_currency") or "USD").upper()
        instruments = ((config.get("universe") or {}).get("instruments") or [])
        symbol_currencies = {
            str(instrument.get("symbol") or "").upper(): currency_for_asset_class(
                str(instrument.get("asset_class") or "")
            )
            for instrument in instruments
        }
        fill_dates = [getattr(fill, "date") for fill in security_fills]
        needs_fx = any(
            symbol_currencies.get(str(getattr(fill, "symbol")).upper())
            not in {None, base_currency}
            for fill in security_fills
        )
        fx_rates = _usd_inr_rates(min(fill_dates), max(fill_dates)) if needs_fx else {}
        last_fx: float | None = None
        ordered_fx_rates = sorted(fx_rates.items())
        fx_index = 0
        ranked_fills: list[tuple[float, RunFill, str | None, float | None]] = []
        for fill in sorted(security_fills, key=lambda row: getattr(row, "date")):
            fill_date = getattr(fill, "date")
            while fx_index < len(ordered_fx_rates) and ordered_fx_rates[fx_index][0] <= fill_date:
                last_fx = ordered_fx_rates[fx_index][1]
                fx_index += 1
            currency = symbol_currencies.get(str(getattr(fill, "symbol")).upper())
            notional_native = abs(float(getattr(fill, "notional_native", 0.0) or 0.0))
            notional_base = _native_notional_to_base(
                notional_native, currency, base_currency, last_fx
            )
            rank_value = notional_base if notional_base is not None else notional_native
            ranked_fills.append((rank_value, fill, currency, notional_base))
        _, largest_fill, trade_currency, trade_notional_base = max(
            ranked_fills, key=lambda item: item[0]
        )
        order_side = None
        largest_order_id = getattr(largest_fill, "order_id", None)
        if largest_order_id is not None:
            side_row = (
                db.query(RunOrder.order_id, RunOrder.side)
                .filter(RunOrder.order_id == largest_order_id)
                .first()
            )
            order_side = side_row[1] if side_row else None
        largest_trade = {
            "date": getattr(largest_fill, "date"),
            "symbol": getattr(largest_fill, "symbol"),
            "side": order_side,
            "qty": float(getattr(largest_fill, "qty")),
            "notional_native": float(
                getattr(largest_fill, "notional_native", 0.0) or 0.0
            ),
            "currency": trade_currency,
            "notional_base": trade_notional_base,
        }

    tax_rows = db.query(RunTaxEvent).filter(RunTaxEvent.run_id == run.run_id).all()
    largest_tax_event = None
    if tax_rows:
        tax_event = max(tax_rows, key=lambda row: abs(float(row.tax_due_base)))
        largest_tax_event = {
            "date": tax_event.date,
            "symbol": tax_event.symbol,
            "realized_pnl_base": float(tax_event.realized_pnl_base),
            "tax_due_base": float(tax_event.tax_due_base),
            "bucket": tax_event.bucket,
        }

    def pct(value: float | None) -> str:
        return "unknown" if value is None else f"{value * 100:.2f}%"

    if dominant_drag:
        drag_label = dominant_drag.replace("_", " ")
        drag_verb = "was" if dominant_drag == "margin_interest" else "were"
        headline = (
            f"Net return {pct(net_return)}; "
            f"{drag_label} {drag_verb} the largest drag."
        )
        summary = (
            f"The run earned {pct(gross_return)} gross and {pct(net_return)} net. "
            f"{drag_label.capitalize()} {drag_verb} the largest drag."
        )
    else:
        headline = f"Net return {pct(net_return)} with minimal cost drag."
        summary = f"The run earned {pct(gross_return)} gross and {pct(net_return)} net."

    return RunExplainOut(
        gross_return=gross_return,
        net_return=net_return,
        total_drag=total_drag,
        drag_breakdown=drag_breakdown,
        dominant_drag=dominant_drag,
        trade_count=int(trade_count),
        turnover=_metric_value(metrics, "turnover"),
        tax_regime=tax_regime,
        headline=headline,
        summary=summary,
        best_period=best_period,
        worst_period=worst_period,
        largest_position=largest_position,
        largest_trade=largest_trade,
        largest_tax_event=largest_tax_event,
    )


def _csv_response(filename: str, headers: list[str], rows: list[list[object]]) -> StreamingResponse:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(headers)
    writer.writerows(rows)
    buffer.seek(0)
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _tax_summary(run_id: UUID, db: Session) -> dict:
    rows = db.query(RunTaxEvent).filter(RunTaxEvent.run_id == run_id).all()
    return {
        "event_count": len(rows),
        "total_realized_pnl_base": sum(float(row.realized_pnl_base or 0.0) for row in rows),
        "total_tax_due_base": sum(float(row.tax_due_base or 0.0) for row in rows),
    }


@router.get("/{run_id}", response_model=BacktestOut)
def get_run(
    run_id: UUID,
    actor: ActorContext = Depends(get_current_actor),
    db: Session = Depends(get_db),
) -> BacktestOut:
    run = _get_actor_run(run_id, actor, db)
    set_cached_run_summary(run)
    set_cached_run_status(run)
    return _to_backtest_out(run)


@router.get("/{run_id}/status", response_model=BacktestStatusOut)
def get_run_status(
    run_id: UUID,
    actor: ActorContext = Depends(get_current_actor),
    db: Session = Depends(get_db),
) -> BacktestStatusOut:
    cached = get_cached_run_status(actor.actor_key, str(run_id))
    if cached:
        return BacktestStatusOut(
            run_id=run_id,
            status=cached.status,
            started_at=_parse_datetime(cached.started_at),
            finished_at=_parse_datetime(cached.finished_at),
            error_code=cached.error_code,
            error_message_public=cached.error_message_public,
        )
    run = _get_actor_run(run_id, actor, db)
    set_cached_run_status(run)
    set_cached_run_summary(run)
    return BacktestStatusOut(
        run_id=run.run_id,
        status=run.status,
        started_at=run.started_at,
        finished_at=run.finished_at,
        error_code=run.error_code,
        error_message_public=run.error_message_public,
    )


@router.get("/{run_id}/equity", response_model=list[RunDailyEquityOut])
def get_run_equity(
    run_id: UUID,
    start_date: date | None = None,
    end_date: date | None = None,
    limit: int = Query(default=2000, ge=1, le=10000),
    actor: ActorContext = Depends(get_current_actor),
    db: Session = Depends(get_db),
) -> list[RunDailyEquityOut]:
    run = _get_actor_run(run_id, actor, db)
    if not _is_terminal_status(run.status):
        return []
    if start_date and end_date and end_date < start_date:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="end_date must be >= start_date",
        )
    rows = (
        db.query(RunDailyEquity)
        .filter(RunDailyEquity.run_id == run_id)
    )
    if start_date:
        rows = rows.filter(RunDailyEquity.date >= start_date)
    if end_date:
        rows = rows.filter(RunDailyEquity.date <= end_date)
    rows = (
        rows.order_by(RunDailyEquity.date.asc())
        .limit(limit)
        .all()
    )
    return rows


def _add_exposure(
    breakdowns: dict[str, RunExposureBreakdownOut],
    key: str,
    *,
    qty: float,
    market_value_base: float,
) -> None:
    breakdown = breakdowns.setdefault(
        key,
        RunExposureBreakdownOut(
            long_base=0.0,
            short_base=0.0,
            gross_base=0.0,
            net_base=0.0,
        ),
    )
    magnitude = abs(market_value_base)
    if qty > 0.0:
        breakdown.long_base += magnitude
    elif qty < 0.0:
        breakdown.short_base += magnitude
    breakdown.gross_base = breakdown.long_base + breakdown.short_base
    breakdown.net_base = breakdown.long_base - breakdown.short_base


@router.get("/{run_id}/exposure", response_model=list[RunExposurePointOut])
def get_run_exposure(
    run_id: UUID,
    start: date | None = None,
    end: date | None = None,
    limit: int = Query(default=2000, ge=1, le=10000),
    actor: ActorContext = Depends(get_current_actor),
    db: Session = Depends(get_db),
) -> list[RunExposurePointOut]:
    run = _get_actor_run(run_id, actor, db)
    if not _is_terminal_status(run.status):
        return []
    if start and end and end < start:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="end must be >= start",
        )

    equity_query = db.query(RunDailyEquity).filter(RunDailyEquity.run_id == run_id)
    if start:
        equity_query = equity_query.filter(RunDailyEquity.date >= start)
    if end:
        equity_query = equity_query.filter(RunDailyEquity.date <= end)
    equity_rows = equity_query.order_by(RunDailyEquity.date.asc()).limit(limit).all()
    if not equity_rows:
        return []

    exposure_dates = [row.date for row in equity_rows]
    position_rows = (
        db.query(RunPosition)
        .filter(
            RunPosition.run_id == run_id,
            RunPosition.date.in_(exposure_dates),
        )
        .all()
    )
    symbols = sorted({str(row.symbol).upper() for row in position_rows})
    asset_rows = (
        db.query(Asset).filter(func.upper(Asset.symbol).in_(symbols)).all()
        if symbols
        else []
    )
    assets_by_symbol = {str(row.symbol).upper(): row for row in asset_rows}
    positions_by_date: dict[date, list[RunPosition]] = {}
    for position in position_rows:
        positions_by_date.setdefault(position.date, []).append(position)

    results: list[RunExposurePointOut] = []
    for equity in equity_rows:
        by_currency: dict[str, RunExposureBreakdownOut] = {}
        by_asset_class: dict[str, RunExposureBreakdownOut] = {}
        by_country: dict[str, RunExposureBreakdownOut] = {}
        total = RunExposureBreakdownOut(
            long_base=0.0,
            short_base=0.0,
            gross_base=0.0,
            net_base=0.0,
        )
        for position in positions_by_date.get(equity.date, []):
            qty = float(position.qty or 0.0)
            market_value_base = float(position.market_value_base or 0.0)
            magnitude = abs(market_value_base)
            if qty > 0.0:
                total.long_base += magnitude
            elif qty < 0.0:
                total.short_base += magnitude

            asset = assets_by_symbol.get(str(position.symbol).upper())
            asset_class = str(getattr(asset, "asset_class", None) or "UNKNOWN").upper()
            currency = str(getattr(asset, "currency", None) or "UNKNOWN").upper()
            country = country_for_asset_class(asset_class)
            for breakdowns, key in (
                (by_currency, currency),
                (by_asset_class, asset_class),
                (by_country, country),
            ):
                _add_exposure(
                    breakdowns,
                    key,
                    qty=qty,
                    market_value_base=market_value_base,
                )

        total.gross_base = total.long_base + total.short_base
        total.net_base = total.long_base - total.short_base
        equity_base = float(equity.equity_base or 0.0)
        results.append(
            RunExposurePointOut(
                date=equity.date,
                long_base=total.long_base,
                short_base=total.short_base,
                gross_base=total.gross_base,
                net_base=total.net_base,
                leverage=(
                    total.gross_base / equity_base if abs(equity_base) > 1e-12 else None
                ),
                equity_native_by_currency={
                    str(currency): float(value)
                    for currency, value in (equity.equity_by_currency or {}).items()
                },
                exposure_base_by_currency=by_currency,
                by_asset_class=by_asset_class,
                by_country=by_country,
            )
        )
    return results


@router.get("/{run_id}/metrics", response_model=RunMetricOut)
def get_run_metrics(
    run_id: UUID,
    actor: ActorContext = Depends(get_current_actor),
    db: Session = Depends(get_db),
) -> RunMetricOut:
    run = _get_actor_run(run_id, actor, db)
    metrics = db.query(RunMetric).filter(RunMetric.run_id == run_id).first()
    if not metrics:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Metrics not found")

    out = RunMetricOut.model_validate(metrics)
    out.explanation = _run_explanation(run, db).summary
    return out


@router.get("/{run_id}/explain", response_model=RunExplainOut)
def explain_run(
    run_id: UUID,
    actor: ActorContext = Depends(get_current_actor),
    db: Session = Depends(get_db),
) -> RunExplainOut:
    run = _get_actor_run(run_id, actor, db)
    if not _is_terminal_status(run.status):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Run is not complete")
    return _run_explanation(run, db)


def _dispatch_derived_run(
    *,
    parent: BacktestRun,
    config: dict,
    actor: ActorContext,
    name: str | None,
    response: Response,
    idempotency_key: str | None,
    reuse_succeeded_run: bool,
    db: Session,
) -> BacktestOut:
    # Lazy import avoids coupling the two route modules during router initialization.
    from app.api.routes.backtests import _dispatch_run

    return _dispatch_run(
        db,
        config,
        actor,
        name,
        response=response,
        idempotency_key=idempotency_key,
        reuse_succeeded_run=reuse_succeeded_run,
        data_snapshot_id=parent.data_snapshot_id,
        seed=parent.seed,
        strategy_id=parent.strategy_id,
    )


@router.post("/{run_id}/clone", response_model=BacktestOut, status_code=status.HTTP_201_CREATED)
def clone_run(
    run_id: UUID,
    response: Response,
    payload: RunCloneRequest | None = None,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    reuse_succeeded_run: bool = Header(default=False, alias="X-Reuse-Succeeded-Run"),
    actor: ActorContext = Depends(get_current_actor),
    db: Session = Depends(get_db),
) -> BacktestOut:
    parent = _get_actor_run(run_id, actor, db)
    try:
        config = build_clone_config(parent.config_snapshot or {}, parent.run_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    name = (payload.name if payload else None) or f"{parent.name or 'Run'} (Clone)"
    return _dispatch_derived_run(
        parent=parent,
        config=config,
        actor=actor,
        name=name,
        response=response,
        idempotency_key=idempotency_key,
        reuse_succeeded_run=reuse_succeeded_run,
        db=db,
    )


@router.post("/{run_id}/scenario", response_model=BacktestOut, status_code=status.HTTP_201_CREATED)
def create_run_scenario(
    run_id: UUID,
    payload: RunScenarioRequest,
    response: Response,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    reuse_succeeded_run: bool = Header(default=False, alias="X-Reuse-Succeeded-Run"),
    actor: ActorContext = Depends(get_current_actor),
    db: Session = Depends(get_db),
) -> BacktestOut:
    parent = _get_actor_run(run_id, actor, db)
    try:
        config = build_scenario_config(
            parent.config_snapshot or {}, parent.run_id, payload.patch
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    name = payload.name or f"{parent.name or 'Run'} (Scenario)"
    return _dispatch_derived_run(
        parent=parent,
        config=config,
        actor=actor,
        name=name,
        response=response,
        idempotency_key=idempotency_key,
        reuse_succeeded_run=reuse_succeeded_run,
        db=db,
    )


@router.get("/{run_id}/positions", response_model=list[RunPositionOut])
def get_run_positions(
    run_id: UUID,
    date_value: date | None = Query(default=None, alias="date"),
    limit: int = Query(default=50, ge=1, le=200),
    actor: ActorContext = Depends(get_current_actor),
    db: Session = Depends(get_db),
) -> list[RunPositionOut]:
    run = _get_actor_run(run_id, actor, db)
    if not _is_terminal_status(run.status):
        return []
    if not isinstance(limit, int):
        limit = int(getattr(limit, "default", 50))

    target_date = date_value
    if hasattr(target_date, "default"):
        target_date = target_date.default
    if target_date is None:
        target_date = (
            db.query(func.max(RunPosition.date))
            .filter(RunPosition.run_id == run_id)
            .scalar()
        )
        if target_date is None:
            return []

    rows = (
        db.query(RunPosition)
        .filter(RunPosition.run_id == run_id, RunPosition.date == target_date)
        .order_by(RunPosition.market_value_base.desc(), RunPosition.symbol.asc())
        .limit(limit)
        .all()
    )
    if not rows:
        return []

    equity_row = (
        db.query(RunDailyEquity.equity_base)
        .filter(RunDailyEquity.run_id == run_id, RunDailyEquity.date == target_date)
        .first()
    )
    equity_base = equity_row[0] if equity_row else None

    results: list[RunPositionOut] = []
    for row in rows:
        weight = None
        if equity_base and abs(equity_base) > 1e-12:
            weight = row.market_value_base / equity_base
        results.append(
            RunPositionOut(
                date=row.date,
                symbol=row.symbol,
                qty=row.qty,
                avg_cost_native=row.avg_cost_native,
                market_value_base=row.market_value_base,
                unrealized_pnl_base=row.unrealized_pnl_base,
                weight=weight,
            )
        )
    return results


@router.get("/{run_id}/fills", response_model=list[RunFillOut])
def get_run_fills(
    run_id: UUID,
    start: date | None = None,
    end: date | None = None,
    limit: int = Query(default=200, ge=1, le=1000),
    offset: int = Query(default=0, ge=0, le=5000),
    actor: ActorContext = Depends(get_current_actor),
    db: Session = Depends(get_db),
) -> list[RunFillOut]:
    run = _get_actor_run(run_id, actor, db)
    if not _is_terminal_status(run.status):
        return []
    if not isinstance(limit, int):
        limit = int(getattr(limit, "default", 200))
    if not isinstance(offset, int):
        offset = int(getattr(offset, "default", 0))
    if start and end and end < start:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="end must be >= start",
        )

    rows = db.query(RunFill).filter(RunFill.run_id == run_id)
    if start:
        rows = rows.filter(RunFill.date >= start)
    if end:
        rows = rows.filter(RunFill.date <= end)
    fills = rows.order_by(RunFill.date.asc()).offset(offset).limit(limit).all()

    if not fills:
        return []

    order_ids = {fill.order_id for fill in fills if fill.order_id is not None}
    side_lookup: dict[UUID, str] = {}
    if order_ids:
        side_rows = (
            db.query(RunOrder.order_id, RunOrder.side)
            .filter(RunOrder.order_id.in_(order_ids))
            .all()
        )
        side_lookup = {order_id: side for order_id, side in side_rows}

    return [
        RunFillOut(
            date=fill.date,
            symbol=fill.symbol,
            side=side_lookup.get(fill.order_id) if fill.order_id else None,
            qty=fill.qty,
            price=fill.price_native,
            notional=fill.notional_native,
            commission=fill.commission_native,
            slippage=fill.slippage_native,
        )
        for fill in fills
    ]


@router.get("/{run_id}/costs_summary", response_model=RunCostsSummaryOut)
def get_run_costs_summary(
    run_id: UUID,
    start: date | None = None,
    end: date | None = None,
    actor: ActorContext = Depends(get_current_actor),
    db: Session = Depends(get_db),
) -> RunCostsSummaryOut:
    run = _get_actor_run(run_id, actor, db)
    if not _is_terminal_status(run.status):
        return RunCostsSummaryOut(
            commissions_native={},
            slippage_native={},
            fees_total_base=0.0,
            taxes_total_base=0.0,
            borrow_fees_base=0.0,
            margin_interest_base=0.0,
        )
    if start and end and end < start:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="end must be >= start",
        )

    fill_rows = db.query(
        RunFill.symbol,
        func.coalesce(func.sum(RunFill.commission_native), 0.0),
        func.coalesce(func.sum(RunFill.slippage_native), 0.0),
    ).filter(RunFill.run_id == run_id)
    if start:
        fill_rows = fill_rows.filter(RunFill.date >= start)
    if end:
        fill_rows = fill_rows.filter(RunFill.date <= end)
    fill_totals_by_symbol = fill_rows.group_by(RunFill.symbol).all()

    instruments = ((run.config_snapshot or {}).get("universe") or {}).get("instruments") or []
    symbol_currencies = {
        str(instrument.get("symbol") or "").upper(): currency_for_asset_class(
            str(instrument.get("asset_class") or "")
        )
        for instrument in instruments
    }
    commissions_native: dict[str, float] = {}
    slippage_native: dict[str, float] = {}
    base_currency = str((run.config_snapshot or {}).get("base_currency") or "USD").upper()
    for symbol, commissions, slippage in fill_totals_by_symbol:
        currency = (
            base_currency
            if str(symbol or "").upper() == "USDINR"
            else symbol_currencies.get(str(symbol).upper())
        )
        if currency is None:
            continue
        commissions_native[currency] = commissions_native.get(currency, 0.0) + float(
            commissions or 0.0
        )
        slippage_native[currency] = slippage_native.get(currency, 0.0) + float(
            slippage or 0.0
        )

    equity_rows = db.query(RunDailyEquity).filter(RunDailyEquity.run_id == run_id)
    if start:
        equity_rows = equity_rows.filter(RunDailyEquity.date >= start)
    if end:
        equity_rows = equity_rows.filter(RunDailyEquity.date <= end)
    latest_equity = equity_rows.order_by(RunDailyEquity.date.desc()).first()
    return RunCostsSummaryOut(
        commissions_native=commissions_native,
        slippage_native=slippage_native,
        fees_total_base=float(latest_equity.fees_cum_base if latest_equity else 0.0),
        taxes_total_base=float(latest_equity.taxes_cum_base if latest_equity else 0.0),
        borrow_fees_base=float(latest_equity.borrow_fees_cum_base if latest_equity else 0.0),
        margin_interest_base=float(
            latest_equity.margin_interest_cum_base if latest_equity else 0.0
        ),
    )


@router.get("/{run_id}/export/equity.csv")
def export_run_equity_csv(
    run_id: UUID,
    actor: ActorContext = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    _get_actor_run(run_id, actor, db)
    rows = (
        db.query(RunDailyEquity)
        .filter(RunDailyEquity.run_id == run_id)
        .order_by(RunDailyEquity.date.asc())
        .all()
    )
    return _csv_response(
        "equity.csv",
        [
            "date",
            "equity_base",
            "cash_base",
            "gross_exposure_base",
            "net_exposure_base",
            "drawdown",
            "fees_cum_base",
            "taxes_cum_base",
            "borrow_fees_cum_base",
            "margin_interest_cum_base",
        ],
        [
            [
                row.date,
                row.equity_base,
                row.cash_base,
                row.gross_exposure_base,
                row.net_exposure_base,
                row.drawdown,
                row.fees_cum_base,
                row.taxes_cum_base,
                row.borrow_fees_cum_base,
                row.margin_interest_cum_base,
            ]
            for row in rows
        ],
    )


@router.get("/{run_id}/export/fills.csv")
def export_run_fills_csv(
    run_id: UUID,
    actor: ActorContext = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    _get_actor_run(run_id, actor, db)
    fills = (
        db.query(RunFill)
        .filter(RunFill.run_id == run_id)
        .order_by(RunFill.date.asc())
        .all()
    )
    order_ids = {fill.order_id for fill in fills if fill.order_id is not None}
    side_lookup: dict[UUID, str] = {}
    if order_ids:
        side_rows = (
            db.query(RunOrder.order_id, RunOrder.side)
            .filter(RunOrder.order_id.in_(order_ids))
            .all()
        )
        side_lookup = {order_id: side for order_id, side in side_rows}
    return _csv_response(
        "fills.csv",
        ["date", "symbol", "side", "qty", "price", "notional", "commission", "slippage"],
        [
            [
                row.date,
                row.symbol,
                side_lookup.get(row.order_id) if row.order_id else None,
                row.qty,
                row.price_native,
                row.notional_native,
                row.commission_native,
                row.slippage_native,
            ]
            for row in fills
        ],
    )


@router.get("/{run_id}/export/taxes.csv")
def export_run_taxes_csv(
    run_id: UUID,
    actor: ActorContext = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    _get_actor_run(run_id, actor, db)
    rows = (
        db.query(RunTaxEvent)
        .filter(RunTaxEvent.run_id == run_id)
        .order_by(RunTaxEvent.date.asc(), RunTaxEvent.tax_event_id.asc())
        .all()
    )
    return _csv_response(
        "taxes.csv",
        [
            "date",
            "symbol",
            "quantity",
            "realized_pnl_base",
            "holding_period_days",
            "bucket",
            "tax_rate",
            "tax_due_base",
        ],
        [
            [
                row.date,
                row.symbol,
                row.quantity,
                row.realized_pnl_base,
                row.holding_period_days,
                row.bucket,
                row.tax_rate,
                row.tax_due_base,
            ]
            for row in rows
        ],
    )


@router.get("/{run_id}/report.json")
def get_run_report_json(
    run_id: UUID,
    actor: ActorContext = Depends(get_current_actor),
    db: Session = Depends(get_db),
) -> dict:
    run = _get_actor_run(run_id, actor, db)
    metrics = db.query(RunMetric).filter(RunMetric.run_id == run_id).first()
    latest_equity = _latest_equity(run_id, db)
    equity_rows = (
        db.query(RunDailyEquity)
        .filter(RunDailyEquity.run_id == run_id)
        .order_by(RunDailyEquity.date.asc())
        .all()
    )
    fill_rows = (
        db.query(RunFill)
        .filter(RunFill.run_id == run_id)
        .order_by(RunFill.date.asc(), RunFill.fill_id.asc())
        .all()
    )
    order_ids = [fill.order_id for fill in fill_rows if fill.order_id]
    side_lookup: dict[UUID, str] = {}
    if order_ids:
        side_lookup = dict(
            db.query(RunOrder.order_id, RunOrder.side)
            .filter(RunOrder.order_id.in_(order_ids))
            .all()
        )
    trades = [
        RunFillOut(
            date=fill.date,
            symbol=fill.symbol,
            side=side_lookup.get(fill.order_id) if fill.order_id else None,
            qty=float(fill.qty),
            price=float(fill.price_native),
            notional=float(fill.notional_native),
            commission=float(fill.commission_native),
            slippage=float(fill.slippage_native),
        ).model_dump(mode="json")
        for fill in fill_rows
    ]
    tax_rows = (
        db.query(RunTaxEvent)
        .filter(RunTaxEvent.run_id == run_id)
        .order_by(RunTaxEvent.date.asc(), RunTaxEvent.tax_event_id.asc())
        .all()
    )
    tax_events = [
        RunTaxEventOut.model_validate(row).model_dump(mode="json") for row in tax_rows
    ]
    metric_payload = (
        RunMetricOut.model_validate(metrics).model_dump(mode="json") if metrics else None
    )
    metric_meta = (metric_payload or {}).get("meta") or {}
    risk = {
        key: (metric_payload or {}).get(key, metric_meta.get(key))
        for key in ("volatility", "sharpe", "sortino", "max_drawdown")
    }
    risk.update(
        {
            key: metric_meta.get(key)
            for key in (
                "calmar",
                "var_95",
                "cvar_95",
                "beta",
                "alpha",
                "information_ratio",
            )
        }
    )
    config = run.config_snapshot or {}
    instruments = ((config.get("universe") or {}).get("instruments") or [])
    backtest = config.get("backtest") or {}
    coverage: list[dict] = []
    try:
        symbols = [str(item.get("symbol") or "").upper() for item in instruments]
        if symbols and backtest.get("start_date") and backtest.get("end_date"):
            coverage, _, _ = _query_symbol_coverage(
                symbols,
                date.fromisoformat(str(backtest["start_date"])),
                date.fromisoformat(str(backtest["end_date"])),
            )
    except Exception:
        coverage = []
    return {
        "run": _to_backtest_out(run).model_dump(mode="json"),
        "metrics": metric_payload,
        "risk": risk,
        "explanation": _run_explanation(run, db).model_dump(mode="json") if metrics else None,
        "costs": get_run_costs_summary(run_id=run_id, actor=actor, db=db).model_dump(mode="json"),
        "taxes": _tax_summary(run_id, db),
        "tax_events": tax_events,
        "trades": trades,
        "equity_curve": [
            RunDailyEquityOut.model_validate(row).model_dump(mode="json")
            for row in equity_rows
        ],
        "data_snapshot": {
            "id": run.data_snapshot_id,
            "coverage": coverage,
        },
        "latest_equity": RunDailyEquityOut.model_validate(latest_equity).model_dump(mode="json")
        if latest_equity
        else None,
    }


@router.get("/{run_id}/report.html", response_class=HTMLResponse)
def get_run_report_html(
    run_id: UUID,
    actor: ActorContext = Depends(get_current_actor),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    """Render the canonical JSON report as a self-contained, printable HTML file."""
    report = get_run_report_json(run_id=run_id, actor=actor, db=db)
    explanation = report.get("explanation") or {}
    drag_breakdown = explanation.get("drag_breakdown") or {}
    nonzero_drags = [
        (str(name).replace("_", " ").title(), float(value or 0.0))
        for name, value in drag_breakdown.items()
        if abs(float(value or 0.0)) > 1e-12
    ]
    max_drag = max((abs(value) for _, value in nonzero_drags), default=0.0)
    drag_rows = [
        {
            "label": label,
            "value": value,
            "width": round(480.0 * abs(value) / max_drag, 2) if max_drag else 0.0,
        }
        for label, value in nonzero_drags
    ]
    equity_curve = report.get("equity_curve") or []

    def chart_points(field: str) -> str:
        values = [float(row.get(field) or 0.0) for row in equity_curve]
        if not values:
            return ""
        low, high = min(values), max(values)
        spread = high - low or 1.0
        denominator = max(len(values) - 1, 1)
        return " ".join(
            f"{20 + 720 * index / denominator:.2f},{20 + 150 * (high - value) / spread:.2f}"
            for index, value in enumerate(values)
        )

    html = _REPORT_TEMPLATE.render(
        run=report.get("run") or {},
        metrics=report.get("metrics") or {},
        explanation=explanation,
        costs=report.get("costs") or {},
        taxes=report.get("taxes") or {},
        latest_equity=report.get("latest_equity") or {},
        drag_rows=drag_rows,
        risk=report.get("risk") or {},
        equity_curve=equity_curve,
        equity_points=chart_points("equity_base"),
        drawdown_points=chart_points("drawdown"),
        trades=report.get("trades") or [],
        tax_events=report.get("tax_events") or [],
        data_snapshot=report.get("data_snapshot") or {},
    )
    return HTMLResponse(
        content=html,
        headers={
            "Content-Disposition": f'inline; filename="run-{run_id}-report.html"',
            "Cache-Control": "private, no-store",
        },
    )


@router.get("/{run_id}/top-holdings", response_model=list[RunPositionOut])
def get_run_top_holdings(
    run_id: UUID,
    limit: int = Query(default=10, ge=1, le=50),
    actor: ActorContext = Depends(get_current_actor),
    db: Session = Depends(get_db),
) -> list[RunPositionOut]:
    cached = get_cached_top_holdings(actor.actor_key, str(run_id), limit)
    if cached is not None:
        return [RunPositionOut.model_validate(item) for item in cached]
    rows = get_run_positions(
        run_id=run_id,
        date_value=None,
        limit=limit,
        actor=actor,
        db=db,
    )
    payload = [row.model_dump(mode="json") for row in rows]
    set_cached_top_holdings(actor.actor_key, str(run_id), limit, payload)
    return rows
