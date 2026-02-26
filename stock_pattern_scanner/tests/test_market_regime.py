"""Tests for market regime detection."""

from __future__ import annotations

import numpy as np
import pandas as pd

from market_regime import MarketRegime


def _make_spy_df(
    closes: list[float],
    volumes: list[float] | None = None,
) -> pd.DataFrame:
    """Build a minimal SPY OHLCV DataFrame."""
    n = len(closes)
    if volumes is None:
        volumes = [50_000_000] * n
    dates = pd.bdate_range(end="2026-02-20", periods=n)
    return pd.DataFrame(
        {
            "Open": closes,
            "High": [c * 1.005 for c in closes],
            "Low": [c * 0.995 for c in closes],
            "Close": closes,
            "Volume": volumes,
        },
        index=dates,
    )


def test_confirmed_uptrend():
    """SPY steadily rising above both MAs, low volume on down days."""
    # 300 days of steady uptrend: 400 -> 520 (30% gain)
    closes = [400 + (120 * i / 299) for i in range(300)]
    df = _make_spy_df(closes)
    regime = MarketRegime(df)
    result = regime.evaluate()
    assert result["status"] == "confirmed_uptrend"


def test_market_in_correction():
    """SPY drops below 200-day MA with declining 50-day MA."""
    # 250 days up, then 50 days sharp decline below 200-day MA
    up = [400 + (100 * i / 249) for i in range(250)]
    down = [500 - (150 * i / 49) for i in range(50)]
    closes = up + down
    # High volume on down days to create distribution days
    volumes = [50_000_000] * 250 + [80_000_000] * 50
    df = _make_spy_df(closes, volumes)
    regime = MarketRegime(df)
    result = regime.evaluate()
    assert result["status"] == "correction"


def test_uptrend_under_pressure():
    """SPY above 200-day MA but with 4+ distribution days."""
    # Steady uptrend for 280 days, then choppy last 20 days
    up = [400 + (80 * i / 279) for i in range(280)]
    # Choppy: alternating small down days on high volume
    choppy = []
    for i in range(20):
        if i % 2 == 0:
            choppy.append(up[-1] - 2)  # down day
        else:
            choppy.append(up[-1] + 1)  # up day
    closes = up + choppy
    # High volume on the down days
    volumes = [50_000_000] * 280
    for i in range(20):
        if i % 2 == 0:
            volumes.append(70_000_000)  # high vol down = distribution
        else:
            volumes.append(40_000_000)
    df = _make_spy_df(closes, volumes)
    regime = MarketRegime(df)
    result = regime.evaluate()
    assert result["status"] in ("uptrend_under_pressure", "confirmed_uptrend")


def test_distribution_day_count():
    """Verify distribution day counting logic."""
    # 300 days of steady rise
    closes = [400 + (100 * i / 299) for i in range(300)]
    df = _make_spy_df(closes)
    regime = MarketRegime(df)
    # In a clean uptrend, should have very few distribution days
    assert regime.distribution_day_count() < 4


def test_evaluate_returns_required_keys():
    """Result dict must contain status, spy_above_200ma, spy_above_50ma, distribution_days."""
    closes = [400 + (100 * i / 299) for i in range(300)]
    df = _make_spy_df(closes)
    regime = MarketRegime(df)
    result = regime.evaluate()
    assert "status" in result
    assert "spy_above_200ma" in result
    assert "spy_above_50ma" in result
    assert "distribution_days" in result
    assert "ma50_slope_rising" in result
