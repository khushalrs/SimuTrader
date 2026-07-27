# Custom Strategy Builder — Form-Based v1 Plan

> Status: planning / not started. Base for a form-based custom strategy builder,
> designed to expand into a block/graph editor later without backend rework.

## Context & key facts (from the current codebase)

- **The engine already has the seam we need.** Every strategy is just one callback
  passed to `run_engine`:
  ```python
  target_allocations_fn(ctx: DayContext) -> {symbol: weight} | None
  ```
  See `app/backtest/momentum.py` and `app/backtest/engine.py`. The engine handles
  everything downstream: orders, fills, slippage, commissions, taxes, FX, financing,
  leverage. A "custom strategy" only needs to *author this callback*.

- **`DayContext`** (per bar) exposes: `date`, `flags`, `prices`, `market_open`,
  `state`, `equity_base`, `cash_base_total`, `position_value_base`, `fx_rate`
  (`app/backtest/engine.py:41`).

- **Dispatch is currently a hardcoded `if/elif`** on strategy type in
  `app/backtest/executor.py:113` over 5 presets: `BUY_AND_HOLD`, `DCA`,
  `FIXED_WEIGHT_REBALANCE`, `MOMENTUM`, `MEAN_REVERSION`.

- **Strategies persist** in the `strategies` table with a JSONB `config`
  (`app/models/strategies.py`). CRUD in `app/api/routes/strategies.py`.

- **Frontend builder** is a wizard: `apps/web/components/builder/steps/`
  (`UniverseStep`, `StrategyStep`, `RealismStep`, `ReviewStep`), entry at
  `apps/web/app/build_page/`. Today it only *tunes parameters* of a fixed preset.

## Mental model: a strategy is a 6-stage decision pipeline

| Stage | Question | Example |
|---|---|---|
| 1. Universe | Which symbols do I consider? | static list |
| 2. Signal/features | What do I compute from history ≤ today? | 90-day momentum, RSI(14) |
| 3. Rules/scoring | Buy/sell/hold or score per symbol | rank by momentum; RSI < 30 |
| 4. Sizing | Turn decisions into target weights | equal-weight top 5 |
| 5. Schedule | When do I recompute? | monthly |
| 6. Constraints | What limits override? | max 30% per name, long-only |

A custom strategy = a specific choice at each slot. The form lets users compose the
slots (vs. today's "tune one fixed pipeline").

---

## Shared foundation — the v1 form spec (freeze this FIRST)

The spec is the contract between frontend and backend. Stored in `strategies.config`
with `strategy_type: "CUSTOM"`. v1 is deliberately **one signal** (blocks later turn
`signal` into a list/tree — the only structural change).

```jsonc
{
  "version": 1,
  "strategy_type": "CUSTOM",
  "universe": { "instruments": [...] },        // reuse existing universe shape
  "signal": {
    "indicator": "MOMENTUM",                    // one of a fixed catalog
    "params": { "lookback_days": 90, "skip_days": 1 }
  },
  "selection": {
    "mode": "RANK",                             // RANK | THRESHOLD
    "direction": "TOP", "count": 5,             // RANK fields
    "operator": "LT", "value": 30               // THRESHOLD fields (e.g. RSI<30)
  },
  "sizing": { "method": "EQUAL" },              // EQUAL | SIGNAL_PROPORTIONAL
  "schedule": { "rebalance_frequency": "MONTHLY" },
  "constraints": { "max_weight": 0.30, "long_only": true }
}
```

---

## Backend plan

### Phase B0 — Registry & interface refactor (unblocks everything)
- Replace the `if/elif` dispatch in `app/backtest/executor.py:113` with a
  `STRATEGY_REGISTRY` keyed by strategy type; register the 5 existing runners unchanged.
- Document the strategy contract (`run_*(db, run, config) -> int`, already de facto true)
  so `CUSTOM` is just another registry entry.
- Add `"CUSTOM"` as a recognized type in `_resolve_strategy_type`.
- Pure refactor — no behavior change. Confirm existing runs still pass.

### Phase B1 — Indicator library
- New pure module `app/backtest/indicators.py`. Each indicator:
  `compute(history: list[float], params) -> float | None`, point-in-time (only sees
  history ≤ today), returns `None` during warmup, declares `warmup_bars`.
- v1 catalog (small): `MOMENTUM` (return over lookback with skip), `SMA_RATIO`
  (price / SMA(n)), `RSI`, `VOLATILITY` (stdev of returns), `PRICE` (raw).
- Unit-test each indicator standalone. This is the reusable core the block editor reuses.

### Phase B2 — Spec schema & validation
- Pydantic models in `app/schemas/strategies.py` (`CustomStrategySpec`, `SignalSpec`,
  `SelectionSpec`, ...).
- Extend `app/services/config_validation.py`: unknown indicator, param ranges,
  `RANK.count <= universe size`, threshold requires numeric `value`, derive required
  warmup and warn if it exceeds the backtest window, `long_only` consistency.
- Return structured errors matching existing preflight/error style.

### Phase B3 — Interpreter runner
- New `app/backtest/custom.py` -> `run_custom(db, run, config)` building a
  `target_allocations_fn` closure (mirror `momentum.py`: accumulate per-symbol history,
  honor rebalance schedule).
- Per rebalance bar: compute signal per symbol -> apply selection (`RANK` top/bottom K,
  or `THRESHOLD` filter) -> size (`EQUAL` / `SIGNAL_PROPORTIONAL`) -> apply `max_weight`
  cap and re-normalize -> return weights.
- Extract momentum's `_should_rebalance` helpers into a shared `schedule.py`.
- Register in `STRATEGY_REGISTRY`.

### Phase B4 — API surface
- Ensure `create_strategy` validates `CUSTOM` specs (calls B2) with clear messages.
- Add a **catalog endpoint** `GET /strategies/catalog` returning indicators + their
  params (name, type, range, default), selection modes, sizing methods, schedules.
  Makes the form data-driven — new indicators become backend-only additions.
- Wire `CUSTOM` into preflight for coverage/data-quality checks.

### Phase B5 — Parity & determinism tests
- Golden test: a `CUSTOM` spec replicating the momentum preset must produce identical
  equity/metrics to `run_momentum`. Proves interpreter correctness.
- Determinism test (same spec + snapshot + seed -> identical output).
- Edge cases: universe smaller than `count`, all-`None` warmup period, empty selection
  (return `None`, stay in cash).

---

## Frontend plan

### Phase F0 — Foundation
- Entry point: choose **Preset** (existing) vs **Custom strategy** (new) at build start.
- TS types for the spec mirroring the backend schema.
- Fetch `GET /strategies/catalog` and drive all form options from it (no hardcoded lists).

### Phase F1 — Form steps
- New custom variant of `StrategyStep.tsx`, sub-sections matching the spec:
  1. Signal — indicator dropdown + dynamic param fields (from catalog).
  2. Selection — mode toggle (Rank / Threshold) with conditional fields.
  3. Sizing — equal vs signal-proportional.
  4. Schedule — rebalance frequency.
  5. Constraints — max weight, long-only.
- Reuse `UniverseStep`, `RealismStep`, `ReviewStep` unchanged.

### Phase F2 — Validation & live feedback
- Client-side validation mirroring B2 (count <= universe size, warmup vs date range).
- Inline field errors, disabled submit until valid.
- **Live human-readable summary** as they fill it in, e.g.:
  *"Rank the universe by 90-day momentum, hold the top 5 equally, rebalance monthly,
  max 30% per name."* Best UX lever for a form — makes the abstract spec legible.

### Phase F3 — Review & submit
- ReviewStep renders the human-readable summary + resolved universe, then submits ->
  `create_strategy` (CUSTOM) -> launch run via existing run-creation flow.

### Phase F4 — Results & lifecycle
- Run dashboard identifies custom runs: show strategy summary in `RunHeader` /
  `ConfigTab` (not just "CUSTOM").
- Save / load / duplicate custom strategies from the strategies list.

### Phase F5 — Polish & on-ramps
- Per-indicator help tooltips and sensible defaults from the catalog.
- **"Start from a template"**: pre-fill the form from an existing preset (e.g. momentum)
  so users edit rather than face a blank form. Doubles as a live parity demo of B5.

---

## Sequencing & dependencies
- `B0 -> B1 -> B2 -> B3` is a hard chain.
- **B4's catalog endpoint should land early** (right after B2) because F0/F1 depend on it.
- Frontend can start **F0 against a mocked catalog** in parallel with B1–B3, then
  integrate once B4 is live.
- **B5 gates "done"** — don't expose custom strategies until momentum-parity passes.

## Designed-for-blocks-later
1. `signal` is a single object today but treat it as *the root of a tree* in code, so
   blocks make it a nested composition without touching selection/sizing/engine.
2. The catalog endpoint means new indicators/operators are backend-only additions.
3. The block editor becomes a richer front-end onto the *same* interpreter and spec.
