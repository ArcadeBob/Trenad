"""End-to-end smoke test: scan a few real tickers and verify output structure."""

import pytest
from pattern_scanner import StockScanner, PatternResult


@pytest.mark.integration
def test_scan_real_tickers():
    """Scan 3 real tickers and verify the pipeline works end-to-end.

    This test hits the network (yfinance). Skip in CI with: pytest -m "not integration"
    """
    scanner = StockScanner(tickers=["AAPL", "MSFT", "NVDA"], max_workers=3)
    results = scanner.scan()

    assert isinstance(results, list)
    for r in results:
        assert isinstance(r, PatternResult)
        assert r.confidence_score >= 0
        assert r.confidence_score <= 100
        assert r.rs_rating >= 0
        assert r.rs_rating <= 100
        assert r.current_price > 0
        assert r.buy_point > 0
        assert r.base_depth > 0
        assert r.base_length_weeks > 0
