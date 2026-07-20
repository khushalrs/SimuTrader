from __future__ import annotations

from datetime import date
from math import sqrt

import pytest

from app.backtest.engine import (
    _align_benchmark_to_base,
    _compute_metrics,
    _linear_percentile,
)


def test_linear_percentile_matches_numpy_default_interpolation() -> None:
    assert _linear_percentile([-0.1, 0.1, 0.1], 0.05) == pytest.approx(-0.08)


def test_compute_metrics_populates_downside_tail_turnover_and_benchmark_metrics() -> None:
    equity = [100.0, 110.0, 99.0, 94.05, 103.455]
    benchmark = [100.0, 105.0, 99.75, 97.25625, 102.1190625]

    metrics = _compute_metrics(
        equity,
        initial_cash=100.0,
        turnover_notional_base=300.0,
        benchmark_series_base=benchmark,
    )

    daily_mean = (0.1 - 0.1 - 0.05 + 0.1) / 4.0
    downside_deviation = sqrt((0.1**2 + 0.05**2) / 4.0)
    expected_sortino = (daily_mean * 252.0) / (downside_deviation * sqrt(252.0))
    expected_turnover = 300.0 / ((sum(equity) / len(equity)) * (4.0 / 252.0))

    assert metrics["sortino"] == pytest.approx(expected_sortino)
    assert metrics["turnover"] == pytest.approx(expected_turnover)
    assert metrics["calmar"] is not None
    assert metrics["var_95"] == pytest.approx(0.0925)
    assert metrics["cvar_95"] == pytest.approx(0.1)
    assert metrics["best_day"] == pytest.approx(0.1)
    assert metrics["worst_day"] == pytest.approx(-0.1)
    assert metrics["win_rate"] == pytest.approx(0.5)
    assert metrics["avg_win_day"] == pytest.approx(0.1)
    assert metrics["avg_loss_day"] == pytest.approx(-0.075)
    assert metrics["beta"] == pytest.approx(2.0)
    assert metrics["alpha"] == pytest.approx(0.0, abs=1e-12)
    assert metrics["information_ratio"] is not None


def test_sortino_requires_two_negative_observations() -> None:
    metrics = _compute_metrics([100.0, 110.0, 99.0, 108.9, 119.79])
    assert metrics["sortino"] is None


def test_foreign_benchmark_is_forward_filled_and_converted_to_base() -> None:
    dates = [date(2024, 1, 2), date(2024, 1, 3), date(2024, 1, 4)]

    aligned = _align_benchmark_to_base(
        dates,
        {
            date(2024, 1, 2): 8000.0,
            date(2024, 1, 4): 8400.0,
        },
        "INR",
        "USD",
        {
            date(2024, 1, 2): 80.0,
            date(2024, 1, 4): 84.0,
        },
    )

    assert aligned == pytest.approx([100.0, 100.0, 100.0])


def test_missing_benchmark_produces_null_relative_metrics() -> None:
    metrics = _compute_metrics(
        [100.0, 101.0, 102.0],
        benchmark_series_base=[None, None, None],
    )

    assert metrics["beta"] is None
    assert metrics["alpha"] is None
    assert metrics["information_ratio"] is None
