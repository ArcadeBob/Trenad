import numpy as np
import pandas as pd
from pattern_scanner import PatternResult, PatternDetector


def test_pattern_result_creation():
    result = PatternResult(
        ticker="AAPL",
        pattern_type="Cup & Handle",
        confidence_score=85.0,
        buy_point=150.0,
        current_price=148.0,
        distance_to_pivot=-1.33,
        base_depth=20.0,
        base_length_weeks=12,
        volume_confirmation=True,
        above_50ma=True,
        above_200ma=True,
        rs_rating=90.0,
        pattern_details={"cup_low": 120.0, "handle_low": 145.0},
    )
    assert result.ticker == "AAPL"
    assert result.confidence_score == 85.0
    assert result.pattern_details["cup_low"] == 120.0


def test_pattern_result_status_at_pivot():
    """Within 1% above or below buy point = At Pivot"""
    result = PatternResult(
        ticker="MSFT", pattern_type="Flat Base", confidence_score=70.0,
        buy_point=100.0, current_price=99.5, distance_to_pivot=-0.5,
        base_depth=10.0, base_length_weeks=6, volume_confirmation=True,
        above_50ma=True, above_200ma=True, rs_rating=80.0, pattern_details={},
    )
    assert result.status == "At Pivot"


def test_pattern_result_status_near_pivot():
    """Within 5% below buy point = Near Pivot"""
    result = PatternResult(
        ticker="MSFT", pattern_type="Flat Base", confidence_score=70.0,
        buy_point=100.0, current_price=96.0, distance_to_pivot=-4.0,
        base_depth=10.0, base_length_weeks=6, volume_confirmation=True,
        above_50ma=True, above_200ma=True, rs_rating=80.0, pattern_details={},
    )
    assert result.status == "Near Pivot"


def test_pattern_result_status_building():
    """More than 5% below buy point = Building"""
    result = PatternResult(
        ticker="MSFT", pattern_type="Flat Base", confidence_score=70.0,
        buy_point=100.0, current_price=90.0, distance_to_pivot=-10.0,
        base_depth=10.0, base_length_weeks=6, volume_confirmation=True,
        above_50ma=True, above_200ma=True, rs_rating=80.0, pattern_details={},
    )
    assert result.status == "Building"


def test_pattern_result_status_extended():
    """More than 5% above buy point = Extended"""
    result = PatternResult(
        ticker="MSFT", pattern_type="Flat Base", confidence_score=70.0,
        buy_point=100.0, current_price=108.0, distance_to_pivot=8.0,
        base_depth=10.0, base_length_weeks=6, volume_confirmation=True,
        above_50ma=True, above_200ma=True, rs_rating=80.0, pattern_details={},
    )
    assert result.status == "Extended"


def _make_price_df(closes: list[float], volumes: list[float] | None = None) -> pd.DataFrame:
    """Helper to create a minimal DataFrame for testing."""
    n = len(closes)
    if volumes is None:
        volumes = [1_000_000] * n
    dates = pd.bdate_range(end="2026-02-20", periods=n)
    return pd.DataFrame({
        "Open": closes,
        "High": [c * 1.01 for c in closes],
        "Low": [c * 0.99 for c in closes],
        "Close": closes,
        "Volume": volumes,
    }, index=dates)


def test_find_local_peaks():
    prices = [10, 11, 12, 13, 14, 15, 14, 13, 12, 11, 10]
    closes = pd.Series(prices)
    detector = PatternDetector()
    peaks = detector.find_local_peaks(closes, window=3)
    assert 5 in peaks


def test_find_local_troughs():
    prices = [15, 14, 13, 12, 11, 10, 11, 12, 13, 14, 15]
    closes = pd.Series(prices)
    detector = PatternDetector()
    troughs = detector.find_local_troughs(closes, window=3)
    assert 5 in troughs


def test_add_moving_averages():
    closes = list(range(100, 300))  # 200 data points
    df = _make_price_df(closes)
    detector = PatternDetector()
    result = detector.add_moving_averages(df)
    assert "MA10" in result.columns
    assert "MA20" in result.columns
    assert "MA50" in result.columns
    assert "MA200" in result.columns
    assert "AvgVolume50" in result.columns
    assert pd.notna(result["MA200"].iloc[-1])


def test_calculate_relative_strength():
    """Stock that doubled while SPY gained 10% should have high RS."""
    detector = PatternDetector()
    n = 252
    stock_closes = [100 + (100 * i / n) for i in range(n)]
    spy_closes = [400 + (40 * i / n) for i in range(n)]
    stock_df = _make_price_df(stock_closes)
    spy_df = _make_price_df(spy_closes)
    rs = detector.calculate_relative_strength(stock_df, spy_df)
    assert rs > 80


def test_detect_flat_base_valid():
    """Tight consolidation <15% range after 30%+ uptrend."""
    detector = PatternDetector()
    # 30 days flat preamble + 140 day uptrend (100 -> 140, 40% gain) + 40 days flat = 210 total
    # 126-day max gain in uptrend = 40*126/140 = 36% > 30% threshold
    preamble = [100.0] * 30
    uptrend = [100 + (40 * i / 140) for i in range(140)]
    flat = [140 + 3 * np.sin(i * 0.3) for i in range(40)]
    closes = preamble + uptrend + flat
    volumes = [1_000_000] * len(closes)
    flat_start = len(preamble) + len(uptrend)
    for i in range(flat_start, len(closes)):
        volumes[i] = 600_000
    df = _make_price_df(closes, volumes)
    df = detector.add_moving_averages(df)
    result = detector.detect_flat_base(df)
    assert result is not None
    assert result["pattern_type"] == "Flat Base"
    assert result["base_depth"] < 15.0
    assert result["base_length_weeks"] >= 5


def test_detect_flat_base_too_deep():
    """Consolidation >15% should NOT be flat base."""
    detector = PatternDetector()
    preamble = [100.0] * 30
    uptrend = [100 + (50 * i / 140) for i in range(140)]
    # 20%+ range consolidation — too deep for flat base
    deep_consol = [150 - (30 * i / 40) + (15 * (i % 2)) for i in range(40)]
    closes = preamble + uptrend + deep_consol
    df = _make_price_df(closes)
    df = detector.add_moving_averages(df)
    result = detector.detect_flat_base(df)
    assert result is None


def test_detect_flat_base_no_prior_uptrend():
    """Flat consolidation without 30%+ prior uptrend should NOT match."""
    detector = PatternDetector()
    preamble = [100.0] * 30
    uptrend = [100 + (10 * i / 140) for i in range(140)]
    flat = [110 + 2 * np.sin(i * 0.3) for i in range(40)]
    closes = preamble + uptrend + flat
    df = _make_price_df(closes)
    df = detector.add_moving_averages(df)
    result = detector.detect_flat_base(df)
    assert result is None
