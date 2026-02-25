from pattern_scanner import PatternResult


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
