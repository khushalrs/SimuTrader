from __future__ import annotations

import numpy as np
import pytest

from app.services.monte_carlo import (
    daily_returns_from_equity,
    monte_carlo_identity,
    simulate_daily_returns,
    simulate_trade_shuffle,
)


def test_daily_bootstrap_is_seeded_and_returns_bands_and_plot_paths() -> None:
    returns = daily_returns_from_equity(
        [101.0, 99.0, 103.0, 104.0],
        100.0,
    )
    first = simulate_daily_returns(
        returns,
        method="bootstrap",
        n=200,
        block_len=2,
        seed=42,
    )
    second = simulate_daily_returns(
        returns,
        method="bootstrap",
        n=200,
        block_len=2,
        seed=42,
    )

    assert first == second
    assert len(first["paths"]) == 30
    assert len(first["paths"][0]["values"]) == len(returns) + 1
    assert first["terminal_return"]["p05"] <= first["terminal_return"]["p95"]
    assert 0.0 <= first["probability_positive"] <= 1.0
    assert first["drawdown_at_risk_95"] >= 0.0


def test_block_bootstrap_rejects_block_longer_than_history() -> None:
    with pytest.raises(ValueError, match="block_len cannot exceed"):
        simulate_daily_returns(
            np.asarray([0.01, -0.01]),
            method="block_bootstrap",
            n=100,
            block_len=3,
            seed=42,
        )


def test_trade_shuffle_preserves_terminal_pnl_but_changes_path_risk() -> None:
    result = simulate_trade_shuffle(
        [20.0, -15.0, 10.0, -5.0],
        initial_cash=100.0,
        n=200,
        seed=42,
    )

    assert result["terminal_return"]["mean"] == pytest.approx(0.1)
    assert result["terminal_return"]["std"] == pytest.approx(0.0, abs=1e-12)
    assert result["max_drawdown"]["p05"] < result["max_drawdown"]["p95"]


def test_monte_carlo_identity_is_request_specific_and_reproducible() -> None:
    first = monte_carlo_identity(
        run_seed=42,
        method="bootstrap",
        n=5000,
        block_len=None,
    )
    second = monte_carlo_identity(
        run_seed=42,
        method="bootstrap",
        n=5000,
        block_len=None,
    )
    changed = monte_carlo_identity(
        run_seed=42,
        method="block_bootstrap",
        n=5000,
        block_len=5,
    )
    assert first == second
    assert changed != first
