"""Tests for sector relative strength analysis."""

from __future__ import annotations

import numpy as np
import pandas as pd
from unittest.mock import MagicMock, patch

from sector_strength import SectorAnalyzer


class TestSectorMapping:
    def test_known_tech_stock_maps_to_xlk(self):
        analyzer = SectorAnalyzer.__new__(SectorAnalyzer)
        analyzer._ticker_sector_cache = {}
        analyzer._sector_overrides = {"AAPL": "Technology"}
        assert analyzer._get_sector("AAPL") == "Technology"

    def test_unknown_ticker_falls_back_to_yfinance(self):
        analyzer = SectorAnalyzer.__new__(SectorAnalyzer)
        analyzer._ticker_sector_cache = {}
        analyzer._sector_overrides = {}
        with patch("sector_strength.yfinance.Ticker") as mock_yf:
            mock_info = MagicMock()
            mock_info.info = {"sector": "Healthcare"}
            mock_yf.return_value = mock_info
            sector = analyzer._get_sector("UNKNOWN")
            assert sector == "Healthcare"


class TestSectorRS:
    def test_leading_sector_classified_correctly(self):
        analyzer = SectorAnalyzer.__new__(SectorAnalyzer)
        assert analyzer._classify(75) == "leading"

    def test_neutral_sector_classified_correctly(self):
        analyzer = SectorAnalyzer.__new__(SectorAnalyzer)
        assert analyzer._classify(60) == "neutral"

    def test_lagging_sector_classified_correctly(self):
        analyzer = SectorAnalyzer.__new__(SectorAnalyzer)
        assert analyzer._classify(40) == "lagging"


class TestSectorScoring:
    def test_leading_sector_gives_bonus(self):
        analyzer = SectorAnalyzer.__new__(SectorAnalyzer)
        assert analyzer.confidence_adjustment("leading") == 5

    def test_neutral_sector_gives_zero(self):
        analyzer = SectorAnalyzer.__new__(SectorAnalyzer)
        assert analyzer.confidence_adjustment("neutral") == 0

    def test_lagging_sector_gives_penalty(self):
        analyzer = SectorAnalyzer.__new__(SectorAnalyzer)
        assert analyzer.confidence_adjustment("lagging") == -10


class TestSectorRSCalculation:
    def test_compute_rs_with_spy_data(self):
        """Sector outperforming SPY should have RS > 50."""
        dates = pd.date_range("2025-01-01", periods=260, freq="B")
        # Sector ETF rising faster than SPY
        sector_prices = pd.DataFrame(
            {"Close": np.linspace(100, 160, 260)}, index=dates
        )
        spy_prices = pd.DataFrame(
            {"Close": np.linspace(100, 120, 260)}, index=dates
        )
        analyzer = SectorAnalyzer.__new__(SectorAnalyzer)
        rs = analyzer._compute_rs(sector_prices, spy_prices)
        assert rs > 60  # clearly outperforming

    def test_compute_rs_underperforming(self):
        """Sector underperforming SPY should have RS < 50."""
        dates = pd.date_range("2025-01-01", periods=260, freq="B")
        sector_prices = pd.DataFrame(
            {"Close": np.linspace(100, 105, 260)}, index=dates
        )
        spy_prices = pd.DataFrame(
            {"Close": np.linspace(100, 140, 260)}, index=dates
        )
        analyzer = SectorAnalyzer.__new__(SectorAnalyzer)
        rs = analyzer._compute_rs(sector_prices, spy_prices)
        assert rs < 50  # clearly underperforming
