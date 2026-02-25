from ticker_lists import (
    DEFAULT_GROWTH_WATCHLIST,
    get_sp500_tickers,
    get_nasdaq100_tickers,
    SP500_FALLBACK,
    NASDAQ100_FALLBACK,
)


def test_default_watchlist_has_categories():
    assert len(DEFAULT_GROWTH_WATCHLIST) >= 80
    assert "AAPL" in DEFAULT_GROWTH_WATCHLIST
    assert "NVDA" in DEFAULT_GROWTH_WATCHLIST
    assert "LLY" in DEFAULT_GROWTH_WATCHLIST


def test_sp500_fallback_is_populated():
    assert len(SP500_FALLBACK) >= 400


def test_nasdaq100_fallback_is_populated():
    assert len(NASDAQ100_FALLBACK) >= 90


def test_get_sp500_tickers_returns_list():
    tickers = get_sp500_tickers()
    assert isinstance(tickers, list)
    assert len(tickers) >= 90
    assert all(isinstance(t, str) for t in tickers)


def test_get_nasdaq100_tickers_returns_list():
    tickers = get_nasdaq100_tickers()
    assert isinstance(tickers, list)
    assert len(tickers) >= 90
    assert all(isinstance(t, str) for t in tickers)
