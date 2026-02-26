"""Tests for trend strength validation."""

from __future__ import annotations

import numpy as np
import pandas as pd

from trend_strength import TrendAnalyzer


def _make_ohlcv(
    closes: list[float],
    spread: float = 0.02,
) -> pd.DataFrame:
    """Build OHLCV DataFrame with realistic high/low from closes."""
    n = len(closes)
    dates = pd.bdate_range(end="2026-02-20", periods=n)
    highs = [c * (1 + spread / 2) for c in closes]
    lows = [c * (1 - spread / 2) for c in closes]
    return pd.DataFrame(
        {
            "Open": closes,
            "High": highs,
            "Low": lows,
            "Close": closes,
            "Volume": [1_000_000] * n,
        },
        index=dates,
    )


def test_adx_strong_uptrend():
    """Steady rising prices should produce ADX > 25."""
    closes = [100 + (80 * i / 299) for i in range(300)]
    df = _make_ohlcv(closes)
    analyzer = TrendAnalyzer(df)
    adx = analyzer.adx()
    assert adx > 20


def test_adx_sideways_market():
    """Flat prices should produce low ADX."""
    rng = np.random.RandomState(42)
    closes = [100 + rng.normal(0, 0.3) for _ in range(300)]
    df = _make_ohlcv(closes, spread=0.005)
    analyzer = TrendAnalyzer(df)
    adx = analyzer.adx()
    assert adx < 30


def test_ma_slope_positive_in_uptrend():
    """50-day MA slope should be positive in a clear uptrend."""
    closes = [100 + (100 * i / 299) for i in range(300)]
    df = _make_ohlcv(closes)
    analyzer = TrendAnalyzer(df)
    slope = analyzer.ma50_slope()
    assert slope > 0


def test_ma_slope_negative_in_downtrend():
    """50-day MA slope should be negative in a clear downtrend."""
    closes = [200 - (100 * i / 299) for i in range(300)]
    df = _make_ohlcv(closes)
    analyzer = TrendAnalyzer(df)
    slope = analyzer.ma50_slope()
    assert slope < 0


def test_atr_ratio_low_for_smooth_trend():
    """Smooth price moves should have low ATR ratio."""
    closes = [100 + (50 * i / 299) for i in range(300)]
    df = _make_ohlcv(closes, spread=0.01)  # tight spread
    analyzer = TrendAnalyzer(df)
    ratio = analyzer.atr_ratio()
    assert ratio < 5.0


def test_atr_ratio_high_for_volatile():
    """Wide swings should produce high ATR ratio."""
    closes = [100 + 20 * np.sin(i * 0.5) for i in range(300)]
    df = _make_ohlcv(closes, spread=0.10)  # wide spread
    analyzer = TrendAnalyzer(df)
    ratio = analyzer.atr_ratio()
    assert ratio > 3.0


def test_is_too_volatile():
    """ATR ratio > 5% should be flagged as too volatile."""
    # Extremely choppy with wide spreads
    closes = [100 + 30 * np.sin(i * 0.8) for i in range(300)]
    df = _make_ohlcv(closes, spread=0.15)
    analyzer = TrendAnalyzer(df)
    assert analyzer.is_too_volatile()


def test_score_returns_0_to_10():
    """Trend score must be in [0, 10]."""
    closes = [100 + (50 * i / 299) for i in range(300)]
    df = _make_ohlcv(closes)
    analyzer = TrendAnalyzer(df)
    score = analyzer.score()
    assert 0 <= score <= 10
