"""Tests for StockScanner class using mocked yfinance data."""

from unittest.mock import patch, MagicMock
import pandas as pd
import numpy as np
from pattern_scanner import StockScanner, PatternResult


def _mock_yf_download(tickers, period, **kwargs):
    """Create mock price data that forms a flat base pattern."""
    dates = pd.bdate_range(end="2026-02-20", periods=500)
    if isinstance(tickers, str):
        tickers = [tickers]

    frames = {}
    for ticker in tickers:
        # Uptrend then flat consolidation
        uptrend = [100 + (50 * i / 400) for i in range(400)]
        flat = [150 + 3 * np.sin(i * 0.3) for i in range(100)]
        closes = uptrend + flat
        frames[ticker] = pd.DataFrame({
            "Open": closes,
            "High": [c * 1.01 for c in closes],
            "Low": [c * 0.99 for c in closes],
            "Close": closes,
            "Volume": [1_000_000] * 500,
        }, index=dates)

    if len(tickers) == 1:
        return frames[tickers[0]]
    return frames


def test_scanner_scan_returns_results():
    scanner = StockScanner(tickers=["AAPL", "MSFT"])
    with patch("pattern_scanner.yf") as mock_yf:
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = _mock_yf_download("AAPL", "2y")
        mock_yf.Ticker.return_value = mock_ticker

        # Also mock SPY
        spy_mock = MagicMock()
        spy_mock.history.return_value = _mock_yf_download("SPY", "2y")
        mock_yf.Ticker.side_effect = lambda t: spy_mock if t == "SPY" else mock_ticker

        results = scanner.scan()
        assert isinstance(results, list)
        for r in results:
            assert isinstance(r, PatternResult)


def test_scanner_progress_callback():
    scanner = StockScanner(tickers=["AAPL"])
    progress_calls = []

    def on_progress(current, total, ticker):
        progress_calls.append((current, total, ticker))

    with patch("pattern_scanner.yf") as mock_yf:
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = _mock_yf_download("AAPL", "2y")
        mock_yf.Ticker.return_value = mock_ticker

        scanner.scan(progress_callback=on_progress)
        assert len(progress_calls) > 0


def test_scanner_results_sorted_by_confidence():
    """Results should be sorted by confidence score descending."""
    scanner = StockScanner(tickers=["AAPL", "MSFT", "GOOGL"])

    with patch("pattern_scanner.yf") as mock_yf:
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = _mock_yf_download("AAPL", "2y")
        mock_yf.Ticker.return_value = mock_ticker

        results = scanner.scan()
        if len(results) >= 2:
            for i in range(len(results) - 1):
                assert results[i].confidence_score >= results[i + 1].confidence_score
