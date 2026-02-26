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


def test_add_moving_averages(make_price_df):
    closes = list(range(100, 300))  # 200 data points
    df = make_price_df(closes)
    detector = PatternDetector()
    result = detector.add_moving_averages(df)
    assert "MA10" in result.columns
    assert "MA20" in result.columns
    assert "MA50" in result.columns
    assert "MA200" in result.columns
    assert "AvgVolume50" in result.columns
    assert pd.notna(result["MA200"].iloc[-1])


def test_calculate_relative_strength(make_price_df):
    """Stock that doubled while SPY gained 10% should have high RS."""
    detector = PatternDetector()
    n = 252
    stock_closes = [100 + (100 * i / n) for i in range(n)]
    spy_closes = [400 + (40 * i / n) for i in range(n)]
    stock_df = make_price_df(stock_closes)
    spy_df = make_price_df(spy_closes)
    rs = detector.calculate_relative_strength(stock_df, spy_df)
    assert rs > 80


def test_detect_flat_base_valid(make_price_df):
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
    df = make_price_df(closes, volumes)
    df = detector.add_moving_averages(df)
    result = detector.detect_flat_base(df)
    assert result is not None
    assert result["pattern_type"] == "Flat Base"
    assert result["base_depth"] < 15.0
    assert result["base_length_weeks"] >= 5


def test_detect_flat_base_too_deep(make_price_df):
    """Consolidation >15% should NOT be flat base."""
    detector = PatternDetector()
    preamble = [100.0] * 30
    uptrend = [100 + (50 * i / 140) for i in range(140)]
    # 20%+ range consolidation — too deep for flat base
    deep_consol = [150 - (30 * i / 40) + (15 * (i % 2)) for i in range(40)]
    closes = preamble + uptrend + deep_consol
    df = make_price_df(closes)
    df = detector.add_moving_averages(df)
    result = detector.detect_flat_base(df)
    assert result is None


def test_detect_flat_base_no_prior_uptrend(make_price_df):
    """Flat consolidation without 30%+ prior uptrend should NOT match."""
    detector = PatternDetector()
    preamble = [100.0] * 30
    uptrend = [100 + (10 * i / 140) for i in range(140)]
    flat = [110 + 2 * np.sin(i * 0.3) for i in range(40)]
    closes = preamble + uptrend + flat
    df = make_price_df(closes)
    df = detector.add_moving_averages(df)
    result = detector.detect_flat_base(df)
    assert result is None


def test_detect_double_bottom_valid(make_price_df):
    """W-pattern with two lows within 3-5% of each other."""
    detector = PatternDetector()

    # Build: uptrend -> first low -> bounce -> second low -> recovery
    uptrend = [100 + (50 * i / 100) for i in range(100)]     # 100 -> 150
    decline1 = [150 - (30 * i / 30) for i in range(30)]       # 150 -> 120
    bounce = [120 + (15 * i / 25) for i in range(25)]          # 120 -> 135
    decline2 = [135 - (16 * i / 25) for i in range(25)]        # 135 -> 119
    recovery = [119 + (14 * i / 30) for i in range(30)]        # 119 -> 133

    closes = uptrend + decline1 + bounce + decline2 + recovery
    df = make_price_df(closes)
    df = detector.add_moving_averages(df)

    result = detector.detect_double_bottom(df)
    assert result is not None
    assert result["pattern_type"] == "Double Bottom"


def test_detect_double_bottom_lows_too_far_apart(make_price_df):
    """Two lows more than 5% apart should NOT match."""
    detector = PatternDetector()

    uptrend = [100 + (50 * i / 100) for i in range(100)]
    decline1 = [150 - (30 * i / 30) for i in range(30)]       # -> 120
    bounce = [120 + (15 * i / 25) for i in range(25)]
    decline2 = [135 - (35 * i / 25) for i in range(25)]        # -> 100 (too far from 120)
    recovery = [100 + (14 * i / 30) for i in range(30)]

    closes = uptrend + decline1 + bounce + decline2 + recovery
    df = make_price_df(closes)
    df = detector.add_moving_averages(df)

    result = detector.detect_double_bottom(df)
    assert result is None


def test_detect_cup_and_handle_valid(make_price_df):
    """U-shaped cup (12-33% depth) with small handle."""
    detector = PatternDetector()

    # Prior uptrend: 100 -> 150 (50% gain)
    uptrend = [100 + (50 * i / 100) for i in range(100)]
    # Cup left side: 150 -> 120 (20% decline)
    left_side = [150 - (30 * i / 40) for i in range(40)]
    # Cup bottom: rounded
    bottom = [120 + 2 * np.sin(i * np.pi / 30) for i in range(30)]
    # Cup right side: 120 -> 148
    right_side = [120 + (28 * i / 40) for i in range(40)]
    # Handle: small pullback 148 -> 142 -> 146
    handle = [148 - (6 * i / 10) for i in range(10)] + [142 + (4 * i / 10) for i in range(10)]

    closes = uptrend + left_side + bottom + right_side + handle
    volumes = [1_000_000] * len(closes)
    # Declining volume in handle
    handle_start = len(uptrend) + len(left_side) + len(bottom) + len(right_side)
    for i in range(handle_start, len(closes)):
        volumes[i] = 500_000

    df = make_price_df(closes, volumes)
    df = detector.add_moving_averages(df)

    result = detector.detect_cup_and_handle(df)
    assert result is not None
    assert result["pattern_type"] in ("Cup & Handle", "Deep Cup & Handle")
    assert 12 <= result["base_depth"] <= 33


def test_detect_cup_and_handle_deep(make_price_df):
    """Cup with 33-50% depth should be classified as Deep Cup & Handle."""
    detector = PatternDetector()

    uptrend = [100 + (60 * i / 100) for i in range(100)]      # 100 -> 160
    left_side = [160 - (64 * i / 40) for i in range(40)]       # 160 -> 96 (40% decline)
    bottom = [96 + 3 * np.sin(i * np.pi / 30) for i in range(30)]
    right_side = [96 + (60 * i / 50) for i in range(50)]       # 96 -> 156
    handle = [156 - (8 * i / 10) for i in range(10)] + [148 + (6 * i / 10) for i in range(10)]

    closes = uptrend + left_side + bottom + right_side + handle
    df = make_price_df(closes)
    df = detector.add_moving_averages(df)

    result = detector.detect_cup_and_handle(df)
    assert result is not None
    assert result["pattern_type"] == "Deep Cup & Handle"


def test_detect_cup_and_handle_too_shallow(make_price_df):
    """Cup with <12% depth should NOT match."""
    detector = PatternDetector()

    uptrend = [100 + (50 * i / 100) for i in range(100)]
    # Only 8% decline — too shallow
    left_side = [150 - (12 * i / 40) for i in range(40)]
    bottom = [138 + 1 * np.sin(i * np.pi / 30) for i in range(30)]
    right_side = [138 + (10 * i / 40) for i in range(40)]
    handle = [148 - (3 * i / 10) for i in range(10)] + [145 + (2 * i / 10) for i in range(10)]

    closes = uptrend + left_side + bottom + right_side + handle
    df = make_price_df(closes)
    df = detector.add_moving_averages(df)

    result = detector.detect_cup_and_handle(df)
    assert result is None


def test_confidence_score_high_quality(make_price_df):
    """Pattern with all positive signals should score 40+ (without external module scores)."""
    detector = PatternDetector()
    pattern = {
        "pattern_type": "Flat Base",
        "base_depth": 10.0,
        "volume_confirmation": True,
        "base_length_weeks": 7,
    }
    df = make_price_df(list(range(100, 300)))
    df = detector.add_moving_averages(df)
    score = detector.calculate_confidence(pattern, df)
    assert score >= 40


def test_confidence_score_low_quality(make_price_df):
    """Pattern with negative signals should score below 60."""
    detector = PatternDetector()
    pattern = {
        "pattern_type": "Cup & Handle",
        "base_depth": 48.0,  # Very deep
        "volume_confirmation": False,
        "base_length_weeks": 60,  # Very long
    }
    # Declining prices — below MAs
    closes = [200 - i * 0.5 for i in range(200)]
    df = make_price_df(closes)
    df = detector.add_moving_averages(df)
    score = detector.calculate_confidence(pattern, df)
    assert score < 60
