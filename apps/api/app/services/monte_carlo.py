from __future__ import annotations

import hashlib
import json
from typing import Any

import numpy as np

MONTE_CARLO_VERSION = 1
PLOT_PATH_LIMIT = 30
BATCH_SIZE = 2000


def monte_carlo_identity(
    *,
    run_seed: int,
    method: str,
    n: int,
    block_len: int | None,
) -> tuple[str, int]:
    canonical = json.dumps(
        {
            "version": MONTE_CARLO_VERSION,
            "run_seed": int(run_seed),
            "method": method,
            "n": int(n),
            "block_len": block_len,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return digest, int(digest[:8], 16)


def daily_returns_from_equity(
    equity_values: list[float],
    initial_cash: float,
) -> np.ndarray:
    if not equity_values:
        raise ValueError("Monte Carlo requires at least one equity observation.")
    if initial_cash <= 0.0:
        raise ValueError("Monte Carlo requires positive initial capital.")
    values = np.asarray(equity_values, dtype=np.float64)
    if not np.all(np.isfinite(values)) or np.any(values <= 0.0):
        raise ValueError("Monte Carlo requires finite, positive equity observations.")
    previous = np.concatenate(([float(initial_cash)], values[:-1]))
    returns = values / previous - 1.0
    if returns.size < 2:
        raise ValueError("Monte Carlo requires at least two return observations.")
    if np.any(returns <= -1.0) or not np.all(np.isfinite(returns)):
        raise ValueError("Run returns cannot be compounded safely.")
    return returns


def _distribution(values: np.ndarray) -> dict[str, Any]:
    finite = values[np.isfinite(values)]
    if finite.size == 0:
        return {
            "p05": None,
            "p25": None,
            "p50": None,
            "p75": None,
            "p95": None,
            "mean": None,
            "std": None,
            "ci95": [],
        }
    percentiles = np.percentile(finite, [2.5, 5, 25, 50, 75, 95, 97.5])
    return {
        "p05": float(percentiles[1]),
        "p25": float(percentiles[2]),
        "p50": float(percentiles[3]),
        "p75": float(percentiles[4]),
        "p95": float(percentiles[5]),
        "mean": float(np.mean(finite)),
        "std": float(np.std(finite)),
        "ci95": [float(percentiles[0]), float(percentiles[6])],
    }


def _path_statistics(
    wealth: np.ndarray,
    *,
    risk_free_rate_annual: float,
    frequency: str,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    terminal = wealth[:, -1] - 1.0
    peak = np.maximum.accumulate(
        np.concatenate((np.ones((wealth.shape[0], 1)), wealth), axis=1),
        axis=1,
    )[:, 1:]
    max_drawdown = np.min(wealth / peak - 1.0, axis=1)
    previous = np.concatenate(
        (np.ones((wealth.shape[0], 1)), wealth[:, :-1]),
        axis=1,
    )
    path_returns = wealth / previous - 1.0
    means = np.mean(path_returns, axis=1)
    stds = np.std(path_returns, axis=1, ddof=1)
    if frequency == "daily":
        rf_period = (1.0 + risk_free_rate_annual) ** (1.0 / 252.0) - 1.0
        numerator = (means - rf_period) * 252.0
        denominator = stds * np.sqrt(252.0)
    else:
        numerator = means * np.sqrt(path_returns.shape[1])
        denominator = stds
    sharpe = np.full(means.shape, np.nan, dtype=np.float64)
    np.divide(
        numerator,
        denominator,
        out=sharpe,
        where=denominator > 0.0,
    )
    return terminal, max_drawdown, sharpe


def _sample_daily_returns(
    returns: np.ndarray,
    *,
    method: str,
    batch_size: int,
    block_len: int,
    rng: np.random.Generator,
) -> np.ndarray:
    horizon = returns.size
    if method == "bootstrap":
        indexes = rng.integers(0, horizon, size=(batch_size, horizon))
        return returns[indexes]
    block_count = (horizon + block_len - 1) // block_len
    starts = rng.integers(0, horizon, size=(batch_size, block_count))
    offsets = np.arange(block_len)
    indexes = (starts[:, :, None] + offsets[None, None, :]) % horizon
    return returns[indexes.reshape(batch_size, -1)[:, :horizon]]


def simulate_daily_returns(
    returns: np.ndarray,
    *,
    method: str,
    n: int,
    block_len: int,
    seed: int,
    risk_free_rate_annual: float = 0.0,
    plot_path_limit: int = PLOT_PATH_LIMIT,
) -> dict[str, Any]:
    if method not in {"bootstrap", "block_bootstrap"}:
        raise ValueError(f"Unsupported daily Monte Carlo method '{method}'.")
    if method == "block_bootstrap" and block_len > returns.size:
        raise ValueError("block_len cannot exceed the number of return observations.")
    rng = np.random.default_rng(seed)
    terminal_parts: list[np.ndarray] = []
    drawdown_parts: list[np.ndarray] = []
    sharpe_parts: list[np.ndarray] = []
    plot_paths: list[dict[str, Any]] = []
    completed = 0
    effective_batch_limit = max(
        1,
        min(BATCH_SIZE, 2_000_000 // max(int(returns.size), 1)),
    )
    effective_plot_limit = min(
        plot_path_limit,
        max(1, 100_000 // (int(returns.size) + 1)),
    )
    while completed < n:
        batch_size = min(effective_batch_limit, n - completed)
        sampled = _sample_daily_returns(
            returns,
            method=method,
            batch_size=batch_size,
            block_len=block_len,
            rng=rng,
        )
        wealth = np.cumprod(1.0 + sampled, axis=1)
        terminal, drawdown, sharpe = _path_statistics(
            wealth,
            risk_free_rate_annual=risk_free_rate_annual,
            frequency="daily",
        )
        terminal_parts.append(terminal)
        drawdown_parts.append(drawdown)
        sharpe_parts.append(sharpe)
        remaining_plot_paths = max(effective_plot_limit - len(plot_paths), 0)
        for offset in range(min(remaining_plot_paths, batch_size)):
            plot_paths.append(
                {
                    "path_id": completed + offset,
                    "values": [1.0, *wealth[offset].astype(float).tolist()],
                }
            )
        completed += batch_size
    return _result_payload(
        terminal=np.concatenate(terminal_parts),
        max_drawdown=np.concatenate(drawdown_parts),
        sharpe=np.concatenate(sharpe_parts),
        paths=plot_paths,
    )


def simulate_trade_shuffle(
    pnl_values: list[float],
    *,
    initial_cash: float,
    n: int,
    seed: int,
    plot_path_limit: int = PLOT_PATH_LIMIT,
) -> dict[str, Any]:
    pnl = np.asarray(pnl_values, dtype=np.float64)
    if pnl.size < 2:
        raise ValueError("trade_shuffle requires at least two realized trade events.")
    if initial_cash <= 0.0 or not np.all(np.isfinite(pnl)):
        raise ValueError("trade_shuffle requires finite PnL and positive initial capital.")
    rng = np.random.default_rng(seed)
    terminal_parts: list[np.ndarray] = []
    drawdown_parts: list[np.ndarray] = []
    sharpe_parts: list[np.ndarray] = []
    plot_paths: list[dict[str, Any]] = []
    completed = 0
    effective_plot_limit = min(
        plot_path_limit,
        max(1, 100_000 // (int(pnl.size) + 1)),
    )
    while completed < n:
        batch_size = min(BATCH_SIZE, n - completed)
        shuffled = np.vstack([rng.permutation(pnl) for _ in range(batch_size)])
        equity = initial_cash + np.cumsum(shuffled, axis=1)
        if np.any(equity <= 0.0):
            raise ValueError(
                "trade_shuffle produced non-positive equity; trade PnL cannot be compounded."
            )
        wealth = equity / initial_cash
        terminal, drawdown, sharpe = _path_statistics(
            wealth,
            risk_free_rate_annual=0.0,
            frequency="trade_event",
        )
        terminal_parts.append(terminal)
        drawdown_parts.append(drawdown)
        sharpe_parts.append(sharpe)
        remaining_plot_paths = max(effective_plot_limit - len(plot_paths), 0)
        for offset in range(min(remaining_plot_paths, batch_size)):
            plot_paths.append(
                {
                    "path_id": completed + offset,
                    "values": [1.0, *wealth[offset].astype(float).tolist()],
                }
            )
        completed += batch_size
    return _result_payload(
        terminal=np.concatenate(terminal_parts),
        max_drawdown=np.concatenate(drawdown_parts),
        sharpe=np.concatenate(sharpe_parts),
        paths=plot_paths,
    )


def _result_payload(
    *,
    terminal: np.ndarray,
    max_drawdown: np.ndarray,
    sharpe: np.ndarray,
    paths: list[dict[str, Any]],
) -> dict[str, Any]:
    finite_terminal = terminal[np.isfinite(terminal)]
    probability_positive = (
        float(np.mean(finite_terminal > 0.0)) if finite_terminal.size else 0.0
    )
    finite_drawdown = max_drawdown[np.isfinite(max_drawdown)]
    drawdown_at_risk = (
        float(-np.percentile(finite_drawdown, 5.0))
        if finite_drawdown.size
        else None
    )
    return {
        "terminal_return": _distribution(terminal),
        "max_drawdown": _distribution(max_drawdown),
        "sharpe": _distribution(sharpe),
        "probability_positive": probability_positive,
        "drawdown_at_risk_95": drawdown_at_risk,
        "paths": paths,
    }
