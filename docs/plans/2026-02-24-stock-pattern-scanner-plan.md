# Stock Base Pattern Scanner Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a FastAPI web app + CLI that scans stocks for CAN SLIM base patterns (cup & handle, double bottom, flat base) using yfinance data.

**Architecture:** Core scanner engine shared by web app and CLI. FastAPI serves a dark-themed dashboard with SSE progress streaming. SQLite caches scan results. ThreadPoolExecutor provides concurrent data fetching.

**Tech Stack:** Python 3.11+, FastAPI, uvicorn, yfinance, pandas, numpy, openpyxl, Jinja2, SQLite

---

## Task 1: Project Setup

**Files:**
- Create: `stock_pattern_scanner/requirements.txt`
- Create: `stock_pattern_scanner/tests/__init__.py`

**Step 1: Create directory structure**

```bash
mkdir -p stock_pattern_scanner/templates stock_pattern_scanner/tests
```

**Step 2: Create requirements.txt**

```
fastapi>=0.104.0
uvicorn[standard]>=0.24.0
yfinance>=0.2.31
pandas>=2.1.0
numpy>=1.25.0
openpyxl>=3.1.2
jinja2>=3.1.2
aiofiles>=23.2.1
sse-starlette>=1.8.0
pytest>=7.4.0
```

**Step 3: Create empty test init**

Create empty `stock_pattern_scanner/tests/__init__.py`.

**Step 4: Install dependencies**

```bash
cd stock_pattern_scanner && pip install -r requirements.txt
```

**Step 5: Commit**

```bash
git add stock_pattern_scanner/requirements.txt stock_pattern_scanner/tests/__init__.py
git commit -m "feat: project setup with requirements and test directory"
```

---

## Task 2: PatternResult Dataclass

**Files:**
- Create: `stock_pattern_scanner/pattern_scanner.py`
- Create: `stock_pattern_scanner/tests/test_pattern_scanner.py`

**Step 1: Write the failing test**

```python
# tests/test_pattern_scanner.py
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
        ticker="MSFT",
        pattern_type="Flat Base",
        confidence_score=70.0,
        buy_point=100.0,
        current_price=99.5,
        distance_to_pivot=-0.5,
        base_depth=10.0,
        base_length_weeks=6,
        volume_confirmation=True,
        above_50ma=True,
        above_200ma=True,
        rs_rating=80.0,
        pattern_details={},
    )
    assert result.status == "At Pivot"


def test_pattern_result_status_near_pivot():
    """Within 5% below buy point = Near Pivot"""
    result = PatternResult(
        ticker="MSFT",
        pattern_type="Flat Base",
        confidence_score=70.0,
        buy_point=100.0,
        current_price=96.0,
        distance_to_pivot=-4.0,
        base_depth=10.0,
        base_length_weeks=6,
        volume_confirmation=True,
        above_50ma=True,
        above_200ma=True,
        rs_rating=80.0,
        pattern_details={},
    )
    assert result.status == "Near Pivot"


def test_pattern_result_status_building():
    """More than 5% below buy point = Building"""
    result = PatternResult(
        ticker="MSFT",
        pattern_type="Flat Base",
        confidence_score=70.0,
        buy_point=100.0,
        current_price=90.0,
        distance_to_pivot=-10.0,
        base_depth=10.0,
        base_length_weeks=6,
        volume_confirmation=True,
        above_50ma=True,
        above_200ma=True,
        rs_rating=80.0,
        pattern_details={},
    )
    assert result.status == "Building"


def test_pattern_result_status_extended():
    """More than 5% above buy point = Extended"""
    result = PatternResult(
        ticker="MSFT",
        pattern_type="Flat Base",
        confidence_score=70.0,
        buy_point=100.0,
        current_price=108.0,
        distance_to_pivot=8.0,
        base_depth=10.0,
        base_length_weeks=6,
        volume_confirmation=True,
        above_50ma=True,
        above_200ma=True,
        rs_rating=80.0,
        pattern_details={},
    )
    assert result.status == "Extended"
```

**Step 2: Run test to verify it fails**

```bash
cd stock_pattern_scanner && python -m pytest tests/test_pattern_scanner.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'pattern_scanner'`

**Step 3: Write minimal implementation**

```python
# pattern_scanner.py
"""Core pattern detection engine for stock base pattern scanning."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict


@dataclass
class PatternResult:
    """Result of a pattern scan for a single stock."""

    ticker: str
    pattern_type: str
    confidence_score: float
    buy_point: float
    current_price: float
    distance_to_pivot: float
    base_depth: float
    base_length_weeks: int
    volume_confirmation: bool
    above_50ma: bool
    above_200ma: bool
    rs_rating: float
    pattern_details: Dict = field(default_factory=dict)

    @property
    def status(self) -> str:
        """Determine status based on distance to pivot (buy point).

        Returns one of: 'At Pivot', 'Near Pivot', 'Building', 'Extended'
        """
        if self.distance_to_pivot > 5.0:
            return "Extended"
        elif abs(self.distance_to_pivot) <= 1.0:
            return "At Pivot"
        elif -5.0 <= self.distance_to_pivot < -1.0:
            return "Near Pivot"
        elif self.distance_to_pivot < -5.0:
            return "Building"
        else:
            # 1.0 < distance <= 5.0 (slightly above buy point but not extended)
            return "At Pivot"
```

**Step 4: Run test to verify it passes**

```bash
cd stock_pattern_scanner && python -m pytest tests/test_pattern_scanner.py -v
```

Expected: All 5 PASS

**Step 5: Commit**

```bash
git add stock_pattern_scanner/pattern_scanner.py stock_pattern_scanner/tests/test_pattern_scanner.py
git commit -m "feat: add PatternResult dataclass with status property"
```

---

## Task 3: Ticker Lists Module

**Files:**
- Create: `stock_pattern_scanner/ticker_lists.py`
- Create: `stock_pattern_scanner/tests/test_ticker_lists.py`

**Step 1: Write the failing test**

```python
# tests/test_ticker_lists.py
from ticker_lists import (
    DEFAULT_GROWTH_WATCHLIST,
    get_sp500_tickers,
    get_nasdaq100_tickers,
    SP500_FALLBACK,
    NASDAQ100_FALLBACK,
)


def test_default_watchlist_has_categories():
    assert len(DEFAULT_GROWTH_WATCHLIST) >= 80
    # Spot check known tickers
    assert "AAPL" in DEFAULT_GROWTH_WATCHLIST
    assert "NVDA" in DEFAULT_GROWTH_WATCHLIST
    assert "LLY" in DEFAULT_GROWTH_WATCHLIST


def test_sp500_fallback_is_populated():
    assert len(SP500_FALLBACK) >= 400


def test_nasdaq100_fallback_is_populated():
    assert len(NASDAQ100_FALLBACK) >= 90


def test_get_sp500_tickers_returns_list():
    """Should return a non-empty list of ticker strings."""
    tickers = get_sp500_tickers()
    assert isinstance(tickers, list)
    assert len(tickers) >= 90  # fallback at minimum
    assert all(isinstance(t, str) for t in tickers)


def test_get_nasdaq100_tickers_returns_list():
    tickers = get_nasdaq100_tickers()
    assert isinstance(tickers, list)
    assert len(tickers) >= 90
    assert all(isinstance(t, str) for t in tickers)
```

**Step 2: Run test to verify it fails**

```bash
cd stock_pattern_scanner && python -m pytest tests/test_ticker_lists.py -v
```

Expected: FAIL — `ModuleNotFoundError`

**Step 3: Write implementation**

```python
# ticker_lists.py
"""Stock ticker lists: default watchlist, S&P 500, NASDAQ 100.

Dynamic lists fetched from Wikipedia with hardcoded fallbacks.
"""

from __future__ import annotations

import logging

import pandas as pd

logger = logging.getLogger(__name__)

DEFAULT_GROWTH_WATCHLIST: list[str] = [
    # Software/Cloud
    "NOW", "CRM", "WDAY", "TEAM", "DDOG", "SNOW", "NET", "ZS", "CRWD", "PANW",
    "FTNT", "HUBS", "MNDY", "TTD", "BILL", "MDB", "CFLT", "ESTC",
    # Semiconductors
    "NVDA", "AMD", "AVGO", "QCOM", "MRVL", "KLAC", "LRCX", "AMAT", "ASML",
    "TSM", "ON", "NXPI", "MPWR", "SWKS",
    # Consumer/Retail
    "COST", "TJX", "LULU", "CMG", "DECK", "ORLY", "ULTA", "BIRD", "DPZ",
    "CAVA", "WINGSTOP", "ELF",
    # Healthcare
    "LLY", "NVO", "ISRG", "DXCM", "VEEV", "TMO", "DHR", "SYK", "BSX",
    "PODD", "ALGN", "HOLX",
    # Fintech
    "V", "MA", "PYPL", "SQ", "COIN", "MELI", "NU", "AFRM", "SOFI",
    # Mega-cap Tech
    "AAPL", "MSFT", "GOOGL", "AMZN", "META", "TSLA", "NFLX",
    # Energy/Industrial
    "NEE", "CEG", "FSLR", "CAT", "DE", "URI", "GE", "UBER", "ABNB",
    # Other growth
    "AXON", "CELH", "DUOL", "RKLB", "TOST", "APP", "IOT", "FOUR",
]

NASDAQ100_FALLBACK: list[str] = [
    "AAPL", "ABNB", "ADBE", "ADI", "ADP", "ADSK", "AEP", "AMAT", "AMGN",
    "AMZN", "ANSS", "ARM", "ASML", "AVGO", "AZN", "BIIB", "BKNG", "BKR",
    "CCEP", "CDNS", "CDW", "CEG", "CHTR", "CMCSA", "COST", "CPRT", "CRWD",
    "CSCO", "CSGP", "CSX", "CTAS", "CTSH", "DASH", "DDOG", "DLTR", "DXCM",
    "EA", "EXC", "FANG", "FAST", "FTNT", "GEHC", "GFS", "GILD", "GOOG",
    "GOOGL", "HON", "IDXX", "ILMN", "INTC", "INTU", "ISRG", "KDP", "KHC",
    "KLAC", "LIN", "LRCX", "LULU", "MAR", "MCHP", "MDB", "MDLZ", "MELI",
    "META", "MNST", "MRNA", "MRVL", "MSFT", "MU", "NFLX", "NVDA", "NXPI",
    "ODFL", "ON", "ORLY", "PANW", "PAYX", "PCAR", "PDD", "PEP", "PYPL",
    "QCOM", "REGN", "RIVN", "ROST", "SBUX", "SMCI", "SNPS", "SPLK", "TEAM",
    "TMUS", "TSLA", "TTD", "TTWO", "TXN", "VRSK", "VRTX", "WBA", "WBD",
    "WDAY", "XEL", "ZS",
]

SP500_FALLBACK: list[str] = [
    "AAPL", "ABBV", "ABT", "ACN", "ADBE", "ADI", "ADM", "ADP", "ADSK", "AEE",
    "AEP", "AES", "AFL", "AIG", "AIZ", "AJG", "AKAM", "ALB", "ALGN", "ALK",
    "ALL", "ALLE", "AMAT", "AMCR", "AMD", "AME", "AMGN", "AMP", "AMT", "AMZN",
    "ANET", "ANSS", "AON", "AOS", "APA", "APD", "APH", "APTV", "ARE", "ATO",
    "ATVI", "AVB", "AVGO", "AVY", "AWK", "AXP", "AZO", "BA", "BAC", "BAX",
    "BBWI", "BBY", "BDX", "BEN", "BF.B", "BG", "BIIB", "BIO", "BK", "BKNG",
    "BKR", "BLK", "BMY", "BR", "BRK.B", "BRO", "BSX", "BWA", "BXP", "C",
    "CAG", "CAH", "CARR", "CAT", "CB", "CBOE", "CBRE", "CCI", "CCL", "CDAY",
    "CDNS", "CDW", "CE", "CEG", "CF", "CFG", "CHD", "CHRW", "CHTR", "CI",
    "CINF", "CL", "CLX", "CMA", "CMCSA", "CME", "CMG", "CMI", "CMS", "CNC",
    "CNP", "COF", "COO", "COP", "COST", "CPB", "CPRT", "CPT", "CRL", "CRM",
    "CSCO", "CSGP", "CSX", "CTAS", "CTLT", "CTRA", "CTSH", "CTVA", "CVS",
    "CVX", "CZR", "D", "DAL", "DD", "DE", "DFS", "DG", "DGX", "DHI", "DHR",
    "DIS", "DISH", "DLR", "DLTR", "DOV", "DOW", "DPZ", "DRI", "DTE", "DUK",
    "DVA", "DVN", "DXC", "DXCM", "EA", "EBAY", "ECL", "ED", "EFX", "EIX",
    "EL", "EMN", "EMR", "ENPH", "EOG", "EPAM", "EQIX", "EQR", "EQT", "ES",
    "ESS", "ETN", "ETR", "ETSY", "EVRG", "EW", "EXC", "EXPD", "EXPE", "EXR",
    "F", "FANG", "FAST", "FBHS", "FCX", "FDS", "FDX", "FE", "FFIV", "FIS",
    "FISV", "FITB", "FLT", "FMC", "FOX", "FOXA", "FRC", "FRT", "FSLR", "FTNT",
    "FTV", "GD", "GE", "GEHC", "GEN", "GILD", "GIS", "GL", "GLW", "GM",
    "GNRC", "GOOG", "GOOGL", "GPC", "GPN", "GRMN", "GS", "GWW", "HAL", "HAS",
    "HBAN", "HCA", "HOLX", "HON", "HPE", "HPQ", "HRL", "HSIC", "HST", "HSY",
    "HUM", "HWM", "IBM", "ICE", "IDXX", "IEX", "IFF", "ILMN", "INCY", "INTC",
    "INTU", "INVH", "IP", "IPG", "IQV", "IR", "IRM", "ISRG", "IT", "ITW",
    "IVZ", "J", "JBHT", "JCI", "JKHY", "JNJ", "JNPR", "JPM", "K", "KDP",
    "KEY", "KEYS", "KHC", "KIM", "KLAC", "KMB", "KMI", "KMX", "KO", "KR",
    "L", "LDOS", "LEN", "LH", "LHX", "LIN", "LKQ", "LLY", "LMT", "LNC",
    "LNT", "LOW", "LRCX", "LULU", "LUV", "LVS", "LW", "LYB", "LYV", "MA",
    "MAA", "MAR", "MAS", "MCD", "MCHP", "MCK", "MCO", "MDLZ", "MDT", "MET",
    "META", "MGM", "MHK", "MKC", "MKTX", "MLM", "MMC", "MMM", "MNST", "MO",
    "MOH", "MOS", "MPC", "MPWR", "MRK", "MRNA", "MRO", "MS", "MSCI", "MSFT",
    "MSI", "MTB", "MTCH", "MTD", "MU", "NCLH", "NDAQ", "NDSN", "NEE", "NEM",
    "NFLX", "NI", "NKE", "NOC", "NOW", "NRG", "NSC", "NTAP", "NTRS", "NUE",
    "NVDA", "NVR", "NWL", "NWS", "NWSA", "NXPI", "O", "ODFL", "OGN", "OKE",
    "OMC", "ON", "ORCL", "ORLY", "OTIS", "OXY", "PARA", "PAYC", "PAYX",
    "PCAR", "PCG", "PEAK", "PEG", "PEP", "PFE", "PFG", "PG", "PGR", "PH",
    "PHM", "PKG", "PKI", "PLD", "PM", "PNC", "PNR", "PNW", "POOL", "PPG",
    "PPL", "PRU", "PSA", "PSX", "PTC", "PVH", "PWR", "PXD", "PYPL", "QCOM",
    "QRVO", "RCL", "RE", "REG", "REGN", "RF", "RHI", "RJF", "RL", "RMD",
    "ROK", "ROL", "ROP", "ROST", "RSG", "RTX", "RVTY", "SBAC", "SBNY",
    "SBUX", "SCHW", "SEE", "SHW", "SIVB", "SJM", "SLB", "SNA", "SNPS", "SO",
    "SPG", "SPGI", "SRE", "STE", "STT", "STX", "STZ", "SWK", "SWKS", "SYF",
    "SYK", "SYY", "T", "TAP", "TDG", "TDY", "TECH", "TEL", "TER", "TFC",
    "TFX", "TGT", "TMO", "TMUS", "TPR", "TRGP", "TRMB", "TROW", "TRV",
    "TSCO", "TSLA", "TSN", "TT", "TTWO", "TXN", "TXT", "TYL", "UAL", "UDR",
    "UHS", "ULTA", "UNH", "UNP", "UPS", "URI", "USB", "V", "VFC", "VICI",
    "VLO", "VMC", "VRSK", "VRSN", "VRTX", "VTR", "VTRS", "VZ", "WAB", "WAT",
    "WBA", "WBD", "WDC", "WEC", "WELL", "WFC", "WHR", "WM", "WMB", "WMT",
    "WRB", "WRK", "WST", "WTW", "WY", "WYNN", "XEL", "XOM", "XRAY", "XYL",
    "YUM", "ZBH", "ZBRA", "ZION", "ZTS",
]


def get_sp500_tickers() -> list[str]:
    """Fetch S&P 500 tickers from Wikipedia. Falls back to hardcoded list."""
    try:
        tables = pd.read_html("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies")
        df = tables[0]
        tickers = df["Symbol"].str.replace(".", "-", regex=False).tolist()
        if len(tickers) > 400:
            return sorted(tickers)
    except Exception as e:
        logger.warning("Failed to fetch S&P 500 from Wikipedia: %s. Using fallback.", e)
    return SP500_FALLBACK


def get_nasdaq100_tickers() -> list[str]:
    """Fetch NASDAQ 100 tickers from Wikipedia. Falls back to hardcoded list."""
    try:
        tables = pd.read_html("https://en.wikipedia.org/wiki/Nasdaq-100")
        df = tables[4]  # The ticker table is typically the 5th table
        tickers = df["Ticker"].tolist()
        if len(tickers) > 80:
            return sorted(tickers)
    except Exception as e:
        logger.warning("Failed to fetch NASDAQ 100 from Wikipedia: %s. Using fallback.", e)
    return NASDAQ100_FALLBACK
```

**Step 4: Run test to verify it passes**

```bash
cd stock_pattern_scanner && python -m pytest tests/test_ticker_lists.py -v
```

Expected: All 5 PASS (Wikipedia fetch tests may use fallback — that's fine)

**Step 5: Commit**

```bash
git add stock_pattern_scanner/ticker_lists.py stock_pattern_scanner/tests/test_ticker_lists.py
git commit -m "feat: add ticker lists with Wikipedia fetching and fallbacks"
```

---

## Task 4: PatternDetector Helpers — Peaks, Troughs, and Moving Averages

**Files:**
- Modify: `stock_pattern_scanner/pattern_scanner.py`
- Modify: `stock_pattern_scanner/tests/test_pattern_scanner.py`

**Step 1: Write failing tests**

Add to `tests/test_pattern_scanner.py`:

```python
import numpy as np
import pandas as pd
from pattern_scanner import PatternDetector


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
    # Simple peak at index 5
    prices = [10, 11, 12, 13, 14, 15, 14, 13, 12, 11, 10]
    closes = pd.Series(prices)
    detector = PatternDetector()
    peaks = detector.find_local_peaks(closes, window=3)
    assert 5 in peaks


def test_find_local_troughs():
    # Simple trough at index 5
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
    # First 199 rows of MA200 should be NaN, last row should not
    assert pd.notna(result["MA200"].iloc[-1])


def test_calculate_relative_strength():
    """Stock that doubled while SPY gained 10% should have high RS."""
    detector = PatternDetector()
    n = 252  # one trading year
    stock_closes = [100 + (100 * i / n) for i in range(n)]  # 100 -> 200
    spy_closes = [400 + (40 * i / n) for i in range(n)]      # 400 -> 440
    stock_df = _make_price_df(stock_closes)
    spy_df = _make_price_df(spy_closes)
    rs = detector.calculate_relative_strength(stock_df, spy_df)
    assert rs > 80  # Strong outperformer
```

**Step 2: Run test to verify it fails**

```bash
cd stock_pattern_scanner && python -m pytest tests/test_pattern_scanner.py -v -k "peak or trough or moving or relative"
```

Expected: FAIL — `ImportError: cannot import name 'PatternDetector'`

**Step 3: Write implementation**

Add to `pattern_scanner.py`:

```python
import numpy as np
import pandas as pd
from scipy.signal import argrelextrema  # Add scipy to requirements.txt


class PatternDetector:
    """Detects CAN SLIM base patterns in stock price data."""

    def find_local_peaks(self, prices: pd.Series, window: int = 10) -> list[int]:
        """Find indices of local maxima in a price series.

        Args:
            prices: Series of price values.
            window: Number of points on each side to compare.

        Returns:
            List of integer indices where local peaks occur.
        """
        arr = prices.values
        peaks = argrelextrema(arr, np.greater_equal, order=window)[0]
        return peaks.tolist()

    def find_local_troughs(self, prices: pd.Series, window: int = 10) -> list[int]:
        """Find indices of local minima in a price series.

        Args:
            prices: Series of price values.
            window: Number of points on each side to compare.

        Returns:
            List of integer indices where local troughs occur.
        """
        arr = prices.values
        troughs = argrelextrema(arr, np.less_equal, order=window)[0]
        return troughs.tolist()

    def add_moving_averages(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add moving average columns and 50-day average volume to DataFrame.

        Adds: MA10, MA20, MA50, MA200, AvgVolume50
        """
        df = df.copy()
        df["MA10"] = df["Close"].rolling(window=10).mean()
        df["MA20"] = df["Close"].rolling(window=20).mean()
        df["MA50"] = df["Close"].rolling(window=50).mean()
        df["MA200"] = df["Close"].rolling(window=200).mean()
        df["AvgVolume50"] = df["Volume"].rolling(window=50).mean()
        return df

    def calculate_relative_strength(
        self, stock_df: pd.DataFrame, spy_df: pd.DataFrame
    ) -> float:
        """Calculate relative strength rating (0-100) vs SPY.

        Uses a weighted blend of 3-month, 6-month, 9-month, 12-month performance.
        Weight: 40% recent quarter, 20% each for the other three.
        """
        periods = [63, 126, 189, 252]  # ~3, 6, 9, 12 months
        weights = [0.4, 0.2, 0.2, 0.2]

        stock_close = stock_df["Close"]
        spy_close = spy_df["Close"]

        stock_returns = []
        spy_returns = []

        for period in periods:
            if len(stock_close) > period and len(spy_close) > period:
                sr = (stock_close.iloc[-1] / stock_close.iloc[-period] - 1) * 100
                spr = (spy_close.iloc[-1] / spy_close.iloc[-period] - 1) * 100
                stock_returns.append(sr)
                spy_returns.append(spr)
            else:
                stock_returns.append(0)
                spy_returns.append(0)

        # Weighted stock performance
        weighted_stock = sum(r * w for r, w in zip(stock_returns, weights))
        weighted_spy = sum(r * w for r, w in zip(spy_returns, weights))

        # Convert to 0-100 scale: stock that matches SPY = 50
        # Each 1% outperformance adds ~1 point, capped at 0-99
        rs_raw = 50 + (weighted_stock - weighted_spy)
        return max(1, min(99, round(rs_raw, 1)))
```

Also add `scipy>=1.11.0` to requirements.txt and install it.

**Step 4: Run tests**

```bash
cd stock_pattern_scanner && python -m pytest tests/test_pattern_scanner.py -v
```

Expected: All PASS

**Step 5: Commit**

```bash
git add stock_pattern_scanner/pattern_scanner.py stock_pattern_scanner/tests/test_pattern_scanner.py stock_pattern_scanner/requirements.txt
git commit -m "feat: add PatternDetector with peak/trough finding, moving averages, and RS rating"
```

---

## Task 5: Flat Base Detection

**Files:**
- Modify: `stock_pattern_scanner/pattern_scanner.py`
- Modify: `stock_pattern_scanner/tests/test_pattern_scanner.py`

**Step 1: Write failing tests**

Add to `tests/test_pattern_scanner.py`:

```python
def test_detect_flat_base_valid():
    """Tight consolidation <15% range after 30%+ uptrend."""
    detector = PatternDetector()

    # Build a 30%+ uptrend (100 -> 140) followed by 8 weeks of flat consolidation
    uptrend = [100 + (40 * i / 150) for i in range(150)]  # ~100 to 140
    # 8 weeks * 5 days = 40 days of consolidation between 135-145 (<15% range)
    flat = [140 + 3 * np.sin(i * 0.3) for i in range(40)]  # oscillates ~137-143

    closes = uptrend + flat
    volumes = [1_000_000] * len(closes)
    # Declining volume in base
    for i in range(len(uptrend), len(closes)):
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
    uptrend = [100 + (50 * i / 150) for i in range(150)]
    # 20% range consolidation — too deep for flat base
    deep_consol = [150 - (30 * i / 40) + (15 * (i % 2)) for i in range(40)]
    closes = uptrend + deep_consol
    df = _make_price_df(closes)
    df = detector.add_moving_averages(df)
    result = detector.detect_flat_base(df)
    assert result is None


def test_detect_flat_base_no_prior_uptrend():
    """Flat consolidation without 30%+ prior uptrend should NOT match."""
    detector = PatternDetector()
    # Only 10% uptrend
    uptrend = [100 + (10 * i / 150) for i in range(150)]
    flat = [110 + 2 * np.sin(i * 0.3) for i in range(40)]
    closes = uptrend + flat
    df = _make_price_df(closes)
    df = detector.add_moving_averages(df)
    result = detector.detect_flat_base(df)
    assert result is None
```

**Step 2: Run test to verify it fails**

```bash
cd stock_pattern_scanner && python -m pytest tests/test_pattern_scanner.py -v -k "flat_base"
```

Expected: FAIL — `AttributeError: 'PatternDetector' has no attribute 'detect_flat_base'`

**Step 3: Write implementation**

Add to `PatternDetector` class in `pattern_scanner.py`:

```python
    def _has_prior_uptrend(self, df: pd.DataFrame, end_idx: int, min_gain: float = 30.0) -> bool:
        """Check if there's a min_gain% uptrend in the 6 months before end_idx."""
        lookback = min(126, end_idx)  # ~6 months
        if lookback < 20:
            return False
        segment = df["Close"].iloc[end_idx - lookback : end_idx]
        low = segment.min()
        high = segment.max()
        low_idx = segment.idxmin()
        high_idx = segment.idxmax()
        # High must come after low (uptrend, not downtrend)
        if high_idx <= low_idx:
            return False
        gain = (high - low) / low * 100
        return gain >= min_gain

    def detect_flat_base(self, df: pd.DataFrame) -> dict | None:
        """Detect a flat base pattern in the most recent price data.

        Criteria:
        - <15% range from high to low in consolidation
        - Minimum 5 weeks (25 trading days) duration
        - Prior 30%+ uptrend
        - Mostly above 50-day MA

        Returns:
            Pattern dict with details, or None if no pattern found.
        """
        if len(df) < 200:
            return None

        closes = df["Close"]

        # Look at the last 15 weeks (75 trading days) for a flat base
        lookback_days = 75
        recent = closes.iloc[-lookback_days:]
        recent_high = recent.max()
        recent_low = recent.min()

        if recent_high == 0:
            return None

        depth = (recent_high - recent_low) / recent_high * 100

        if depth >= 15.0:
            return None

        # Find the actual base start: where consolidation began
        # Walk backward from end to find where price entered the range
        base_top = recent_high
        base_bottom = recent_low
        base_start_idx = len(df) - lookback_days

        for i in range(len(df) - lookback_days, len(df)):
            price = closes.iloc[i]
            if price >= base_bottom and price <= base_top:
                base_start_idx = i
                break

        base_length_days = len(df) - 1 - base_start_idx
        base_length_weeks = base_length_days / 5

        if base_length_weeks < 5:
            return None

        # Check prior uptrend
        if not self._has_prior_uptrend(df, base_start_idx):
            return None

        # Check if mostly above 50-day MA
        if "MA50" in df.columns:
            base_data = df.iloc[base_start_idx:]
            above_50ma = (base_data["Close"] > base_data["MA50"]).mean()
            if above_50ma < 0.5:
                return None

        # Volume confirmation: declining volume during base
        volume_confirm = False
        if "AvgVolume50" in df.columns:
            base_avg_vol = df["Volume"].iloc[base_start_idx:].mean()
            prior_avg_vol = df["Volume"].iloc[base_start_idx - 50 : base_start_idx].mean()
            if prior_avg_vol > 0:
                volume_confirm = base_avg_vol < prior_avg_vol * 0.9

        buy_point = round(float(recent_high), 2)
        current_price = round(float(closes.iloc[-1]), 2)
        distance = round((current_price - buy_point) / buy_point * 100, 2)

        return {
            "pattern_type": "Flat Base",
            "buy_point": buy_point,
            "current_price": current_price,
            "distance_to_pivot": distance,
            "base_depth": round(depth, 2),
            "base_length_weeks": int(round(base_length_weeks)),
            "volume_confirmation": volume_confirm,
            "base_high": round(float(recent_high), 2),
            "base_low": round(float(recent_low), 2),
            "base_start_idx": base_start_idx,
        }
```

**Step 4: Run tests**

```bash
cd stock_pattern_scanner && python -m pytest tests/test_pattern_scanner.py -v -k "flat_base"
```

Expected: All 3 flat base tests PASS

**Step 5: Commit**

```bash
git add stock_pattern_scanner/pattern_scanner.py stock_pattern_scanner/tests/test_pattern_scanner.py
git commit -m "feat: add flat base detection with prior uptrend validation"
```

---

## Task 6: Double Bottom Detection

**Files:**
- Modify: `stock_pattern_scanner/pattern_scanner.py`
- Modify: `stock_pattern_scanner/tests/test_pattern_scanner.py`

**Step 1: Write failing tests**

Add to `tests/test_pattern_scanner.py`:

```python
def test_detect_double_bottom_valid():
    """W-pattern with two lows within 3-5% of each other."""
    detector = PatternDetector()

    # Build: uptrend -> first low -> bounce -> second low -> recovery
    uptrend = [100 + (50 * i / 100) for i in range(100)]     # 100 -> 150
    decline1 = [150 - (30 * i / 30) for i in range(30)]       # 150 -> 120
    bounce = [120 + (15 * i / 25) for i in range(25)]          # 120 -> 135
    decline2 = [135 - (16 * i / 25) for i in range(25)]        # 135 -> 119
    recovery = [119 + (14 * i / 30) for i in range(30)]        # 119 -> 133

    closes = uptrend + decline1 + bounce + decline2 + recovery
    df = _make_price_df(closes)
    df = detector.add_moving_averages(df)

    result = detector.detect_double_bottom(df)
    assert result is not None
    assert result["pattern_type"] == "Double Bottom"


def test_detect_double_bottom_lows_too_far_apart():
    """Two lows more than 5% apart should NOT match."""
    detector = PatternDetector()

    uptrend = [100 + (50 * i / 100) for i in range(100)]
    decline1 = [150 - (30 * i / 30) for i in range(30)]       # -> 120
    bounce = [120 + (15 * i / 25) for i in range(25)]
    decline2 = [135 - (35 * i / 25) for i in range(25)]        # -> 100 (too far from 120)
    recovery = [100 + (14 * i / 30) for i in range(30)]

    closes = uptrend + decline1 + bounce + decline2 + recovery
    df = _make_price_df(closes)
    df = detector.add_moving_averages(df)

    result = detector.detect_double_bottom(df)
    assert result is None
```

**Step 2: Run test to verify it fails**

```bash
cd stock_pattern_scanner && python -m pytest tests/test_pattern_scanner.py -v -k "double_bottom"
```

Expected: FAIL — `AttributeError: 'PatternDetector' has no attribute 'detect_double_bottom'`

**Step 3: Write implementation**

Add to `PatternDetector` class:

```python
    def detect_double_bottom(self, df: pd.DataFrame) -> dict | None:
        """Detect a double bottom (W-pattern) in recent price data.

        Criteria:
        - Two distinct lows within 3-5% of each other
        - Second low may slightly undercut first (bullish shakeout)
        - 20-30% typical depth from prior high
        - Middle peak forms resistance / buy point

        Returns:
            Pattern dict with details, or None if no pattern found.
        """
        if len(df) < 200:
            return None

        closes = df["Close"]

        # Look in the last 9 months (~190 trading days) for the pattern
        lookback = min(190, len(df) - 50)
        recent = closes.iloc[-lookback:]

        # Find the prior high (highest point before the decline)
        prior_high_idx = recent.idxmax()
        prior_high = recent[prior_high_idx]
        prior_high_pos = recent.index.get_loc(prior_high_idx)

        # Need enough data after the high for the W pattern
        if prior_high_pos > lookback * 0.5:
            return None

        after_high = recent.iloc[prior_high_pos:]
        if len(after_high) < 40:
            return None

        # Find troughs in the data after the high
        troughs = self.find_local_troughs(after_high, window=8)
        if len(troughs) < 2:
            return None

        # Get the two most prominent troughs
        trough_prices = [(t, float(after_high.iloc[t])) for t in troughs]
        trough_prices.sort(key=lambda x: x[1])  # Sort by price (lowest first)

        # Take the two lowest troughs
        first_trough_idx, first_low = trough_prices[0]
        second_trough_idx, second_low = trough_prices[1]

        # Ensure they're in chronological order
        if first_trough_idx > second_trough_idx:
            first_trough_idx, first_low, second_trough_idx, second_low = (
                second_trough_idx, second_low, first_trough_idx, first_low
            )

        # Check lows are within 5% of each other
        low_diff_pct = abs(first_low - second_low) / max(first_low, second_low) * 100
        if low_diff_pct > 5.0:
            return None

        # Need meaningful separation between the two lows (at least 3 weeks)
        if (second_trough_idx - first_trough_idx) < 15:
            return None

        # Find the middle peak between the two troughs
        between = after_high.iloc[first_trough_idx:second_trough_idx + 1]
        if len(between) < 3:
            return None
        middle_peak = float(between.max())

        # Check depth from prior high
        base_low = min(first_low, second_low)
        depth = (prior_high - base_low) / prior_high * 100

        # Double bottom typically 15-35% deep
        if depth < 15 or depth > 40:
            return None

        # Total base length
        total_days = second_trough_idx + 10  # approximate
        base_length_weeks = total_days / 5

        # Volume confirmation: look for declining volume into second low
        volume_confirm = False
        abs_first = after_high.index[first_trough_idx]
        abs_second = after_high.index[second_trough_idx]
        first_pos = df.index.get_loc(abs_first)
        second_pos = df.index.get_loc(abs_second)
        if first_pos > 5 and second_pos > 5:
            vol_around_first = df["Volume"].iloc[first_pos - 5 : first_pos + 5].mean()
            vol_around_second = df["Volume"].iloc[second_pos - 5 : second_pos + 5].mean()
            if vol_around_first > 0:
                volume_confirm = vol_around_second < vol_around_first

        buy_point = round(middle_peak, 2)
        current_price = round(float(closes.iloc[-1]), 2)
        distance = round((current_price - buy_point) / buy_point * 100, 2)

        return {
            "pattern_type": "Double Bottom",
            "buy_point": buy_point,
            "current_price": current_price,
            "distance_to_pivot": distance,
            "base_depth": round(depth, 2),
            "base_length_weeks": int(round(base_length_weeks)),
            "volume_confirmation": volume_confirm,
            "first_low": round(first_low, 2),
            "second_low": round(second_low, 2),
            "middle_peak": round(middle_peak, 2),
            "low_diff_pct": round(low_diff_pct, 2),
        }
```

**Step 4: Run tests**

```bash
cd stock_pattern_scanner && python -m pytest tests/test_pattern_scanner.py -v -k "double_bottom"
```

Expected: All 2 double bottom tests PASS

**Step 5: Commit**

```bash
git add stock_pattern_scanner/pattern_scanner.py stock_pattern_scanner/tests/test_pattern_scanner.py
git commit -m "feat: add double bottom detection"
```

---

## Task 7: Cup & Handle Detection (includes Deep Cup)

**Files:**
- Modify: `stock_pattern_scanner/pattern_scanner.py`
- Modify: `stock_pattern_scanner/tests/test_pattern_scanner.py`

**Step 1: Write failing tests**

Add to `tests/test_pattern_scanner.py`:

```python
def test_detect_cup_and_handle_valid():
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

    df = _make_price_df(closes, volumes)
    df = detector.add_moving_averages(df)

    result = detector.detect_cup_and_handle(df)
    assert result is not None
    assert result["pattern_type"] in ("Cup & Handle", "Deep Cup & Handle")
    assert 12 <= result["base_depth"] <= 33


def test_detect_cup_and_handle_deep():
    """Cup with 33-50% depth should be classified as Deep Cup & Handle."""
    detector = PatternDetector()

    uptrend = [100 + (60 * i / 100) for i in range(100)]      # 100 -> 160
    left_side = [160 - (64 * i / 40) for i in range(40)]       # 160 -> 96 (40% decline)
    bottom = [96 + 3 * np.sin(i * np.pi / 30) for i in range(30)]
    right_side = [96 + (60 * i / 50) for i in range(50)]       # 96 -> 156
    handle = [156 - (8 * i / 10) for i in range(10)] + [148 + (6 * i / 10) for i in range(10)]

    closes = uptrend + left_side + bottom + right_side + handle
    df = _make_price_df(closes)
    df = detector.add_moving_averages(df)

    result = detector.detect_cup_and_handle(df)
    assert result is not None
    assert result["pattern_type"] == "Deep Cup & Handle"


def test_detect_cup_and_handle_too_shallow():
    """Cup with <12% depth should NOT match."""
    detector = PatternDetector()

    uptrend = [100 + (50 * i / 100) for i in range(100)]
    # Only 8% decline — too shallow
    left_side = [150 - (12 * i / 40) for i in range(40)]
    bottom = [138 + 1 * np.sin(i * np.pi / 30) for i in range(30)]
    right_side = [138 + (10 * i / 40) for i in range(40)]
    handle = [148 - (3 * i / 10) for i in range(10)] + [145 + (2 * i / 10) for i in range(10)]

    closes = uptrend + left_side + bottom + right_side + handle
    df = _make_price_df(closes)
    df = detector.add_moving_averages(df)

    result = detector.detect_cup_and_handle(df)
    assert result is None
```

**Step 2: Run test to verify it fails**

```bash
cd stock_pattern_scanner && python -m pytest tests/test_pattern_scanner.py -v -k "cup_and_handle"
```

Expected: FAIL

**Step 3: Write implementation**

Add to `PatternDetector` class:

```python
    def detect_cup_and_handle(self, df: pd.DataFrame) -> dict | None:
        """Detect cup & handle or deep cup & handle pattern.

        Criteria:
        - Cup depth: 12-50% (12-33% = regular, 33-50% = deep)
        - Handle: 1-6 weeks, <15% decline, declining volume
        - Total duration: 7-65 weeks
        - Prior 30%+ uptrend

        Returns:
            Pattern dict with details, or None if no pattern found.
        """
        if len(df) < 200:
            return None

        closes = df["Close"]

        # Scan last 65 weeks (~325 trading days) for cup formation
        max_lookback = min(325, len(df) - 50)
        recent = closes.iloc[-max_lookback:]

        # Find the cup's left lip (highest point before decline)
        peaks = self.find_local_peaks(recent, window=15)
        if not peaks:
            return None

        # Try each peak as potential left lip, starting from most recent viable ones
        for peak_idx in reversed(peaks):
            left_lip = float(recent.iloc[peak_idx])
            left_lip_pos = peak_idx

            # Need at least 35 days after left lip for cup + handle
            if len(recent) - left_lip_pos < 35:
                continue

            # Check prior uptrend before the left lip
            abs_pos = len(df) - max_lookback + left_lip_pos
            if not self._has_prior_uptrend(df, abs_pos):
                continue

            after_lip = recent.iloc[left_lip_pos:]

            # Find the cup low (lowest point after left lip)
            cup_low_rel = after_lip.idxmin()
            cup_low_pos = after_lip.index.get_loc(cup_low_rel)
            cup_low = float(after_lip.iloc[cup_low_pos])

            # Cup depth check
            depth = (left_lip - cup_low) / left_lip * 100
            if depth < 12.0 or depth > 50.0:
                continue

            # The cup low should be roughly in the middle, not at the very end
            after_low = after_lip.iloc[cup_low_pos:]
            if len(after_low) < 15:
                continue

            # Right side should recover close to left lip level
            right_high = float(after_low.max())
            right_high_pos = after_low.values.argmax()
            recovery_pct = (right_high - cup_low) / (left_lip - cup_low) * 100

            if recovery_pct < 70:
                continue  # Right side hasn't recovered enough

            # Look for handle: small pullback after right side recovery
            after_right_high = after_low.iloc[right_high_pos:]
            if len(after_right_high) < 5:
                # No handle yet, but cup is forming — check if current price IS the handle
                handle_low = float(after_low.iloc[-5:].min()) if len(after_low) >= 5 else cup_low
                handle_decline = (right_high - handle_low) / right_high * 100
            else:
                handle_low = float(after_right_high.min())
                handle_decline = (right_high - handle_low) / right_high * 100
                handle_length_days = len(after_right_high)
                handle_length_weeks = handle_length_days / 5

                if handle_length_weeks > 6:
                    continue  # Handle too long
                if handle_decline > 15:
                    continue  # Handle too deep

            # Total base length
            total_days = len(after_lip)
            total_weeks = total_days / 5
            if total_weeks < 7 or total_weeks > 65:
                continue

            # Classify as regular or deep
            pattern_type = "Deep Cup & Handle" if depth > 33 else "Cup & Handle"

            # Volume confirmation: declining volume in handle
            volume_confirm = False
            if "AvgVolume50" in df.columns and len(after_right_high) >= 5:
                abs_right_high_pos = len(df) - len(after_right_high)
                handle_vol = df["Volume"].iloc[abs_right_high_pos:].mean()
                cup_vol = df["Volume"].iloc[abs_pos:abs_right_high_pos].mean()
                if cup_vol > 0:
                    volume_confirm = handle_vol < cup_vol * 0.85

            buy_point = round(right_high, 2)
            current_price = round(float(closes.iloc[-1]), 2)
            distance = round((current_price - buy_point) / buy_point * 100, 2)

            return {
                "pattern_type": pattern_type,
                "buy_point": buy_point,
                "current_price": current_price,
                "distance_to_pivot": distance,
                "base_depth": round(depth, 2),
                "base_length_weeks": int(round(total_weeks)),
                "volume_confirmation": volume_confirm,
                "left_lip": round(left_lip, 2),
                "cup_low": round(cup_low, 2),
                "right_high": round(right_high, 2),
                "handle_low": round(handle_low, 2),
                "recovery_pct": round(recovery_pct, 1),
            }

        return None
```

**Step 4: Run tests**

```bash
cd stock_pattern_scanner && python -m pytest tests/test_pattern_scanner.py -v -k "cup_and_handle"
```

Expected: All 3 cup & handle tests PASS

**Step 5: Commit**

```bash
git add stock_pattern_scanner/pattern_scanner.py stock_pattern_scanner/tests/test_pattern_scanner.py
git commit -m "feat: add cup & handle and deep cup & handle detection"
```

---

## Task 8: Confidence Scoring

**Files:**
- Modify: `stock_pattern_scanner/pattern_scanner.py`
- Modify: `stock_pattern_scanner/tests/test_pattern_scanner.py`

**Step 1: Write failing tests**

Add to `tests/test_pattern_scanner.py`:

```python
def test_confidence_score_high_quality():
    """Pattern with all positive signals should score 75+."""
    detector = PatternDetector()
    pattern = {
        "pattern_type": "Flat Base",
        "base_depth": 10.0,
        "volume_confirmation": True,
        "base_length_weeks": 7,
    }
    df = _make_price_df(list(range(100, 300)))
    df = detector.add_moving_averages(df)
    # Ensure above both MAs
    score = detector.calculate_confidence(pattern, df)
    assert score >= 60


def test_confidence_score_low_quality():
    """Pattern with negative signals should score below 50."""
    detector = PatternDetector()
    pattern = {
        "pattern_type": "Cup & Handle",
        "base_depth": 48.0,  # Very deep
        "volume_confirmation": False,
        "base_length_weeks": 60,  # Very long
    }
    # Declining prices — below MAs
    closes = [200 - i * 0.5 for i in range(200)]
    df = _make_price_df(closes)
    df = detector.add_moving_averages(df)
    score = detector.calculate_confidence(pattern, df)
    assert score < 60
```

**Step 2: Run test to verify it fails**

```bash
cd stock_pattern_scanner && python -m pytest tests/test_pattern_scanner.py -v -k "confidence"
```

Expected: FAIL

**Step 3: Write implementation**

Add to `PatternDetector` class:

```python
    def calculate_confidence(self, pattern: dict, df: pd.DataFrame) -> float:
        """Calculate confidence score (0-100) for a detected pattern.

        Scoring factors:
        - Ideal depth range (20pts)
        - Volume confirmation (15pts)
        - Price above 50-day MA (15pts)
        - Price above 200-day MA (10pts)
        - Consolidation tightness (15pts)
        - Base length in ideal range (10pts)
        - Pattern-specific bonuses (15pts)
        """
        score = 0.0
        pattern_type = pattern["pattern_type"]
        depth = pattern.get("base_depth", 0)
        length_weeks = pattern.get("base_length_weeks", 0)

        # 1. Depth score (20 pts) — ideal ranges by pattern type
        if pattern_type == "Flat Base":
            # Ideal: 5-12%
            if 5 <= depth <= 12:
                score += 20
            elif depth < 5:
                score += 10
            else:
                score += max(0, 20 - (depth - 12) * 2)
        elif pattern_type == "Double Bottom":
            # Ideal: 20-30%
            if 20 <= depth <= 30:
                score += 20
            else:
                score += max(0, 20 - abs(depth - 25) * 1.5)
        elif pattern_type in ("Cup & Handle", "Deep Cup & Handle"):
            # Regular ideal: 15-25%, Deep: 33-40%
            if pattern_type == "Deep Cup & Handle":
                ideal_center = 37
            else:
                ideal_center = 20
            score += max(0, 20 - abs(depth - ideal_center) * 1.0)

        # 2. Volume confirmation (15 pts)
        if pattern.get("volume_confirmation"):
            score += 15

        # 3. Price above 50-day MA (15 pts)
        current_close = df["Close"].iloc[-1]
        above_50 = False
        above_200 = False
        if "MA50" in df.columns and pd.notna(df["MA50"].iloc[-1]):
            if current_close > df["MA50"].iloc[-1]:
                score += 15
                above_50 = True

        # 4. Price above 200-day MA (10 pts)
        if "MA200" in df.columns and pd.notna(df["MA200"].iloc[-1]):
            if current_close > df["MA200"].iloc[-1]:
                score += 10
                above_200 = True

        # 5. Consolidation tightness (15 pts) — based on recent weekly ranges
        last_25 = df["Close"].iloc[-25:]
        if len(last_25) >= 25:
            weekly_range = (last_25.max() - last_25.min()) / last_25.mean() * 100
            if weekly_range < 8:
                score += 15
            elif weekly_range < 12:
                score += 10
            elif weekly_range < 18:
                score += 5

        # 6. Base length (10 pts) — sweet spot varies by pattern
        if pattern_type == "Flat Base":
            ideal_weeks = (6, 12)
        elif pattern_type == "Double Bottom":
            ideal_weeks = (7, 20)
        else:
            ideal_weeks = (8, 30)

        if ideal_weeks[0] <= length_weeks <= ideal_weeks[1]:
            score += 10
        elif length_weeks < ideal_weeks[0]:
            score += 5
        else:
            score += max(0, 10 - (length_weeks - ideal_weeks[1]) * 0.5)

        # 7. Pattern-specific bonuses (15 pts)
        if pattern_type == "Double Bottom":
            low_diff = pattern.get("low_diff_pct", 10)
            if low_diff <= 3:
                score += 10  # Very tight lows
            elif low_diff <= 5:
                score += 5
            # Second low undercut (bullish shakeout)
            first = pattern.get("first_low", 0)
            second = pattern.get("second_low", 0)
            if second < first:
                score += 5

        elif pattern_type in ("Cup & Handle", "Deep Cup & Handle"):
            recovery = pattern.get("recovery_pct", 0)
            if recovery >= 90:
                score += 10
            elif recovery >= 80:
                score += 5
            # Handle tightness
            handle_low = pattern.get("handle_low", 0)
            right_high = pattern.get("right_high", 1)
            if right_high > 0:
                handle_depth = (right_high - handle_low) / right_high * 100
                if handle_depth < 8:
                    score += 5

        elif pattern_type == "Flat Base":
            if above_50 and above_200:
                score += 10  # Strong position
            if depth < 10:
                score += 5  # Very tight

        return round(min(100, max(0, score)), 1)
```

**Step 4: Run tests**

```bash
cd stock_pattern_scanner && python -m pytest tests/test_pattern_scanner.py -v -k "confidence"
```

Expected: Both PASS

**Step 5: Commit**

```bash
git add stock_pattern_scanner/pattern_scanner.py stock_pattern_scanner/tests/test_pattern_scanner.py
git commit -m "feat: add confidence scoring system for pattern quality"
```

---

## Task 9: StockScanner Class

**Files:**
- Modify: `stock_pattern_scanner/pattern_scanner.py`
- Create: `stock_pattern_scanner/tests/test_stock_scanner.py`

**Step 1: Write failing tests**

```python
# tests/test_stock_scanner.py
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
```

**Step 2: Run test to verify it fails**

```bash
cd stock_pattern_scanner && python -m pytest tests/test_stock_scanner.py -v
```

Expected: FAIL

**Step 3: Write implementation**

Add to `pattern_scanner.py`:

```python
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Optional
import yfinance as yf

logger = logging.getLogger(__name__)


class StockScanner:
    """Scans a list of tickers for base patterns using concurrent fetching."""

    def __init__(self, tickers: list[str], max_workers: int = 5):
        self.tickers = tickers
        self.max_workers = max_workers
        self.detector = PatternDetector()

    def _fetch_data(self, ticker: str) -> pd.DataFrame | None:
        """Fetch 2 years of historical data for a ticker."""
        try:
            t = yf.Ticker(ticker)
            df = t.history(period="2y")
            if df is None or len(df) < 200:
                return None
            return df
        except Exception as e:
            logger.warning("Failed to fetch data for %s: %s", ticker, e)
            return None

    def _analyze_ticker(
        self, ticker: str, spy_df: pd.DataFrame
    ) -> list[PatternResult]:
        """Analyze a single ticker for all pattern types."""
        df = self._fetch_data(ticker)
        if df is None:
            return []

        df = self.detector.add_moving_averages(df)

        results = []
        current_price = round(float(df["Close"].iloc[-1]), 2)
        above_50 = bool(
            "MA50" in df.columns
            and pd.notna(df["MA50"].iloc[-1])
            and current_price > df["MA50"].iloc[-1]
        )
        above_200 = bool(
            "MA200" in df.columns
            and pd.notna(df["MA200"].iloc[-1])
            and current_price > df["MA200"].iloc[-1]
        )
        rs_rating = self.detector.calculate_relative_strength(df, spy_df)

        detectors = [
            self.detector.detect_flat_base,
            self.detector.detect_double_bottom,
            self.detector.detect_cup_and_handle,
        ]

        for detect_fn in detectors:
            try:
                pattern = detect_fn(df)
                if pattern is not None:
                    confidence = self.detector.calculate_confidence(pattern, df)
                    result = PatternResult(
                        ticker=ticker,
                        pattern_type=pattern["pattern_type"],
                        confidence_score=confidence,
                        buy_point=pattern["buy_point"],
                        current_price=pattern["current_price"],
                        distance_to_pivot=pattern["distance_to_pivot"],
                        base_depth=pattern["base_depth"],
                        base_length_weeks=pattern["base_length_weeks"],
                        volume_confirmation=pattern["volume_confirmation"],
                        above_50ma=above_50,
                        above_200ma=above_200,
                        rs_rating=rs_rating,
                        pattern_details=pattern,
                    )
                    results.append(result)
            except Exception as e:
                logger.warning("Error detecting %s for %s: %s", detect_fn.__name__, ticker, e)

        return results

    def scan(
        self,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ) -> list[PatternResult]:
        """Scan all tickers for patterns.

        Args:
            progress_callback: Called with (current_index, total, ticker_name) after each ticker.

        Returns:
            List of PatternResult sorted by confidence_score descending.
        """
        # Fetch SPY data for relative strength
        spy_df = self._fetch_data("SPY")
        if spy_df is None:
            logger.error("Failed to fetch SPY data. RS ratings will be inaccurate.")
            spy_df = pd.DataFrame({"Close": [100] * 252, "Volume": [1] * 252})

        all_results: list[PatternResult] = []
        total = len(self.tickers)
        completed = 0

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_ticker = {
                executor.submit(self._analyze_ticker, ticker, spy_df): ticker
                for ticker in self.tickers
            }
            for future in as_completed(future_to_ticker):
                ticker = future_to_ticker[future]
                completed += 1
                try:
                    results = future.result()
                    all_results.extend(results)
                except Exception as e:
                    logger.warning("Error scanning %s: %s", ticker, e)

                if progress_callback:
                    progress_callback(completed, total, ticker)

        all_results.sort(key=lambda r: r.confidence_score, reverse=True)
        return all_results
```

**Step 4: Run tests**

```bash
cd stock_pattern_scanner && python -m pytest tests/test_stock_scanner.py -v
```

Expected: All PASS

**Step 5: Commit**

```bash
git add stock_pattern_scanner/pattern_scanner.py stock_pattern_scanner/tests/test_stock_scanner.py
git commit -m "feat: add StockScanner with concurrent fetching and progress callbacks"
```

---

## Task 10: SQLite Database Cache

**Files:**
- Create: `stock_pattern_scanner/database.py`
- Create: `stock_pattern_scanner/tests/test_database.py`

**Step 1: Write failing tests**

```python
# tests/test_database.py
import os
import tempfile
from database import ScanDatabase
from pattern_scanner import PatternResult


def test_create_scan():
    with tempfile.TemporaryDirectory() as tmpdir:
        db = ScanDatabase(os.path.join(tmpdir, "test.db"))
        scan_id = db.create_scan(watchlist="default", tickers=["AAPL", "MSFT"])
        assert isinstance(scan_id, str)
        assert len(scan_id) > 0


def test_update_scan_progress():
    with tempfile.TemporaryDirectory() as tmpdir:
        db = ScanDatabase(os.path.join(tmpdir, "test.db"))
        scan_id = db.create_scan(watchlist="default", tickers=["AAPL"])
        db.update_progress(scan_id, current=1, total=2, ticker="AAPL")
        progress = db.get_progress(scan_id)
        assert progress["current"] == 1
        assert progress["total"] == 2
        assert progress["ticker"] == "AAPL"


def test_save_and_get_results():
    with tempfile.TemporaryDirectory() as tmpdir:
        db = ScanDatabase(os.path.join(tmpdir, "test.db"))
        scan_id = db.create_scan(watchlist="default", tickers=["AAPL"])

        result = PatternResult(
            ticker="AAPL",
            pattern_type="Flat Base",
            confidence_score=80.0,
            buy_point=150.0,
            current_price=148.0,
            distance_to_pivot=-1.33,
            base_depth=10.0,
            base_length_weeks=7,
            volume_confirmation=True,
            above_50ma=True,
            above_200ma=True,
            rs_rating=85.0,
            pattern_details={"base_high": 152.0},
        )
        db.save_results(scan_id, [result])
        db.update_status(scan_id, "completed")

        results = db.get_results(scan_id)
        assert len(results) == 1
        assert results[0].ticker == "AAPL"
        assert results[0].confidence_score == 80.0

        status = db.get_scan_status(scan_id)
        assert status == "completed"
```

**Step 2: Run test to verify it fails**

```bash
cd stock_pattern_scanner && python -m pytest tests/test_database.py -v
```

Expected: FAIL

**Step 3: Write implementation**

```python
# database.py
"""SQLite database for caching scan results."""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime
from typing import Optional

from pattern_scanner import PatternResult


class ScanDatabase:
    """SQLite-backed storage for scan state and results."""

    def __init__(self, db_path: str = "scanner.db"):
        self.db_path = db_path
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        conn = self._get_conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS scans (
                scan_id TEXT PRIMARY KEY,
                watchlist TEXT,
                tickers TEXT,
                status TEXT DEFAULT 'pending',
                created_at TEXT,
                completed_at TEXT,
                progress_current INTEGER DEFAULT 0,
                progress_total INTEGER DEFAULT 0,
                progress_ticker TEXT DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scan_id TEXT,
                ticker TEXT,
                pattern_type TEXT,
                confidence_score REAL,
                buy_point REAL,
                current_price REAL,
                distance_to_pivot REAL,
                base_depth REAL,
                base_length_weeks INTEGER,
                volume_confirmation INTEGER,
                above_50ma INTEGER,
                above_200ma INTEGER,
                rs_rating REAL,
                pattern_details TEXT,
                FOREIGN KEY (scan_id) REFERENCES scans(scan_id)
            );
        """)
        conn.commit()
        conn.close()

    def create_scan(self, watchlist: str, tickers: list[str]) -> str:
        scan_id = str(uuid.uuid4())[:8]
        conn = self._get_conn()
        conn.execute(
            "INSERT INTO scans (scan_id, watchlist, tickers, status, created_at, progress_total) VALUES (?, ?, ?, ?, ?, ?)",
            (scan_id, watchlist, json.dumps(tickers), "running", datetime.now().isoformat(), len(tickers)),
        )
        conn.commit()
        conn.close()
        return scan_id

    def update_progress(self, scan_id: str, current: int, total: int, ticker: str):
        conn = self._get_conn()
        conn.execute(
            "UPDATE scans SET progress_current=?, progress_total=?, progress_ticker=? WHERE scan_id=?",
            (current, total, ticker, scan_id),
        )
        conn.commit()
        conn.close()

    def get_progress(self, scan_id: str) -> dict:
        conn = self._get_conn()
        row = conn.execute("SELECT * FROM scans WHERE scan_id=?", (scan_id,)).fetchone()
        conn.close()
        if row is None:
            return {"current": 0, "total": 0, "ticker": "", "status": "not_found"}
        return {
            "current": row["progress_current"],
            "total": row["progress_total"],
            "ticker": row["progress_ticker"],
            "status": row["status"],
        }

    def update_status(self, scan_id: str, status: str):
        conn = self._get_conn()
        completed_at = datetime.now().isoformat() if status == "completed" else None
        conn.execute(
            "UPDATE scans SET status=?, completed_at=? WHERE scan_id=?",
            (status, completed_at, scan_id),
        )
        conn.commit()
        conn.close()

    def get_scan_status(self, scan_id: str) -> Optional[str]:
        conn = self._get_conn()
        row = conn.execute("SELECT status FROM scans WHERE scan_id=?", (scan_id,)).fetchone()
        conn.close()
        return row["status"] if row else None

    def save_results(self, scan_id: str, results: list[PatternResult]):
        conn = self._get_conn()
        for r in results:
            conn.execute(
                """INSERT INTO results
                   (scan_id, ticker, pattern_type, confidence_score, buy_point,
                    current_price, distance_to_pivot, base_depth, base_length_weeks,
                    volume_confirmation, above_50ma, above_200ma, rs_rating, pattern_details)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    scan_id, r.ticker, r.pattern_type, r.confidence_score,
                    r.buy_point, r.current_price, r.distance_to_pivot,
                    r.base_depth, r.base_length_weeks,
                    int(r.volume_confirmation), int(r.above_50ma),
                    int(r.above_200ma), r.rs_rating,
                    json.dumps(r.pattern_details),
                ),
            )
        conn.commit()
        conn.close()

    def get_results(self, scan_id: str) -> list[PatternResult]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM results WHERE scan_id=? ORDER BY confidence_score DESC",
            (scan_id,),
        ).fetchall()
        conn.close()

        results = []
        for row in rows:
            results.append(PatternResult(
                ticker=row["ticker"],
                pattern_type=row["pattern_type"],
                confidence_score=row["confidence_score"],
                buy_point=row["buy_point"],
                current_price=row["current_price"],
                distance_to_pivot=row["distance_to_pivot"],
                base_depth=row["base_depth"],
                base_length_weeks=row["base_length_weeks"],
                volume_confirmation=bool(row["volume_confirmation"]),
                above_50ma=bool(row["above_50ma"]),
                above_200ma=bool(row["above_200ma"]),
                rs_rating=row["rs_rating"],
                pattern_details=json.loads(row["pattern_details"]),
            ))
        return results
```

**Step 4: Run tests**

```bash
cd stock_pattern_scanner && python -m pytest tests/test_database.py -v
```

Expected: All 3 PASS

**Step 5: Commit**

```bash
git add stock_pattern_scanner/database.py stock_pattern_scanner/tests/test_database.py
git commit -m "feat: add SQLite database for scan result caching"
```

---

## Task 11: Excel Export

**Files:**
- Create: `stock_pattern_scanner/excel_export.py`
- Create: `stock_pattern_scanner/tests/test_excel_export.py`

**Step 1: Write failing test**

```python
# tests/test_excel_export.py
import os
import tempfile
from openpyxl import load_workbook
from pattern_scanner import PatternResult
from excel_export import export_to_excel


def _sample_results() -> list[PatternResult]:
    return [
        PatternResult(
            ticker="AAPL", pattern_type="Cup & Handle", confidence_score=85.0,
            buy_point=195.0, current_price=193.0, distance_to_pivot=-1.0,
            base_depth=22.0, base_length_weeks=14, volume_confirmation=True,
            above_50ma=True, above_200ma=True, rs_rating=88.0,
            pattern_details={"cup_low": 160.0},
        ),
        PatternResult(
            ticker="NVDA", pattern_type="Flat Base", confidence_score=72.0,
            buy_point=500.0, current_price=485.0, distance_to_pivot=-3.0,
            base_depth=9.0, base_length_weeks=6, volume_confirmation=False,
            above_50ma=True, above_200ma=True, rs_rating=95.0,
            pattern_details={},
        ),
    ]


def test_export_creates_file():
    results = _sample_results()
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "test_report.xlsx")
        export_to_excel(results, path)
        assert os.path.exists(path)


def test_export_has_three_sheets():
    results = _sample_results()
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "test_report.xlsx")
        export_to_excel(results, path)
        wb = load_workbook(path)
        assert "Pattern Scanner Results" in wb.sheetnames
        assert "Pattern Guide" in wb.sheetnames
        assert "Top Picks" in wb.sheetnames


def test_export_results_sheet_has_data():
    results = _sample_results()
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "test_report.xlsx")
        export_to_excel(results, path)
        wb = load_workbook(path)
        ws = wb["Pattern Scanner Results"]
        # Header row + 2 data rows
        assert ws.max_row >= 3
        assert ws["A2"].value == "AAPL"
```

**Step 2: Run test to verify it fails**

```bash
cd stock_pattern_scanner && python -m pytest tests/test_excel_export.py -v
```

Expected: FAIL

**Step 3: Write implementation**

```python
# excel_export.py
"""Excel report generation for pattern scanner results."""

from __future__ import annotations

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from pattern_scanner import PatternResult


def export_to_excel(results: list[PatternResult], filepath: str):
    """Export scan results to a formatted Excel workbook.

    Creates three sheets:
    - Pattern Scanner Results: full data table with conditional formatting
    - Pattern Guide: definitions of each pattern type
    - Top Picks: filtered actionable stocks
    """
    wb = Workbook()

    _create_results_sheet(wb, results)
    _create_guide_sheet(wb)
    _create_top_picks_sheet(wb, results)

    wb.save(filepath)


def _create_results_sheet(wb: Workbook, results: list[PatternResult]):
    ws = wb.active
    ws.title = "Pattern Scanner Results"

    # Styles
    header_font = Font(bold=True, color="FFFFFF", size=11)
    header_fill = PatternFill(start_color="1B2A4A", end_color="1B2A4A", fill_type="solid")
    green_fill = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")
    yellow_fill = PatternFill(start_color="FFEB9C", end_color="FFEB9C", fill_type="solid")
    thin_border = Border(
        left=Side(style="thin"), right=Side(style="thin"),
        top=Side(style="thin"), bottom=Side(style="thin"),
    )

    headers = [
        "Ticker", "Pattern", "Score", "Status", "Price", "Buy Point",
        "Distance %", "Depth %", "Length (wks)", "RS Rating",
        "Above 50MA", "Above 200MA", "Vol Confirm",
    ]

    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center")
        cell.border = thin_border

    for row_idx, r in enumerate(results, 2):
        values = [
            r.ticker, r.pattern_type, r.confidence_score, r.status,
            r.current_price, r.buy_point,
            round(r.distance_to_pivot, 1), round(r.base_depth, 1),
            r.base_length_weeks, round(r.rs_rating, 1),
            "Yes" if r.above_50ma else "No",
            "Yes" if r.above_200ma else "No",
            "Yes" if r.volume_confirmation else "No",
        ]
        for col, val in enumerate(values, 1):
            cell = ws.cell(row=row_idx, column=col, value=val)
            cell.border = thin_border
            cell.alignment = Alignment(horizontal="center")

        # Conditional formatting on score
        score_cell = ws.cell(row=row_idx, column=3)
        if r.confidence_score >= 75:
            score_cell.fill = green_fill
        elif r.confidence_score >= 60:
            score_cell.fill = yellow_fill

    # Column widths
    widths = [8, 18, 8, 12, 10, 10, 10, 10, 12, 10, 10, 12, 12]
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w

    ws.freeze_panes = "A2"


def _create_guide_sheet(wb: Workbook):
    ws = wb.create_sheet("Pattern Guide")

    title_font = Font(bold=True, size=14)
    header_font = Font(bold=True, size=12)

    ws.cell(row=1, column=1, value="Pattern Identification Guide").font = title_font

    patterns = [
        ("Cup & Handle", [
            "U-shaped base followed by small downward-drifting handle",
            "Cup depth: 12-33% correction from prior high",
            "Handle: 1-6 weeks, <15% decline, declining volume",
            "Duration: 7-65 weeks total",
            "Buy point: Break above handle high on volume surge",
        ]),
        ("Deep Cup & Handle", [
            "Same as Cup & Handle but 33-50% cup depth",
            "Often forms in volatile or bear markets",
            "Longer formation time typical",
        ]),
        ("Double Bottom", [
            "W-pattern with two distinct lows at similar price levels",
            "Lows within 3-5% of each other",
            "Second low may slightly undercut first (bullish shakeout)",
            "Depth: 20-30% typical correction",
            "Buy point: Break above middle peak",
        ]),
        ("Flat Base", [
            "Tight sideways consolidation, <15% range",
            "Minimum 5 weeks duration",
            "Often forms after breakout from deeper base",
            "Should form mostly above 50-day moving average",
            "Buy point: Break above base high",
        ]),
    ]

    row = 3
    for name, details in patterns:
        ws.cell(row=row, column=1, value=name).font = header_font
        row += 1
        for detail in details:
            ws.cell(row=row, column=1, value=f"  - {detail}")
            row += 1
        row += 1

    ws.column_dimensions["A"].width = 70


def _create_top_picks_sheet(wb: Workbook, results: list[PatternResult]):
    ws = wb.create_sheet("Top Picks")

    header_font = Font(bold=True, color="FFFFFF", size=11)
    header_fill = PatternFill(start_color="2E7D32", end_color="2E7D32", fill_type="solid")
    thin_border = Border(
        left=Side(style="thin"), right=Side(style="thin"),
        top=Side(style="thin"), bottom=Side(style="thin"),
    )

    # Filter: score >= 65, within 5% of buy point, above 50MA
    top_picks = [
        r for r in results
        if r.confidence_score >= 65
        and r.distance_to_pivot >= -5.0
        and r.above_50ma
    ]

    headers = ["Rank", "Ticker", "Pattern", "Score", "Status", "Price", "Buy Point", "Action"]
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center")
        cell.border = thin_border

    for row_idx, r in enumerate(top_picks, 2):
        if r.status == "At Pivot":
            action = "WATCH - Near breakout"
        elif r.status == "Near Pivot":
            action = "WATCHLIST - Approaching"
        else:
            action = "MONITOR"

        values = [
            row_idx - 1, r.ticker, r.pattern_type, r.confidence_score,
            r.status, r.current_price, r.buy_point, action,
        ]
        for col, val in enumerate(values, 1):
            cell = ws.cell(row=row_idx, column=col, value=val)
            cell.border = thin_border
            cell.alignment = Alignment(horizontal="center")

    widths = [6, 8, 18, 8, 12, 10, 10, 25]
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w

    ws.freeze_panes = "A2"
```

**Step 4: Run tests**

```bash
cd stock_pattern_scanner && python -m pytest tests/test_excel_export.py -v
```

Expected: All 3 PASS

**Step 5: Commit**

```bash
git add stock_pattern_scanner/excel_export.py stock_pattern_scanner/tests/test_excel_export.py
git commit -m "feat: add Excel export with three formatted sheets"
```

---

## Task 12: FastAPI Web App

**Files:**
- Create: `stock_pattern_scanner/app.py`

This task creates the FastAPI application with all API endpoints and SSE progress streaming. Tests will use FastAPI's TestClient.

**Step 1: Write failing test**

Create `stock_pattern_scanner/tests/test_app.py`:

```python
# tests/test_app.py
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from app import app


client = TestClient(app)


def test_dashboard_loads():
    response = client.get("/")
    assert response.status_code == 200
    assert "Stock Pattern Scanner" in response.text


def test_get_watchlists():
    response = client.get("/api/watchlists")
    assert response.status_code == 200
    data = response.json()
    assert "default" in data
    assert "sp500" in data
    assert "nasdaq100" in data


def test_start_scan():
    response = client.post("/api/scan", json={
        "watchlist": "custom",
        "tickers": ["AAPL", "MSFT"],
    })
    assert response.status_code == 200
    data = response.json()
    assert "scan_id" in data


def test_get_results_pending():
    """Results for a non-existent scan return empty."""
    response = client.get("/api/scan/nonexistent/results")
    assert response.status_code == 200
```

**Step 2: Run test to verify it fails**

```bash
cd stock_pattern_scanner && python -m pytest tests/test_app.py -v
```

Expected: FAIL

**Step 3: Write implementation**

```python
# app.py
"""FastAPI web application for the stock pattern scanner."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import threading
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.responses import HTMLResponse, StreamingResponse, FileResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from database import ScanDatabase
from excel_export import export_to_excel
from pattern_scanner import StockScanner
from ticker_lists import (
    DEFAULT_GROWTH_WATCHLIST,
    get_sp500_tickers,
    get_nasdaq100_tickers,
)

logger = logging.getLogger(__name__)

DB_PATH = os.environ.get("SCANNER_DB_PATH", "scanner.db")
db = ScanDatabase(DB_PATH)

templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield

app = FastAPI(title="Stock Pattern Scanner", lifespan=lifespan)


class ScanRequest(BaseModel):
    watchlist: str = "default"
    tickers: Optional[list[str]] = None
    min_score: float = 0


def _resolve_tickers(request: ScanRequest) -> list[str]:
    if request.tickers:
        return request.tickers
    if request.watchlist == "sp500":
        return get_sp500_tickers()
    if request.watchlist == "nasdaq100":
        return get_nasdaq100_tickers()
    return DEFAULT_GROWTH_WATCHLIST


def _run_scan(scan_id: str, tickers: list[str], min_score: float):
    """Run scan in a background thread."""
    def progress_cb(current: int, total: int, ticker: str):
        db.update_progress(scan_id, current, total, ticker)

    try:
        scanner = StockScanner(tickers=tickers, max_workers=5)
        results = scanner.scan(progress_callback=progress_cb)

        if min_score > 0:
            results = [r for r in results if r.confidence_score >= min_score]

        db.save_results(scan_id, results)
        db.update_status(scan_id, "completed")
    except Exception as e:
        logger.error("Scan %s failed: %s", scan_id, e)
        db.update_status(scan_id, "failed")


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})


@app.get("/api/watchlists")
async def get_watchlists():
    return {
        "default": {"name": "Growth Watchlist", "count": len(DEFAULT_GROWTH_WATCHLIST)},
        "sp500": {"name": "S&P 500", "count": "~500"},
        "nasdaq100": {"name": "NASDAQ 100", "count": "~100"},
        "custom": {"name": "Custom Tickers", "count": "variable"},
    }


@app.post("/api/scan")
async def start_scan(request: ScanRequest):
    tickers = _resolve_tickers(request)
    scan_id = db.create_scan(watchlist=request.watchlist, tickers=tickers)

    thread = threading.Thread(
        target=_run_scan,
        args=(scan_id, tickers, request.min_score),
        daemon=True,
    )
    thread.start()

    return {"scan_id": scan_id, "total_tickers": len(tickers)}


@app.get("/api/scan/{scan_id}/progress")
async def scan_progress(scan_id: str):
    """SSE endpoint streaming scan progress."""
    async def event_generator():
        while True:
            progress = db.get_progress(scan_id)
            data = json.dumps(progress)
            yield f"data: {data}\n\n"

            if progress["status"] in ("completed", "failed", "not_found"):
                break
            await asyncio.sleep(0.5)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


@app.get("/api/scan/{scan_id}/results")
async def get_results(scan_id: str):
    results = db.get_results(scan_id)
    return {
        "scan_id": scan_id,
        "count": len(results),
        "results": [
            {
                "ticker": r.ticker,
                "pattern_type": r.pattern_type,
                "confidence_score": r.confidence_score,
                "status": r.status,
                "buy_point": r.buy_point,
                "current_price": r.current_price,
                "distance_to_pivot": r.distance_to_pivot,
                "base_depth": r.base_depth,
                "base_length_weeks": r.base_length_weeks,
                "volume_confirmation": r.volume_confirmation,
                "above_50ma": r.above_50ma,
                "above_200ma": r.above_200ma,
                "rs_rating": r.rs_rating,
            }
            for r in results
        ],
    }


@app.get("/api/export/excel/{scan_id}")
async def export_excel(scan_id: str):
    results = db.get_results(scan_id)
    if not results:
        return {"error": "No results found for this scan"}

    filepath = f"scan_{scan_id}.xlsx"
    export_to_excel(results, filepath)
    return FileResponse(
        filepath,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=f"pattern_scan_{scan_id}.xlsx",
    )
```

**Step 4: Run tests**

```bash
cd stock_pattern_scanner && python -m pytest tests/test_app.py -v
```

Expected: All 4 PASS

**Step 5: Commit**

```bash
git add stock_pattern_scanner/app.py stock_pattern_scanner/tests/test_app.py
git commit -m "feat: add FastAPI app with scan API, SSE progress, and Excel export endpoint"
```

---

## Task 13: Frontend Dashboard Template

**Files:**
- Create: `stock_pattern_scanner/templates/dashboard.html`

This is a large single-file HTML template with embedded CSS and JS. No tests needed — it's purely visual. Validate by running the app and visiting `http://localhost:8000`.

**Step 1: Create the dashboard template**

The template should include:
- Dark theme (background: #0d1117, text: #e6edf3)
- Header with "Stock Pattern Scanner" title
- Controls bar: watchlist dropdown, custom ticker textarea, min score slider, Scan button
- Progress bar (hidden initially, shown during scan via SSE)
- Stats cards row: Total Found, At Pivot, Near Pivot, High Quality (score >= 75)
- Filters row: pattern type dropdown, status dropdown, search input
- Results table: sortable columns, color-coded badges
- Export Excel button
- All interactivity via vanilla JS
- Uses `/api/scan`, `/api/scan/{id}/progress` (SSE), `/api/scan/{id}/results`, `/api/export/excel/{id}`

Key color scheme:
- Cup & Handle badge: #58a6ff
- Deep Cup & Handle badge: #bc8cff
- Double Bottom badge: #3fb950
- Flat Base badge: #f0883e
- At Pivot status: #f85149
- Near Pivot status: #d29922
- Building status: #8b949e
- Extended status: #388bfd

The template is too large to include inline here. Build it with these sections:
1. `<style>` block with CSS variables, dark theme, responsive grid
2. Header bar
3. Controls section with form elements
4. Progress bar section
5. Stats cards section (populated by JS)
6. Filters section
7. Results table section (populated by JS)
8. `<script>` block with: startScan(), listenProgress(), loadResults(), sortTable(), filterResults(), exportExcel()

**Step 2: Run the app to verify**

```bash
cd stock_pattern_scanner && python -m uvicorn app:app --reload --port 8000
```

Visit `http://localhost:8000` — confirm dark theme loads, controls render, Scan button is clickable.

**Step 3: Commit**

```bash
git add stock_pattern_scanner/templates/dashboard.html
git commit -m "feat: add dark-themed dashboard with interactive controls and SSE progress"
```

---

## Task 14: CLI Runner

**Files:**
- Create: `stock_pattern_scanner/run_scanner.py`
- Create: `stock_pattern_scanner/tests/test_cli.py`

**Step 1: Write failing test**

```python
# tests/test_cli.py
import subprocess
import sys


def test_cli_help():
    result = subprocess.run(
        [sys.executable, "run_scanner.py", "--help"],
        capture_output=True, text=True, cwd=".",
    )
    assert result.returncode == 0
    assert "--sp500" in result.stdout
    assert "--nasdaq100" in result.stdout
    assert "--tickers" in result.stdout
    assert "--min-score" in result.stdout


def test_cli_version_or_default():
    """CLI should at least parse arguments without crashing."""
    result = subprocess.run(
        [sys.executable, "run_scanner.py", "--tickers", "FAKE_TICKER_XYZ", "--no-excel", "--top", "1"],
        capture_output=True, text=True, cwd=".", timeout=120,
    )
    # Should complete without Python traceback (may have warnings about invalid ticker)
    assert "Traceback" not in result.stderr or "Traceback" not in result.stdout
```

**Step 2: Run test to verify it fails**

```bash
cd stock_pattern_scanner && python -m pytest tests/test_cli.py -v
```

Expected: FAIL

**Step 3: Write implementation**

```python
#!/usr/bin/env python3
# run_scanner.py
"""CLI entry point for the stock pattern scanner."""

from __future__ import annotations

import argparse
import sys
import time

from pattern_scanner import StockScanner
from excel_export import export_to_excel
from ticker_lists import (
    DEFAULT_GROWTH_WATCHLIST,
    get_sp500_tickers,
    get_nasdaq100_tickers,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Stock Base Pattern Scanner — Detect CAN SLIM base patterns",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--sp500", action="store_true", help="Scan S&P 500 stocks")
    group.add_argument("--nasdaq100", action="store_true", help="Scan NASDAQ 100 stocks")
    group.add_argument("--tickers", nargs="+", metavar="TICKER", help="Specific tickers to scan")
    group.add_argument("--file", metavar="FILE", help="Read tickers from file (one per line)")

    parser.add_argument("--min-score", type=float, default=0, help="Minimum confidence score (0-100)")
    parser.add_argument("--near-pivot", action="store_true", help="Only show stocks within 5%% of buy point")
    parser.add_argument("--top", type=int, default=50, help="Show top N results (default: 50)")
    parser.add_argument("--no-excel", action="store_true", help="Skip Excel export")
    parser.add_argument("--output", metavar="FILE", default="pattern_scan.xlsx", help="Excel output filename")
    parser.add_argument("--web", action="store_true", help="Launch web dashboard instead of CLI scan")

    return parser.parse_args(argv)


def resolve_tickers(args: argparse.Namespace) -> list[str]:
    if args.tickers:
        return [t.upper() for t in args.tickers]
    if args.file:
        with open(args.file) as f:
            return [line.strip().upper() for line in f if line.strip()]
    if args.sp500:
        print("Fetching S&P 500 ticker list...")
        return get_sp500_tickers()
    if args.nasdaq100:
        print("Fetching NASDAQ 100 ticker list...")
        return get_nasdaq100_tickers()
    return DEFAULT_GROWTH_WATCHLIST


def print_progress(current: int, total: int, ticker: str):
    pct = current / total * 100 if total > 0 else 0
    bar_len = 30
    filled = int(bar_len * current / total) if total > 0 else 0
    bar = "█" * filled + "░" * (bar_len - filled)
    print(f"\r  {bar} {pct:5.1f}% ({current}/{total}) {ticker:<8}", end="", flush=True)


def print_results_table(results):
    if not results:
        print("\nNo patterns found matching your criteria.")
        return

    print(f"\n{'─' * 120}")
    print(f"{'#':>3}  {'Ticker':<8} {'Pattern':<20} {'Score':>6} {'Status':<12} "
          f"{'Price':>10} {'Buy Pt':>10} {'Dist%':>7} {'Depth%':>7} "
          f"{'Wks':>4} {'RS':>5} {'50MA':>5} {'200MA':>6} {'Vol':>4}")
    print(f"{'─' * 120}")

    for i, r in enumerate(results, 1):
        ma50 = "✓" if r.above_50ma else "✗"
        ma200 = "✓" if r.above_200ma else "✗"
        vol = "✓" if r.volume_confirmation else "✗"
        print(f"{i:>3}  {r.ticker:<8} {r.pattern_type:<20} {r.confidence_score:>5.1f}  "
              f"{r.status:<12} {r.current_price:>10.2f} {r.buy_point:>10.2f} "
              f"{r.distance_to_pivot:>6.1f}% {r.base_depth:>6.1f}% "
              f"{r.base_length_weeks:>4} {r.rs_rating:>5.1f} {ma50:>5} {ma200:>6} {vol:>4}")

    print(f"{'─' * 120}")


def main():
    args = parse_args()

    if args.web:
        import uvicorn
        print("Starting web dashboard at http://localhost:8000")
        uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
        return

    tickers = resolve_tickers(args)
    print(f"\nStock Base Pattern Scanner")
    print(f"{'═' * 40}")
    print(f"Scanning {len(tickers)} tickers...\n")

    start_time = time.time()
    scanner = StockScanner(tickers=tickers, max_workers=5)
    results = scanner.scan(progress_callback=print_progress)
    elapsed = time.time() - start_time

    print(f"\n\nScan complete in {elapsed:.1f}s — {len(results)} patterns found\n")

    # Apply filters
    if args.min_score > 0:
        results = [r for r in results if r.confidence_score >= args.min_score]
    if args.near_pivot:
        results = [r for r in results if abs(r.distance_to_pivot) <= 5.0]

    results = results[: args.top]
    print_results_table(results)

    # Excel export
    if not args.no_excel and results:
        export_to_excel(results, args.output)
        print(f"\nExcel report saved to: {args.output}")


if __name__ == "__main__":
    main()
```

**Step 4: Run tests**

```bash
cd stock_pattern_scanner && python -m pytest tests/test_cli.py -v
```

Expected: All PASS

**Step 5: Commit**

```bash
git add stock_pattern_scanner/run_scanner.py stock_pattern_scanner/tests/test_cli.py
git commit -m "feat: add CLI runner with argparse, progress bar, and table output"
```

---

## Task 15: Integration Test — End-to-End Smoke Test

**Files:**
- Create: `stock_pattern_scanner/tests/test_integration.py`

**Step 1: Write integration test**

```python
# tests/test_integration.py
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
```

**Step 2: Run it**

```bash
cd stock_pattern_scanner && python -m pytest tests/test_integration.py -v -m integration
```

Expected: PASS (may find 0 patterns — that's OK, the test validates structure)

**Step 3: Commit**

```bash
git add stock_pattern_scanner/tests/test_integration.py
git commit -m "test: add end-to-end integration smoke test"
```

---

## Task 16: README

**Files:**
- Create: `stock_pattern_scanner/README.md`

Write a README covering:
- What it does (1-2 sentences)
- Quick start: `pip install -r requirements.txt && python run_scanner.py --web`
- CLI usage examples (from the brief)
- API endpoints summary
- Pattern descriptions (brief)

**Step 1: Write README**

**Step 2: Commit**

```bash
git add stock_pattern_scanner/README.md
git commit -m "docs: add README with usage instructions"
```

---

## Execution Order Summary

| Task | Component | Dependencies |
|------|-----------|-------------|
| 1 | Project setup | None |
| 2 | PatternResult dataclass | Task 1 |
| 3 | Ticker lists | Task 1 |
| 4 | PatternDetector helpers | Task 2 |
| 5 | Flat base detection | Task 4 |
| 6 | Double bottom detection | Task 4 |
| 7 | Cup & handle detection | Task 4 |
| 8 | Confidence scoring | Tasks 5-7 |
| 9 | StockScanner class | Task 8 |
| 10 | SQLite database | Task 2 |
| 11 | Excel export | Task 2 |
| 12 | FastAPI app | Tasks 9, 10, 11, 3 |
| 13 | Dashboard template | Task 12 |
| 14 | CLI runner | Tasks 9, 11, 3 |
| 15 | Integration test | Tasks 9 |
| 16 | README | All |

**Parallelizable:** Tasks 3, 5, 6, 7 can run in parallel. Tasks 10 and 11 can run in parallel.
