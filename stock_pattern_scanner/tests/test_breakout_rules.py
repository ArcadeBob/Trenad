"""Tests for breakout confirmation and entry rules."""

from __future__ import annotations

import pandas as pd

from breakout_rules import BreakoutAnalyzer


def _make_df(
    closes: list[float],
    volumes: list[float] | None = None,
    highs: list[float] | None = None,
    lows: list[float] | None = None,
) -> pd.DataFrame:
    n = len(closes)
    if volumes is None:
        volumes = [1_000_000] * n
    if highs is None:
        highs = [c * 1.01 for c in closes]
    if lows is None:
        lows = [c * 0.99 for c in closes]
    dates = pd.bdate_range(end="2026-02-20", periods=n)
    df = pd.DataFrame(
        {"Open": closes, "High": highs, "Low": lows, "Close": closes, "Volume": volumes},
        index=dates,
    )
    df["AvgVolume50"] = pd.Series(volumes).rolling(50).mean().values
    return df


def test_stop_loss_price():
    """Stop loss should be 7% below buy point."""
    df = _make_df([100.0] * 100)
    ba = BreakoutAnalyzer(df, buy_point=150.0)
    assert ba.stop_loss_price() == round(150.0 * 0.93, 2)


def test_profit_target_price():
    """Profit target should be 20% above buy point."""
    df = _make_df([100.0] * 100)
    ba = BreakoutAnalyzer(df, buy_point=150.0)
    assert ba.profit_target_price() == round(150.0 * 1.20, 2)


def test_breakout_confirmed_with_volume_surge():
    """Price at pivot with 40%+ volume surge and close in upper half = confirmed."""
    n = 100
    closes = [100.0] * (n - 1) + [151.0]  # Last day closes above pivot
    volumes = [1_000_000] * (n - 1) + [2_000_000]  # 100%+ surge
    highs = [c * 1.01 for c in closes[:-1]] + [152.0]
    lows = [c * 0.99 for c in closes[:-1]] + [149.0]
    df = _make_df(closes, volumes, highs, lows)
    ba = BreakoutAnalyzer(df, buy_point=150.0)
    result = ba.evaluate()
    assert result["breakout_confirmed"] is True


def test_breakout_not_confirmed_low_volume():
    """Price at pivot but without volume surge = not confirmed."""
    n = 100
    closes = [100.0] * (n - 1) + [151.0]
    volumes = [1_000_000] * n  # No surge
    df = _make_df(closes, volumes)
    ba = BreakoutAnalyzer(df, buy_point=150.0)
    result = ba.evaluate()
    assert result["breakout_confirmed"] is False


def test_breakout_pending_below_pivot():
    """Price still below pivot = None (pending)."""
    n = 100
    closes = [100.0] * n
    df = _make_df(closes)
    ba = BreakoutAnalyzer(df, buy_point=150.0)
    result = ba.evaluate()
    assert result["breakout_confirmed"] is None


def test_evaluate_returns_required_keys():
    """Result must have all expected keys."""
    df = _make_df([100.0] * 100)
    ba = BreakoutAnalyzer(df, buy_point=150.0)
    result = ba.evaluate()
    assert "stop_loss_price" in result
    assert "profit_target_price" in result
    assert "breakout_confirmed" in result
    assert "volume_surge_pct" in result


def test_score_confirmed_breakout():
    """Confirmed breakout should score 5 points."""
    n = 100
    closes = [100.0] * (n - 1) + [151.0]
    volumes = [1_000_000] * (n - 1) + [2_000_000]
    highs = [c * 1.01 for c in closes[:-1]] + [152.0]
    lows = [c * 0.99 for c in closes[:-1]] + [149.0]
    df = _make_df(closes, volumes, highs, lows)
    ba = BreakoutAnalyzer(df, buy_point=150.0)
    assert ba.score() == 5.0


def test_score_no_breakout():
    """No breakout = 0 points."""
    df = _make_df([100.0] * 100)
    ba = BreakoutAnalyzer(df, buy_point=150.0)
    assert ba.score() == 0.0
