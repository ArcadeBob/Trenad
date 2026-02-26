"""Shared test fixtures for stock_pattern_scanner tests."""

from __future__ import annotations

from typing import Any

import pandas as pd
import pytest

from database import ScanDatabase
from pattern_scanner import PatternResult

_PATTERN_RESULT_DEFAULTS = dict(
    ticker="AAPL",
    pattern_type="Flat Base",
    confidence_score=75.0,
    buy_point=150.0,
    current_price=148.0,
    distance_to_pivot=-1.33,
    base_depth=10.0,
    base_length_weeks=7,
    volume_confirmation=True,
    above_50ma=True,
    above_200ma=True,
    rs_rating=85.0,
    pattern_details={},
    stop_loss_price=139.5,
    profit_target_price=180.0,
    breakout_confirmed=None,
    volume_surge_pct=None,
    volume_rating="C",
    trend_score=0.0,
)


@pytest.fixture
def make_pattern_result():
    """Factory: builds PatternResult with sensible defaults, override any field."""
    def _factory(**overrides: Any) -> PatternResult:
        kwargs = {**_PATTERN_RESULT_DEFAULTS, **overrides}
        return PatternResult(**kwargs)
    return _factory


@pytest.fixture
def make_price_df():
    """Factory: builds a minimal OHLCV DataFrame from a list of close prices."""
    def _factory(
        closes: list[float],
        volumes: list[float] | None = None,
    ) -> pd.DataFrame:
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
    return _factory


@pytest.fixture
def tmp_db(tmp_path):
    """Provides a ScanDatabase backed by a temporary file."""
    return ScanDatabase(str(tmp_path / "test.db"))
