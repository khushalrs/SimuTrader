from app.backtest.buy_and_hold import run_buy_and_hold
from app.backtest.dca import run_dca
from app.backtest.errors import (
    BacktestError,
    ConfigValidationError,
    DataUnavailableError,
    NoTradingDaysError,
    UnsupportedStrategyError,
)
from app.backtest.fixed_weight_rebalance import run_fixed_weight_rebalance
from app.backtest.mean_reversion import run_mean_reversion
from app.backtest.momentum import run_momentum
try:
    from app.backtest.executor import claim_run, execute_run
except ModuleNotFoundError:
    # Allows engine-level tests/imports in minimal environments without Redis extras.
    def claim_run(*args, **kwargs):  # type: ignore[no-redef]
        raise ModuleNotFoundError("executor dependencies are unavailable in this environment")

    def execute_run(*args, **kwargs):  # type: ignore[no-redef]
        raise ModuleNotFoundError("executor dependencies are unavailable in this environment")

__all__ = [
    "BacktestError",
    "ConfigValidationError",
    "DataUnavailableError",
    "NoTradingDaysError",
    "UnsupportedStrategyError",
    "run_buy_and_hold",
    "run_fixed_weight_rebalance",
    "run_dca",
    "run_mean_reversion",
    "run_momentum",
    "execute_run",
    "claim_run",
]
