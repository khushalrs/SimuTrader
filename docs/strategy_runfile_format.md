# Strategy Runfile Format (Backend)

This document defines the canonical payload format for strategy backtest runs.

## Endpoint

- `POST /backtests`

Request shape:

```json
{
  "name": "my-run-name",
  "config_snapshot": {
    "...": "strategy config"
  },
  "data_snapshot_id": "snapshot_id_string",
  "seed": 42
}
```

## Canonical `config_snapshot` Base

All strategies use the same base structure below. Strategy-specific fields are in `strategy_params` and instrument allocations.

```json
{
  "version": 1,
  "strategy": "BUY_AND_HOLD",
  "strategy_params": {},
  "base_currency": "USD",
  "universe": {
    "instruments": [
      {
        "symbol": "AAPL",
        "asset_class": "US_EQUITY",
        "amount": 10000.0
      }
    ],
    "calendars": {
      "US_EQUITY": "US",
      "IN_EQUITY": "IN",
      "FX": "FX"
    }
  },
  "backtest": {
    "start_date": "2024-01-02",
    "end_date": "2024-01-12",
    "initial_cash": 10000.0,
    "initial_cash_by_currency": {
      "USD": 10000.0
    },
    "contributions": {
      "enabled": false
    }
  },
  "execution": {
    "commission": { "model": "BPS", "bps": 0, "min_fee": 0 },
    "slippage": { "model": "BPS", "bps": 0 },
    "fill_price": "CLOSE"
  },
  "commission": { "model": "BPS", "bps": 0, "min_fee_native": 0 },
  "slippage": { "model": "BPS", "bps": 0 },
  "fill_price_policy": "CLOSE",
  "data_policy": {
    "missing_bar": "FORWARD_FILL",
    "missing_fx": "FORWARD_FILL"
  },
  "financing": {
    "margin": {
      "enabled": false,
      "max_leverage": 1.0,
      "daily_interest_bps": 0
    },
    "shorting": {
      "enabled": false,
      "borrow_fee_daily_bps": 0
    }
  },
  "risk": {
    "max_gross_leverage": 1.0,
    "max_net_leverage": 1.0
  },
  "tax": {
    "enabled": true,
    "regime": "US"
  }
}
```

## Strategy Enum

- `BUY_AND_HOLD`
- `FIXED_WEIGHT_REBALANCE`
- `DCA`
- `MOMENTUM`
- `MEAN_REVERSION`

## Strategy-Specific Fields

### `BUY_AND_HOLD`

- Can use `amount` per instrument, or `weight`, or neither (equal-weight fallback).
- Multi-currency supported when:
  - all instruments use explicit `amount`
  - `backtest.initial_cash_by_currency` includes every instrument currency

### `FIXED_WEIGHT_REBALANCE`

`strategy_params`:

```json
{
  "target_weights": { "AAPL": 0.6, "MSFT": 0.4 },
  "rebalance_frequency": "DAILY|WEEKLY|MONTHLY|QUARTERLY",
  "drift_threshold": 0.0
}
```

Current runtime limitation: effectively single-currency only.

### `DCA`

`strategy_params`:

```json
{
  "buy_frequency": "DAILY|WEEKLY|MONTHLY|QUARTERLY",
  "weighting": "EQUAL|TARGET_WEIGHTS|INSTRUMENT_WEIGHTS"
}
```

`backtest.contributions` when enabled:

```json
{
  "enabled": true,
  "amount": 1000.0,
  "frequency": "WEEKLY"
}
```

Current runtime limitation: single-currency only.

### `MOMENTUM`

`strategy_params`:

```json
{
  "lookback_days": 20,
  "skip_days": 1,
  "top_k": 5,
  "rebalance_frequency": "MONTHLY",
  "weighting": "EQUAL"
}
```

Current runtime limitation: single-currency only.

### `MEAN_REVERSION`

`strategy_params`:

```json
{
  "lookback_days": 20,
  "entry_threshold": 1.5,
  "exit_threshold": 0.5,
  "hold_days": 5,
  "rebalance_frequency": "DAILY|WEEKLY"
}
```

Current runtime limitation: single-currency only.

## Consistency Rules (Important)

The structural contract is the same for all strategies:

1. `POST /backtests` accepts the same top-level fields.
2. `config_snapshot` uses the same base object shape.
3. Worker executes exactly the persisted `config_snapshot`.

Only strategy-specific values/constraints differ (mostly inside `strategy_params` and allocation style).

## Minimal Valid Payload Example

```json
{
  "name": "smoke-buy-hold",
  "data_snapshot_id": "smoke_e2e_v1",
  "seed": 42,
  "config_snapshot": {
    "version": 1,
    "strategy": "BUY_AND_HOLD",
    "universe": {
      "instruments": [
        { "symbol": "A", "asset_class": "US_EQUITY", "amount": 9900.0 }
      ]
    },
    "backtest": {
      "start_date": "2024-01-02",
      "end_date": "2024-01-12",
      "initial_cash": 10000.0
    },
    "data_policy": {
      "missing_bar": "FORWARD_FILL",
      "missing_fx": "FORWARD_FILL"
    }
  }
}
```

