"""Tests for the earnings analysis module."""

from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock
from datetime import date, timedelta

from earnings_analysis import EarningsAnalyzer


class TestEarningsProximity:
    def test_earnings_imminent_within_7_days(self):
        analyzer = EarningsAnalyzer.__new__(EarningsAnalyzer)
        next_date = (date.today() + timedelta(days=5)).isoformat()
        result = analyzer._classify_proximity(next_date)
        assert result["flag"] == "Earnings Imminent"
        assert result["days_until"] == 5

    def test_earnings_soon_within_14_days(self):
        analyzer = EarningsAnalyzer.__new__(EarningsAnalyzer)
        next_date = (date.today() + timedelta(days=10)).isoformat()
        result = analyzer._classify_proximity(next_date)
        assert result["flag"] == "Earnings Soon"
        assert result["days_until"] == 10

    def test_no_flag_beyond_14_days(self):
        analyzer = EarningsAnalyzer.__new__(EarningsAnalyzer)
        next_date = (date.today() + timedelta(days=30)).isoformat()
        result = analyzer._classify_proximity(next_date)
        assert result["flag"] is None
        assert result["days_until"] == 30

    def test_no_date_returns_none(self):
        analyzer = EarningsAnalyzer.__new__(EarningsAnalyzer)
        result = analyzer._classify_proximity(None)
        assert result["flag"] is None
        assert result["days_until"] is None


class TestEarningsMomentum:
    def test_strong_beat_single_quarter(self):
        analyzer = EarningsAnalyzer.__new__(EarningsAnalyzer)
        surprises = [{"surprise_pct": 20.0, "gap_up": False}]
        score = analyzer._calculate_momentum(surprises)
        assert score == 5  # 15%+ beat = 5 pts

    def test_moderate_beat_single_quarter(self):
        analyzer = EarningsAnalyzer.__new__(EarningsAnalyzer)
        surprises = [{"surprise_pct": 8.0, "gap_up": False}]
        score = analyzer._calculate_momentum(surprises)
        assert score == 3  # 5%+ beat = 3 pts

    def test_two_consecutive_beats_bonus(self):
        analyzer = EarningsAnalyzer.__new__(EarningsAnalyzer)
        surprises = [
            {"surprise_pct": 10.0, "gap_up": False},
            {"surprise_pct": 7.0, "gap_up": False},
        ]
        score = analyzer._calculate_momentum(surprises)
        assert score == 6  # 3 (beat) + 3 (consecutive bonus)

    def test_gap_up_bonus(self):
        analyzer = EarningsAnalyzer.__new__(EarningsAnalyzer)
        surprises = [{"surprise_pct": 20.0, "gap_up": True}]
        score = analyzer._calculate_momentum(surprises)
        assert score == 7  # 5 (strong beat) + 2 (gap up)

    def test_max_score_capped_at_10(self):
        analyzer = EarningsAnalyzer.__new__(EarningsAnalyzer)
        surprises = [
            {"surprise_pct": 25.0, "gap_up": True},
            {"surprise_pct": 18.0, "gap_up": False},
        ]
        score = analyzer._calculate_momentum(surprises)
        assert score == 10  # 5 + 3 + 2 = 10, capped

    def test_missed_earnings_zero_score(self):
        analyzer = EarningsAnalyzer.__new__(EarningsAnalyzer)
        surprises = [{"surprise_pct": -5.0, "gap_up": False}]
        score = analyzer._calculate_momentum(surprises)
        assert score == 0

    def test_empty_surprises_zero_score(self):
        analyzer = EarningsAnalyzer.__new__(EarningsAnalyzer)
        score = analyzer._calculate_momentum([])
        assert score == 0


class TestFMPIntegration:
    @patch("earnings_analysis.requests.get")
    def test_fetch_earnings_data_success(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = [
            {"date": "2026-03-15", "eps": 2.50, "epsEstimated": 2.30,
             "revenue": 1000000, "revenueEstimated": 950000}
        ]
        mock_get.return_value = mock_resp

        analyzer = EarningsAnalyzer(api_key="test_key")
        data = analyzer._fetch_from_fmp("AAPL")
        assert data is not None

    @patch("earnings_analysis.requests.get")
    def test_fetch_earnings_handles_api_failure(self, mock_get):
        mock_get.side_effect = Exception("API down")
        analyzer = EarningsAnalyzer(api_key="test_key")
        data = analyzer._fetch_from_fmp("AAPL")
        assert data is None

    @patch("earnings_analysis.requests.get")
    def test_analyze_returns_complete_result(self, mock_get):
        # Mock earnings calendar
        mock_resp_cal = MagicMock()
        mock_resp_cal.status_code = 200
        mock_resp_cal.json.return_value = [
            {"date": (date.today() + timedelta(days=10)).isoformat(),
             "symbol": "AAPL"}
        ]
        # Mock historical earnings
        mock_resp_hist = MagicMock()
        mock_resp_hist.status_code = 200
        mock_resp_hist.json.return_value = [
            {"date": "2026-01-15", "eps": 2.50, "epsEstimated": 2.20,
             "revenue": 1e9, "revenueEstimated": 9.5e8}
        ]
        mock_get.side_effect = [mock_resp_cal, mock_resp_hist]

        analyzer = EarningsAnalyzer(api_key="test_key")
        # Also need to mock stock data for gap-up detection
        import pandas as pd
        stock_df = pd.DataFrame(
            {"Close": [100, 104]},
            index=pd.to_datetime(["2026-01-14", "2026-01-15"]),
        )
        result = analyzer.analyze("AAPL", stock_df)
        assert "flag" in result
        assert "days_until" in result
        assert "momentum_score" in result
