# Accuracy Improvements Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add earnings analysis, sector relative strength, liquidity filtering, and scoring refinements to improve pattern detection confidence.

**Architecture:** Two new modules (`earnings_analysis.py`, `sector_strength.py`) integrate into the existing scan pipeline in `stock_scanner.py`. Scoring rebalance and filter changes modify `pattern_scanner.py`, `breakout_rules.py`, and `market_regime.py`. Database gets new columns and an earnings cache table. Dashboard gets new columns, badges, and help text.

**Tech Stack:** Python, Financial Modeling Prep API, yfinance, SQLite, FastAPI, HTML/CSS/JS

---

## Task 1: Add Constants and FMP Configuration

**Files:**
- Modify: `stock_pattern_scanner/constants.py`

**Step 1: Add new constants to constants.py**

Add the following constants at the end of the file, organized by section:

```python
# --- Earnings Analysis (FMP) ---
FMP_API_BASE_URL = "https://financialmodelingprep.com/api/v3"
FMP_REQUEST_DELAY_MS = 300  # delay between FMP calls to respect rate limits
FMP_CACHE_TTL_HOURS = 24  # cache earnings data for 24 hours

# Earnings proximity thresholds (calendar days)
EARNINGS_IMMINENT_DAYS = 7
EARNINGS_SOON_DAYS = 14

# Post-earnings momentum scoring
EARNINGS_BEAT_MIN_PCT = 5.0  # minimum EPS surprise % for points
EARNINGS_BEAT_STRONG_PCT = 15.0  # strong beat threshold
EARNINGS_GAP_UP_PCT = 3.0  # stock gap-up on earnings day
SCORE_EARNINGS_MOMENTUM_MAX = 10.0  # max points for earnings factor

# --- Sector Relative Strength ---
SECTOR_ETF_MAP = {
    "Technology": "XLK",
    "Healthcare": "XLV",
    "Financial Services": "XLF",
    "Consumer Cyclical": "XLY",
    "Communication Services": "XLC",
    "Industrials": "XLI",
    "Consumer Defensive": "XLP",
    "Energy": "XLE",
    "Utilities": "XLU",
    "Real Estate": "XLRE",
    "Basic Materials": "XLB",
}
SECTOR_LEADING_THRESHOLD = 70  # RS above this = leading sector
SECTOR_LAGGING_THRESHOLD = 50  # RS below this = lagging sector
SECTOR_LEADING_BONUS = 5  # confidence points for leading sector
SECTOR_LAGGING_PENALTY = -10  # confidence penalty for lagging sector
SECTOR_CACHE_TTL_HOURS = 24

# --- Liquidity Floor ---
MIN_AVG_DOLLAR_VOLUME = 5_000_000  # $5M minimum avg daily dollar volume

# --- Scoring Rebalance ---
# Reduce depth from 15 to 10, volume from 20 to 15
SCORE_DEPTH_MAX = 10.0  # was 15.0
SCORE_VOLUME_PROFILE_MAX = 15.0  # was 20.0

# --- Volume Confirmation Grading ---
VOLUME_SURGE_WEAK_PCT = 20.0
VOLUME_SURGE_MODERATE_PCT = 40.0  # was the only threshold
VOLUME_SURGE_STRONG_PCT = 80.0
VOLUME_SURGE_CLIMACTIC_PCT = 150.0

SCORE_BREAKOUT_WEAK = 0.0
SCORE_BREAKOUT_MODERATE = 2.0
SCORE_BREAKOUT_CONFIRMED = 4.0
SCORE_BREAKOUT_STRONG = 5.0
SCORE_BREAKOUT_CLIMACTIC = 3.0  # penalty for exhaustion

# --- Market Regime Softening ---
REGIME_CORRECTION_CONFIDENCE_PENALTY = 15  # points deducted during corrections
```

**Step 2: Verify app starts**

Run: `cd stock_pattern_scanner && python -c "from constants import *; print('OK')"`
Expected: `OK`

**Step 3: Commit**

```bash
git add stock_pattern_scanner/constants.py
git commit -m "feat(accuracy): add constants for earnings, sector RS, liquidity, and scoring"
```

---

## Task 2: Add Earnings Cache Table to Database

**Files:**
- Modify: `stock_pattern_scanner/database.py`

**Step 1: Add earnings_cache table to _init_db()**

In `_init_db()` (around line 52), add a new CREATE TABLE statement after the existing backtest_trades table creation:

```sql
CREATE TABLE IF NOT EXISTS earnings_cache (
    ticker TEXT NOT NULL,
    next_earnings_date TEXT,
    last_4q_surprises TEXT,
    earnings_momentum_score REAL,
    earnings_gap_up INTEGER,
    fetched_at TEXT NOT NULL,
    PRIMARY KEY (ticker, fetched_at)
)
```

**Step 2: Add save/get methods for earnings cache**

Add these methods to the ScanDatabase class:

```python
def save_earnings_cache(self, ticker: str, data: dict):
    """Cache earnings data for a ticker."""
    with self._connect() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO earnings_cache
               (ticker, next_earnings_date, last_4q_surprises,
                earnings_momentum_score, earnings_gap_up, fetched_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (ticker, data.get("next_earnings_date"),
             json.dumps(data.get("surprises", [])),
             data.get("momentum_score", 0),
             1 if data.get("gap_up") else 0,
             datetime.now().isoformat())
        )

def get_earnings_cache(self, ticker: str, max_age_hours: int = 24) -> dict | None:
    """Get cached earnings data if fresh enough."""
    with self._connect() as conn:
        row = conn.execute(
            """SELECT next_earnings_date, last_4q_surprises,
                      earnings_momentum_score, earnings_gap_up, fetched_at
               FROM earnings_cache
               WHERE ticker = ?
               ORDER BY fetched_at DESC LIMIT 1""",
            (ticker,)
        ).fetchone()
    if not row:
        return None
    fetched_at = datetime.fromisoformat(row[4])
    if (datetime.now() - fetched_at).total_seconds() > max_age_hours * 3600:
        return None
    return {
        "next_earnings_date": row[0],
        "surprises": json.loads(row[1]) if row[1] else [],
        "momentum_score": row[2] or 0,
        "gap_up": bool(row[3]),
    }
```

**Step 3: Add new columns to results table via migration**

In the `_init_db()` method, add migration logic after the existing migrations (around line 126-138):

```python
# Migration: add earnings and sector columns to results
for col, coltype in [
    ("earnings_days_until", "INTEGER"),
    ("earnings_momentum_score", "REAL"),
    ("earnings_flag", "TEXT"),
    ("sector", "TEXT"),
    ("sector_rs", "REAL"),
    ("sector_class", "TEXT"),
    ("avg_dollar_volume", "REAL"),
    ("volume_grade", "TEXT"),
    ("regime_penalty", "REAL"),
]:
    try:
        conn.execute(f"ALTER TABLE results ADD COLUMN {col} {coltype}")
    except Exception:
        pass  # column already exists
```

**Step 4: Update save_results() to include new fields**

In `save_results()` (around line 181), update the INSERT statement to include the new columns. The PatternResult will be extended in a later task, so use `.get()` on the dict or `getattr()` with defaults.

**Step 5: Update get_results() to read new fields**

In `get_results()` (around line 205), add the new columns to the SELECT and map them into the result dict.

**Step 6: Verify app starts and run existing tests**

Run: `cd stock_pattern_scanner && python -c "from database import ScanDatabase; print('OK')"`
Run: `cd stock_pattern_scanner && python -m pytest tests/test_database.py -v`
Expected: All existing tests pass (new columns are nullable, backward compatible)

**Step 7: Commit**

```bash
git add stock_pattern_scanner/database.py
git commit -m "feat(accuracy): add earnings cache table and new result columns"
```

---

## Task 3: Create Earnings Analysis Module

**Files:**
- Create: `stock_pattern_scanner/earnings_analysis.py`
- Create: `stock_pattern_scanner/tests/test_earnings_analysis.py`

**Step 1: Write tests for earnings analysis**

Create `tests/test_earnings_analysis.py`:

```python
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
        stock_df = pd.DataFrame({"Close": [100, 104]},
                                index=pd.to_datetime(["2026-01-14", "2026-01-15"]))
        result = analyzer.analyze("AAPL", stock_df)
        assert "flag" in result
        assert "days_until" in result
        assert "momentum_score" in result
```

**Step 2: Run tests to verify they fail**

Run: `cd stock_pattern_scanner && python -m pytest tests/test_earnings_analysis.py -v`
Expected: FAIL (module not found)

**Step 3: Create earnings_analysis.py**

```python
"""Earnings analysis using Financial Modeling Prep API.

Provides two signals:
1. Earnings proximity warning (imminent/soon/none)
2. Post-earnings momentum score (0-10 points)
"""

import os
import time
from datetime import date, datetime, timedelta

import pandas as pd
import requests

from constants import (
    EARNINGS_BEAT_MIN_PCT,
    EARNINGS_BEAT_STRONG_PCT,
    EARNINGS_GAP_UP_PCT,
    EARNINGS_IMMINENT_DAYS,
    EARNINGS_SOON_DAYS,
    FMP_API_BASE_URL,
    FMP_REQUEST_DELAY_MS,
    SCORE_EARNINGS_MOMENTUM_MAX,
)


class EarningsAnalyzer:
    """Analyze earnings dates and surprise history via FMP API."""

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.environ.get("FMP_API_KEY", "")
        self._last_request_time = 0

    def _rate_limit(self):
        """Enforce minimum delay between FMP API calls."""
        elapsed = (time.time() - self._last_request_time) * 1000
        if elapsed < FMP_REQUEST_DELAY_MS:
            time.sleep((FMP_REQUEST_DELAY_MS - elapsed) / 1000)
        self._last_request_time = time.time()

    def _fetch_from_fmp(self, endpoint: str) -> list | None:
        """Fetch data from FMP API with rate limiting."""
        if not self.api_key:
            return None
        try:
            self._rate_limit()
            url = f"{FMP_API_BASE_URL}/{endpoint}&apikey={self.api_key}"
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                return resp.json()
            return None
        except Exception:
            return None

    def _fetch_earnings_calendar(self, ticker: str) -> str | None:
        """Get next earnings date for a ticker."""
        today = date.today().isoformat()
        future = (date.today() + timedelta(days=90)).isoformat()
        data = self._fetch_from_fmp(
            f"earning_calendar?from={today}&to={future}&symbol={ticker}"
        )
        if data and len(data) > 0:
            return data[0].get("date")
        return None

    def _fetch_earnings_history(self, ticker: str) -> list:
        """Get last 4 quarters of earnings surprises."""
        data = self._fetch_from_fmp(
            f"historical/earning_calendar/{ticker}?limit=4"
        )
        if not data:
            return []
        return data

    def _classify_proximity(self, next_date: str | None) -> dict:
        """Classify earnings proximity as imminent/soon/none."""
        if not next_date:
            return {"flag": None, "days_until": None}
        try:
            earnings_date = date.fromisoformat(next_date)
            days_until = (earnings_date - date.today()).days
            if days_until < 0:
                return {"flag": None, "days_until": None}
            if days_until <= EARNINGS_IMMINENT_DAYS:
                return {"flag": "Earnings Imminent", "days_until": days_until}
            if days_until <= EARNINGS_SOON_DAYS:
                return {"flag": "Earnings Soon", "days_until": days_until}
            return {"flag": None, "days_until": days_until}
        except (ValueError, TypeError):
            return {"flag": None, "days_until": None}

    def _calculate_momentum(self, surprises: list) -> float:
        """Calculate post-earnings momentum score (0-10).

        Scoring:
        - Most recent quarter EPS beat 5%+: 3 pts
        - Most recent quarter EPS beat 15%+: 5 pts (replaces 3)
        - Last 2 quarters both beats: +3 pts bonus
        - Stock gapped up 3%+ on earnings day: +2 pts
        - Max: 10 pts
        """
        if not surprises:
            return 0.0

        score = 0.0
        latest = surprises[0]
        surprise_pct = latest.get("surprise_pct", 0)

        # Most recent quarter beat
        if surprise_pct >= EARNINGS_BEAT_STRONG_PCT:
            score += 5
        elif surprise_pct >= EARNINGS_BEAT_MIN_PCT:
            score += 3

        # Two consecutive beats bonus
        if len(surprises) >= 2:
            second = surprises[1]
            if (surprise_pct >= EARNINGS_BEAT_MIN_PCT and
                    second.get("surprise_pct", 0) >= EARNINGS_BEAT_MIN_PCT):
                score += 3

        # Gap-up bonus
        if latest.get("gap_up", False):
            score += 2

        return min(score, SCORE_EARNINGS_MOMENTUM_MAX)

    def _detect_gap_up(self, stock_df: pd.DataFrame,
                       earnings_date_str: str) -> bool:
        """Check if stock gapped up 3%+ on earnings day."""
        try:
            earnings_date = pd.Timestamp(earnings_date_str)
            # Find the closest trading day on or after earnings
            mask = stock_df.index >= earnings_date
            if not mask.any():
                return False
            day_idx = stock_df.index[mask][0]
            pos = stock_df.index.get_loc(day_idx)
            if pos < 1:
                return False
            close_after = stock_df["Close"].iloc[pos]
            close_before = stock_df["Close"].iloc[pos - 1]
            gap_pct = (close_after - close_before) / close_before * 100
            return gap_pct >= EARNINGS_GAP_UP_PCT
        except Exception:
            return False

    def analyze(self, ticker: str,
                stock_df: pd.DataFrame | None = None) -> dict:
        """Full earnings analysis for a ticker.

        Returns:
            dict with keys: flag, days_until, momentum_score, surprises
        """
        # Fetch earnings calendar
        next_date = self._fetch_earnings_calendar(ticker)
        proximity = self._classify_proximity(next_date)

        # Fetch earnings history
        history = self._fetch_earnings_history(ticker)
        surprises = []
        for q in history:
            eps = q.get("eps")
            est = q.get("epsEstimated")
            if eps is not None and est is not None and est != 0:
                surprise_pct = (eps - est) / abs(est) * 100
                gap_up = False
                if stock_df is not None and q.get("date"):
                    gap_up = self._detect_gap_up(stock_df, q["date"])
                surprises.append({
                    "surprise_pct": surprise_pct,
                    "gap_up": gap_up,
                    "date": q.get("date"),
                })

        momentum_score = self._calculate_momentum(surprises)

        return {
            "flag": proximity["flag"],
            "days_until": proximity["days_until"],
            "momentum_score": momentum_score,
            "surprises": surprises,
            "next_earnings_date": next_date,
            "gap_up": any(s["gap_up"] for s in surprises[:1]),
        }
```

**Step 4: Run tests to verify they pass**

Run: `cd stock_pattern_scanner && python -m pytest tests/test_earnings_analysis.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add stock_pattern_scanner/earnings_analysis.py stock_pattern_scanner/tests/test_earnings_analysis.py
git commit -m "feat(accuracy): add earnings analysis module with FMP integration"
```

---

## Task 4: Create Sector Strength Module

**Files:**
- Create: `stock_pattern_scanner/sector_strength.py`
- Create: `stock_pattern_scanner/tests/test_sector_strength.py`

**Step 1: Write tests for sector strength**

Create `tests/test_sector_strength.py`:

```python
import pytest
from unittest.mock import patch, MagicMock
import pandas as pd
import numpy as np
from sector_strength import SectorAnalyzer


class TestSectorMapping:
    def test_known_tech_stock_maps_to_xlk(self):
        analyzer = SectorAnalyzer.__new__(SectorAnalyzer)
        analyzer._ticker_sector_cache = {}
        analyzer._sector_overrides = {"AAPL": "Technology"}
        assert analyzer._get_sector("AAPL") == "Technology"

    def test_unknown_ticker_returns_none(self):
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
```

**Step 2: Run tests to verify they fail**

Run: `cd stock_pattern_scanner && python -m pytest tests/test_sector_strength.py -v`
Expected: FAIL (module not found)

**Step 3: Create sector_strength.py**

```python
"""Sector relative strength analysis.

Compares 11 GICS sector ETFs against SPY to classify sectors
as leading, neutral, or lagging. Applies confidence score
adjustments based on sector strength.
"""

import yfinance
import pandas as pd

from constants import (
    RS_BASELINE,
    RS_PERIODS,
    RS_WEIGHTS,
    SECTOR_ETF_MAP,
    SECTOR_LAGGING_PENALTY,
    SECTOR_LAGGING_THRESHOLD,
    SECTOR_LEADING_BONUS,
    SECTOR_LEADING_THRESHOLD,
)


# Static ticker-to-sector mapping for common growth stocks
# Uses yfinance sector names (not GICS names)
_TICKER_SECTOR_MAP = {
    # Technology
    "AAPL": "Technology", "MSFT": "Technology", "NVDA": "Technology",
    "AMD": "Technology", "AVGO": "Technology", "QCOM": "Technology",
    "CRM": "Technology", "NOW": "Technology", "ADBE": "Technology",
    "ORCL": "Technology", "INTU": "Technology", "SNOW": "Technology",
    "NET": "Technology", "ZS": "Technology", "CRWD": "Technology",
    "PANW": "Technology", "FTNT": "Technology", "DDOG": "Technology",
    "MDB": "Technology", "SHOP": "Technology", "SQ": "Technology",
    "AMAT": "Technology", "KLAC": "Technology", "LRCX": "Technology",
    "MRVL": "Technology", "ON": "Technology", "MPWR": "Technology",
    "SNPS": "Technology", "CDNS": "Technology", "ANSS": "Technology",
    "TXN": "Technology", "MU": "Technology", "INTC": "Technology",
    # Communication Services
    "META": "Communication Services", "GOOGL": "Communication Services",
    "GOOG": "Communication Services", "NFLX": "Communication Services",
    "DIS": "Communication Services", "CMCSA": "Communication Services",
    "TMUS": "Communication Services",
    # Consumer Cyclical
    "AMZN": "Consumer Cyclical", "TSLA": "Consumer Cyclical",
    "HD": "Consumer Cyclical", "NKE": "Consumer Cyclical",
    "SBUX": "Consumer Cyclical", "TJX": "Consumer Cyclical",
    "BKNG": "Consumer Cyclical", "ABNB": "Consumer Cyclical",
    "LULU": "Consumer Cyclical", "CMG": "Consumer Cyclical",
    "DECK": "Consumer Cyclical", "RCL": "Consumer Cyclical",
    # Healthcare
    "UNH": "Healthcare", "LLY": "Healthcare", "JNJ": "Healthcare",
    "ABBV": "Healthcare", "MRK": "Healthcare", "PFE": "Healthcare",
    "TMO": "Healthcare", "ABT": "Healthcare", "ISRG": "Healthcare",
    "DXCM": "Healthcare", "VEEV": "Healthcare", "ALGN": "Healthcare",
    # Financial Services
    "JPM": "Financial Services", "BAC": "Financial Services",
    "GS": "Financial Services", "MS": "Financial Services",
    "V": "Financial Services", "MA": "Financial Services",
    "AXP": "Financial Services", "BLK": "Financial Services",
    "COIN": "Financial Services",
    # Industrials
    "CAT": "Industrials", "UNP": "Industrials", "HON": "Industrials",
    "GE": "Industrials", "RTX": "Industrials", "LMT": "Industrials",
    "DE": "Industrials", "BA": "Industrials", "FDX": "Industrials",
    "UPS": "Industrials",
    # Consumer Defensive
    "PG": "Consumer Defensive", "KO": "Consumer Defensive",
    "PEP": "Consumer Defensive", "COST": "Consumer Defensive",
    "WMT": "Consumer Defensive", "PM": "Consumer Defensive",
    # Energy
    "XOM": "Energy", "CVX": "Energy", "COP": "Energy",
    "SLB": "Energy", "EOG": "Energy",
    # Utilities
    "NEE": "Utilities", "DUK": "Utilities", "SO": "Utilities",
    # Real Estate
    "AMT": "Real Estate", "PLD": "Real Estate", "CCI": "Real Estate",
    # Basic Materials
    "LIN": "Basic Materials", "APD": "Basic Materials",
    "SHW": "Basic Materials", "FCX": "Basic Materials",
}


class SectorAnalyzer:
    """Analyze sector relative strength for pattern confidence scoring."""

    def __init__(self, spy_df: pd.DataFrame | None = None):
        self._spy_df = spy_df
        self._sector_rs_cache: dict[str, float] = {}
        self._sector_class_cache: dict[str, str] = {}
        self._etf_data_cache: dict[str, pd.DataFrame] = {}
        self._ticker_sector_cache: dict[str, str] = {}
        self._sector_overrides = _TICKER_SECTOR_MAP.copy()

    def _get_sector(self, ticker: str) -> str | None:
        """Get sector for a ticker. Uses static map, falls back to yfinance."""
        if ticker in self._ticker_sector_cache:
            return self._ticker_sector_cache[ticker]

        if ticker in self._sector_overrides:
            sector = self._sector_overrides[ticker]
            self._ticker_sector_cache[ticker] = sector
            return sector

        # Fallback: fetch from yfinance
        try:
            info = yfinance.Ticker(ticker).info
            sector = info.get("sector")
            if sector:
                self._ticker_sector_cache[ticker] = sector
                return sector
        except Exception:
            pass
        return None

    def _fetch_etf_data(self, etf: str) -> pd.DataFrame | None:
        """Fetch 1 year of daily data for a sector ETF."""
        if etf in self._etf_data_cache:
            return self._etf_data_cache[etf]
        try:
            df = yfinance.download(etf, period="1y", progress=False)
            if df is not None and len(df) >= 60:
                self._etf_data_cache[etf] = df
                return df
        except Exception:
            pass
        return None

    def _compute_rs(self, sector_df: pd.DataFrame,
                    spy_df: pd.DataFrame) -> float:
        """Compute RS of sector ETF vs SPY using same formula as stock RS."""
        sector_close = sector_df["Close"]
        spy_close = spy_df["Close"]

        weighted_sector = 0.0
        weighted_spy = 0.0

        for period, weight in zip(RS_PERIODS, RS_WEIGHTS):
            if len(sector_close) > period and len(spy_close) > period:
                s_ret = (sector_close.iloc[-1] / sector_close.iloc[-period] - 1) * 100
                spy_ret = (spy_close.iloc[-1] / spy_close.iloc[-period] - 1) * 100
                weighted_sector += float(s_ret) * weight
                weighted_spy += float(spy_ret) * weight

        rs_raw = RS_BASELINE + (weighted_sector - weighted_spy)
        return max(1, min(99, rs_raw))

    def _classify(self, rs: float) -> str:
        """Classify sector RS as leading/neutral/lagging."""
        if rs >= SECTOR_LEADING_THRESHOLD:
            return "leading"
        if rs < SECTOR_LAGGING_THRESHOLD:
            return "lagging"
        return "neutral"

    def load_sector_data(self, spy_df: pd.DataFrame):
        """Pre-load all sector ETF data and compute RS scores.

        Call once at start of scan to avoid repeated fetches.
        """
        self._spy_df = spy_df
        for sector_name, etf in SECTOR_ETF_MAP.items():
            etf_df = self._fetch_etf_data(etf)
            if etf_df is not None and spy_df is not None:
                rs = self._compute_rs(etf_df, spy_df)
                self._sector_rs_cache[sector_name] = rs
                self._sector_class_cache[sector_name] = self._classify(rs)

    def get_sector_info(self, ticker: str) -> dict:
        """Get sector RS info for a ticker.

        Returns:
            dict with keys: sector, sector_rs, sector_class
        """
        sector = self._get_sector(ticker)
        if not sector or sector not in self._sector_rs_cache:
            return {
                "sector": sector or "Unknown",
                "sector_rs": None,
                "sector_class": "neutral",
            }
        return {
            "sector": sector,
            "sector_rs": round(self._sector_rs_cache[sector], 1),
            "sector_class": self._sector_class_cache[sector],
        }

    @staticmethod
    def confidence_adjustment(sector_class: str) -> float:
        """Return confidence score adjustment for sector classification."""
        if sector_class == "leading":
            return SECTOR_LEADING_BONUS
        if sector_class == "lagging":
            return SECTOR_LAGGING_PENALTY
        return 0
```

**Step 4: Run tests to verify they pass**

Run: `cd stock_pattern_scanner && python -m pytest tests/test_sector_strength.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add stock_pattern_scanner/sector_strength.py stock_pattern_scanner/tests/test_sector_strength.py
git commit -m "feat(accuracy): add sector relative strength module"
```

---

## Task 5: Add Liquidity Floor to Scan Pipeline

**Files:**
- Modify: `stock_pattern_scanner/pattern_scanner.py` (StockScanner class, around line 753)

**Step 1: Write test**

Add to `tests/test_stock_scanner.py`:

```python
def test_scanner_skips_low_liquidity_tickers(mock_yf_download, mock_spy_data):
    """Tickers with avg dollar volume < $5M should be skipped."""
    # Create data with very low volume
    dates = pd.date_range("2024-01-01", periods=260, freq="B")
    low_vol_data = pd.DataFrame({
        "Open": [10]*260, "High": [10.5]*260, "Low": [9.5]*260,
        "Close": [10]*260, "Volume": [1000]*260,  # $10 * 1000 = $10k/day
    }, index=dates)
    mock_yf_download.return_value = low_vol_data

    from pattern_scanner import StockScanner
    scanner = StockScanner(["LOWVOL"])
    results = scanner.scan()
    assert len(results) == 0
```

**Step 2: Add liquidity check to _analyze_ticker()**

In `pattern_scanner.py`, in the `_analyze_ticker()` method (around line 753), add a dollar volume check after data fetch and moving average calculation but before pattern detection:

```python
# After add_moving_averages (around line 761-762):
# Liquidity floor check
avg_vol_50 = df["AvgVolume50"].iloc[-1]
current_price = df["Close"].iloc[-1]
avg_dollar_volume = avg_vol_50 * current_price
if avg_dollar_volume < MIN_AVG_DOLLAR_VOLUME:
    return []  # skip illiquid ticker
```

Import `MIN_AVG_DOLLAR_VOLUME` from constants at the top of the file.

**Step 3: Track skip count**

Add a counter to the StockScanner class to track skipped tickers. Add `self.skipped_liquidity = 0` in `__init__` and increment when a ticker is skipped.

**Step 4: Run tests**

Run: `cd stock_pattern_scanner && python -m pytest tests/test_stock_scanner.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add stock_pattern_scanner/pattern_scanner.py stock_pattern_scanner/tests/test_stock_scanner.py
git commit -m "feat(accuracy): add liquidity floor ($5M avg dollar volume)"
```

---

## Task 6: Add 50MA > 200MA Hard Gate

**Files:**
- Modify: `stock_pattern_scanner/pattern_scanner.py` (_analyze_ticker, around line 790)

**Step 1: Write test**

Add to `tests/test_pattern_scanner.py`:

```python
def test_death_cross_rejects_pattern():
    """Pattern should be rejected when 50MA < 200MA (death cross)."""
    # This test verifies the gate is applied during pattern evaluation
    from pattern_scanner import PatternDetector
    detector = PatternDetector()
    # Create data where 50MA < 200MA
    # ... (use existing test data patterns but set MA50 < MA200)
    # The pattern should not be returned
```

**Step 2: Add death cross gate in _analyze_ticker()**

In the per-pattern loop (around line 790), after a pattern is detected but before scoring, add:

```python
# 50MA > 200MA gate (death cross rejection)
ma50_val = df["MA50"].iloc[-1]
ma200_val = df["MA200"].iloc[-1]
if pd.notna(ma50_val) and pd.notna(ma200_val) and ma50_val < ma200_val:
    # During corrections, allow detection but flag as warning
    if market_regime_status != "correction":
        self.skipped_death_cross += 1
        continue  # skip this pattern
```

Add `self.skipped_death_cross = 0` to `__init__`.

**Step 3: Run tests**

Run: `cd stock_pattern_scanner && python -m pytest tests/ -v`
Expected: All tests PASS

**Step 4: Commit**

```bash
git add stock_pattern_scanner/pattern_scanner.py stock_pattern_scanner/tests/test_pattern_scanner.py
git commit -m "feat(accuracy): add 50MA > 200MA death cross hard gate"
```

---

## Task 7: Soften Market Regime Correction Behavior

**Files:**
- Modify: `stock_pattern_scanner/market_regime.py`
- Modify: `stock_pattern_scanner/pattern_scanner.py` (scan method, around line 874)

**Step 1: Write test**

Add to `tests/test_market_regime.py`:

```python
def test_evaluate_returns_confidence_penalty():
    """Evaluation result should include confidence_penalty field."""
    # Create SPY data in correction (below 200MA)
    result = regime.evaluate()
    assert "confidence_penalty" in result

def test_correction_has_penalty():
    """Correction status should carry -15 confidence penalty."""
    # ... setup correction conditions
    result = regime.evaluate()
    if result["status"] == "correction":
        assert result["confidence_penalty"] == 15
```

**Step 2: Add confidence_penalty to evaluate() return**

In `market_regime.py`, modify `evaluate()` (around line 58-91) to include a `confidence_penalty` field:

```python
# Add to the return dict:
if status == "correction":
    penalty = REGIME_CORRECTION_CONFIDENCE_PENALTY  # 15
elif status == "uptrend_under_pressure":
    penalty = 0
else:
    penalty = 0

return {
    "status": status,
    "spy_above_200ma": spy_above_200ma,
    "spy_above_50ma": spy_above_50ma,
    "distribution_days": dist_count,
    "ma50_slope_rising": slope_rising,
    "confidence_penalty": penalty,
}
```

**Step 3: Remove the hard block in scan()**

In `pattern_scanner.py`, the `scan()` method (around line 874) currently skips scanning entirely during corrections. Change this to always scan but pass the regime penalty through:

```python
# OLD (around line 874-881):
# if regime["status"] == "correction":
#     return []

# NEW: Store penalty, pass to _analyze_ticker
self._regime_penalty = regime.get("confidence_penalty", 0)
self._regime_status = regime["status"]
```

Apply the penalty after scoring in `_analyze_ticker()`:

```python
# After calculate_confidence (around line 818):
final_score = confidence_score - self._regime_penalty
final_score = max(1, final_score)  # clamp to minimum 1
```

**Step 4: Run tests**

Run: `cd stock_pattern_scanner && python -m pytest tests/ -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add stock_pattern_scanner/market_regime.py stock_pattern_scanner/pattern_scanner.py stock_pattern_scanner/tests/test_market_regime.py
git commit -m "feat(accuracy): soften market regime correction to penalty instead of blocking"
```

---

## Task 8: Grade Volume Confirmation

**Files:**
- Modify: `stock_pattern_scanner/breakout_rules.py`

**Step 1: Write tests**

Add to `tests/test_breakout_rules.py`:

```python
def test_volume_grade_weak():
    """Volume surge <20% should grade as Weak with 0 pts."""
    # ... create data with 10% volume surge
    result = analyzer.evaluate()
    assert result["volume_grade"] == "Weak"

def test_volume_grade_moderate():
    """Volume surge 20-39% should grade as Moderate with 2 pts."""
    # ... create data with 30% volume surge

def test_volume_grade_confirmed():
    """Volume surge 40-79% should grade as Confirmed with 4 pts."""
    # ... create data with 50% volume surge

def test_volume_grade_strong():
    """Volume surge 80-149% should grade as Strong with 5 pts."""
    # ... create data with 100% volume surge

def test_volume_grade_climactic():
    """Volume surge 150%+ should grade as Climactic with 3 pts (warning)."""
    # ... create data with 200% volume surge
```

**Step 2: Modify evaluate() and score()**

In `breakout_rules.py`, update `evaluate()` (line 38) to add `volume_grade` to the return dict and update `score()` (line 98) to use the graded scale:

```python
def _volume_grade(self, surge_pct: float | None) -> tuple[str, float]:
    """Grade volume surge and return (label, score_points)."""
    if surge_pct is None or surge_pct < VOLUME_SURGE_WEAK_PCT:
        return "Weak", SCORE_BREAKOUT_WEAK
    if surge_pct < VOLUME_SURGE_MODERATE_PCT:
        return "Moderate", SCORE_BREAKOUT_MODERATE
    if surge_pct < VOLUME_SURGE_STRONG_PCT:
        return "Confirmed", SCORE_BREAKOUT_CONFIRMED
    if surge_pct < VOLUME_SURGE_CLIMACTIC_PCT:
        return "Strong", SCORE_BREAKOUT_STRONG
    return "Climactic", SCORE_BREAKOUT_CLIMACTIC
```

Add `volume_grade` and `volume_grade_score` to the evaluate() return dict. Update `score()` to return the graded score instead of binary 0/5.

**Step 3: Run tests**

Run: `cd stock_pattern_scanner && python -m pytest tests/test_breakout_rules.py -v`
Expected: All tests PASS

**Step 4: Commit**

```bash
git add stock_pattern_scanner/breakout_rules.py stock_pattern_scanner/tests/test_breakout_rules.py
git commit -m "feat(accuracy): grade volume confirmation on 5-tier scale"
```

---

## Task 9: Rebalance Confidence Scoring and Integrate New Signals

**Files:**
- Modify: `stock_pattern_scanner/pattern_scanner.py` (calculate_confidence, _analyze_ticker)

**Step 1: Write tests for new scoring**

Add to `tests/test_pattern_scanner.py`:

```python
def test_confidence_score_max_is_100():
    """Total confidence score should not exceed 100."""
    # Create ideal pattern with all max scores
    # Verify result <= 100

def test_earnings_momentum_contributes_to_score():
    """Earnings momentum should add up to 10 points."""
    # Verify earnings factor is included in scoring

def test_sector_overlay_reduces_score_for_lagging():
    """Lagging sector should reduce confidence by 10 points."""
    # Verify sector penalty is applied after base scoring
```

**Step 2: Update calculate_confidence()**

In `pattern_scanner.py`, modify `calculate_confidence()` (line 604) to:

1. Use `SCORE_DEPTH_MAX = 10` (was 15) for depth scoring
2. Use `SCORE_VOLUME_PROFILE_MAX = 15` (was 20) for volume scoring, scale the VolumeAnalyzer output from 0-20 to 0-15
3. Add `earnings_momentum` parameter (0-10 points)
4. Keep all other factors the same

```python
def calculate_confidence(self, pattern, df, volume_score, trend_score,
                         rs_rating, breakout_score,
                         earnings_momentum=0.0, sector_adjustment=0.0):
    # ... existing depth, tightness, length, pattern bonus logic
    # with depth max = 10 and volume max = 15

    # Scale volume score from 0-20 to 0-15
    scaled_volume = volume_score * (SCORE_VOLUME_PROFILE_MAX / 20.0)

    # Earnings momentum (0-10)
    earnings_pts = min(earnings_momentum, SCORE_EARNINGS_MOMENTUM_MAX)

    # Sum base score (max 100)
    total = (depth_pts + scaled_volume + ma50_pts + ma200_pts +
             tightness_pts + length_pts + pattern_pts +
             trend_score + rs_pts + breakout_score + earnings_pts)

    # Apply sector overlay (post-adjustment)
    total += sector_adjustment

    return max(1.0, min(100.0, round(total, 1)))
```

**Step 3: Update _analyze_ticker() to pass new parameters**

Wire earnings_momentum and sector_adjustment into the calculate_confidence call.

**Step 4: Run full test suite**

Run: `cd stock_pattern_scanner && python -m pytest tests/ -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add stock_pattern_scanner/pattern_scanner.py stock_pattern_scanner/tests/test_pattern_scanner.py
git commit -m "feat(accuracy): rebalance scoring with earnings momentum and sector overlay"
```

---

## Task 10: Integrate Earnings and Sector into Scan Pipeline

**Files:**
- Modify: `stock_pattern_scanner/pattern_scanner.py` (StockScanner class)

**Step 1: Update StockScanner.__init__() and scan()**

Add earnings analyzer and sector analyzer initialization:

```python
def __init__(self, tickers, max_workers=DEFAULT_MAX_WORKERS):
    self.tickers = tickers
    self.max_workers = max_workers
    self.detector = PatternDetector()
    self.earnings_analyzer = None  # initialized in scan()
    self.sector_analyzer = None    # initialized in scan()
    self.skipped_liquidity = 0
    self.skipped_death_cross = 0
```

In `scan()`, after fetching SPY data:

```python
# Initialize sector analyzer and pre-load sector data
from sector_strength import SectorAnalyzer
self.sector_analyzer = SectorAnalyzer(spy_df=spy_df)
self.sector_analyzer.load_sector_data(spy_df)

# Initialize earnings analyzer
from earnings_analysis import EarningsAnalyzer
api_key = os.environ.get("FMP_API_KEY", "")
self.earnings_analyzer = EarningsAnalyzer(api_key=api_key) if api_key else None
```

**Step 2: Update _analyze_ticker() to use new analyzers**

After pattern detection, before scoring:

```python
# Earnings analysis (if FMP key configured)
earnings_data = {"momentum_score": 0, "flag": None, "days_until": None}
if self.earnings_analyzer:
    cached = db.get_earnings_cache(ticker) if hasattr(self, '_db') else None
    if cached:
        earnings_data = cached
    else:
        earnings_data = self.earnings_analyzer.analyze(ticker, df)
        if hasattr(self, '_db'):
            self._db.save_earnings_cache(ticker, earnings_data)

# Sector analysis
sector_info = {"sector": "Unknown", "sector_rs": None, "sector_class": "neutral"}
if self.sector_analyzer:
    sector_info = self.sector_analyzer.get_sector_info(ticker)

sector_adj = SectorAnalyzer.confidence_adjustment(sector_info["sector_class"])
```

Pass `earnings_momentum=earnings_data["momentum_score"]` and `sector_adjustment=sector_adj` to `calculate_confidence()`.

**Step 3: Update PatternResult dataclass**

Add new fields to PatternResult (around line 114):

```python
# New fields
earnings_flag: str | None = None
earnings_days_until: int | None = None
earnings_momentum_score: float = 0.0
sector: str = "Unknown"
sector_rs: float | None = None
sector_class: str = "neutral"
avg_dollar_volume: float = 0.0
volume_grade: str = "Weak"
regime_penalty: float = 0.0
```

**Step 4: Run full test suite**

Run: `cd stock_pattern_scanner && python -m pytest tests/ -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add stock_pattern_scanner/pattern_scanner.py
git commit -m "feat(accuracy): integrate earnings and sector into scan pipeline"
```

---

## Task 11: Update API Response Format

**Files:**
- Modify: `stock_pattern_scanner/app.py` (results endpoint, around line 141)

**Step 1: Add new fields to results JSON**

In the results endpoint (around line 141-171), update the result dict to include the new PatternResult fields:

```python
# Add to each result dict:
"earnings_flag": r.earnings_flag,
"earnings_days_until": r.earnings_days_until,
"earnings_momentum_score": r.earnings_momentum_score,
"sector": r.sector,
"sector_rs": r.sector_rs,
"sector_class": r.sector_class,
"avg_dollar_volume": r.avg_dollar_volume,
"volume_grade": r.volume_grade,
"regime_penalty": r.regime_penalty,
```

**Step 2: Update market-status endpoint**

In the `/api/market-status` endpoint (around line 88), add the confidence_penalty field to the response:

```python
"confidence_penalty": regime.get("confidence_penalty", 0),
```

**Step 3: Verify app starts**

Run: `cd stock_pattern_scanner && python -c "from app import app; print('OK')"`
Expected: `OK`

**Step 4: Commit**

```bash
git add stock_pattern_scanner/app.py
git commit -m "feat(accuracy): add new fields to API response"
```

---

## Task 12: Update Dashboard — New Columns and Badges

**Files:**
- Modify: `stock_pattern_scanner/templates/dashboard.html`

**Step 1: Add new table header columns**

In the `<tr id="table-head">` (around line 750), add after the Status column:

```html
<th data-col="earnings_flag">Earnings <span class="tooltip-trigger" tabindex="0">i<span class="tooltip-text">Days until next earnings report. "Earnings Soon" (14 days) and "Earnings Imminent" (7 days) warn of upcoming risk. "Beat" means the last quarter beat estimates, boosting confidence.</span></span> <span class="sort-arrow">&#9650;</span></th>
<th data-col="sector">Sector <span class="tooltip-trigger" tabindex="0">i<span class="tooltip-text">The stock's market sector and its relative strength. &uarr; = leading sector (outperforming market, +5 pts). &rarr; = neutral. &darr; = lagging sector (underperforming, -10 pts penalty). Best patterns appear in leading sectors.</span></span> <span class="sort-arrow">&#9650;</span></th>
```

Update the Volume column header to reflect grading:

Replace the existing Vol header tooltip text with:

```
Volume breakout grade. Weak = &lt;20% surge. Mod = 20-39%. &check; = 40-79% (confirmed). Strong = 80-149%. &amp;#9888; Climactic = 150%+ (exhaustion warning, often fails).
```

**Step 2: Update renderTable() row building**

In the `renderTable()` function (around line 1234), add cells for new columns:

```javascript
// Earnings column
var earningsCell = '';
if (r.earnings_flag === 'Earnings Imminent') {
    earningsCell = '<span class="status-badge" style="background:rgba(248,81,73,0.15);color:var(--danger);">' + r.earnings_days_until + 'd</span>';
} else if (r.earnings_flag === 'Earnings Soon') {
    earningsCell = '<span class="status-badge" style="background:rgba(210,153,34,0.15);color:var(--warning);">' + r.earnings_days_until + 'd</span>';
} else if (r.earnings_momentum_score >= 5) {
    earningsCell = '<span class="status-badge" style="background:rgba(63,185,80,0.15);color:var(--success);">Beat</span>';
} else if (r.earnings_days_until != null) {
    earningsCell = r.earnings_days_until + 'd';
} else {
    earningsCell = '-';
}

// Sector column
var sectorArrow = r.sector_class === 'leading' ? '&uarr;' : r.sector_class === 'lagging' ? '&darr;' : '&rarr;';
var sectorColor = r.sector_class === 'leading' ? 'var(--success)' : r.sector_class === 'lagging' ? 'var(--danger)' : 'var(--text-secondary)';
var sectorCell = '<span style="color:' + sectorColor + ';">' + sectorArrow + '</span> ' + esc(r.sector || '');

// Volume grade column (replace binary checkmark)
var volGradeColor = {'Weak':'var(--danger)','Moderate':'var(--warning)','Confirmed':'var(--success)','Strong':'var(--success)','Climactic':'var(--warning)'}[r.volume_grade] || 'var(--text-muted)';
var volGradeLabel = r.volume_grade === 'Confirmed' ? '&#10003;' : esc(r.volume_grade || '-');
var volCell = '<span style="color:' + volGradeColor + ';">' + volGradeLabel + '</span>';
```

**Step 3: Update market banner for softened corrections**

In `fetchMarketStatus()`, update the correction branch to show penalty instead of "Buy signals disabled":

```javascript
} else if (data.status === 'correction') {
    banner.className = 'market-banner correction';
    banner.innerHTML = 'Market: In Correction &mdash; Confidence scores reduced by ' + (data.confidence_penalty || 15) + ' points <span class="tooltip-trigger" tabindex="0">i<span class="tooltip-text tooltip-left">The market is in a downtrend. Patterns detected during corrections have historically lower win rates. Confidence scores are reduced by ' + (data.confidence_penalty || 15) + ' points. Only the strongest setups survive this penalty &mdash; consider waiting for market confirmation.</span></span>';
```

**Step 4: Update progress display**

After scan completes, show skip counts. In the `loadResults()` function, add skip info to the progress area or stats section.

**Step 5: Verify app starts**

Run: `cd stock_pattern_scanner && python -c "from app import app; print('OK')"`
Expected: `OK`

**Step 6: Commit**

```bash
git add stock_pattern_scanner/templates/dashboard.html
git commit -m "feat(accuracy): add earnings, sector, and volume grade columns to dashboard"
```

---

## Task 13: Update Help Panel and Tooltips

**Files:**
- Modify: `stock_pattern_scanner/templates/dashboard.html`

**Step 1: Add "Earnings & Timing" section to help panel**

Insert after the "Reading Your Results" section in the help panel:

```html
<div class="help-section">
    <h3>Earnings &amp; Timing</h3>
    <p>Earnings reports are the single biggest risk for breakout trades. A stock can have a perfect pattern and still drop 20% on a bad earnings surprise.</p>
    <p><strong>What the Earnings column tells you:</strong></p>
    <ul>
        <li><strong>Red badge (Xd)</strong> &mdash; Earnings within 7 days. Very high risk &mdash; consider waiting until after the report.</li>
        <li><strong>Yellow badge (Xd)</strong> &mdash; Earnings within 14 days. Proceed with caution and smaller position sizes.</li>
        <li><strong>Green "Beat" badge</strong> &mdash; The stock beat earnings estimates last quarter. This confirms institutional demand and adds up to 10 points to the confidence score.</li>
        <li><strong>Plain number (Xd)</strong> &mdash; Days until earnings, no immediate concern.</li>
    </ul>
    <p>The ideal setup: buy a breakout <strong>3-5 weeks before earnings</strong> with a recent "Beat" &mdash; you get the momentum tailwind without imminent report risk.</p>
</div>
```

**Step 2: Add "Sector Strength" section to help panel**

```html
<div class="help-section">
    <h3>Sector Strength</h3>
    <p>Markets rotate between sectors. The best breakouts happen in <strong>leading sectors</strong> &mdash; sectors that are outperforming the S&amp;P 500. Patterns in lagging sectors fail roughly twice as often.</p>
    <p><strong>How to read the Sector column:</strong></p>
    <ul>
        <li><strong>&uarr; (green arrow)</strong> &mdash; Leading sector. Outperforming the market. +5 confidence points.</li>
        <li><strong>&rarr; (neutral)</strong> &mdash; In line with the market. No adjustment.</li>
        <li><strong>&darr; (red arrow)</strong> &mdash; Lagging sector. Underperforming. -10 confidence point penalty.</li>
    </ul>
    <p>The sector score is calculated using the same relative strength formula as individual stocks, comparing each of the 11 GICS sector ETFs against the S&amp;P 500 over multiple timeframes.</p>
</div>
```

**Step 3: Update Glossary with new terms**

Add these to the glossary `<dl>` in alphabetical order:

```html
<div class="glossary-term">
    <dt>Climactic Volume</dt>
    <dd>When breakout volume surges 150%+ above average. Counterintuitively, this often signals exhaustion &mdash; everyone who wanted to buy already did. These breakouts have higher failure rates.</dd>
</div>
<div class="glossary-term">
    <dt>Death Cross</dt>
    <dd>When the 50-day moving average crosses below the 200-day moving average. Signals a structural downtrend. Patterns forming during a death cross are filtered out by the scanner.</dd>
</div>
<div class="glossary-term">
    <dt>Dollar Volume</dt>
    <dd>Average daily trading volume in dollars (price &times; shares traded). The scanner requires $5M+ to ensure you can enter and exit positions without moving the price.</dd>
</div>
<div class="glossary-term">
    <dt>Earnings Surprise</dt>
    <dd>The percentage by which actual earnings per share (EPS) exceeded or missed analyst estimates. Positive surprises (beats) confirm institutional demand and add to the confidence score.</dd>
</div>
<div class="glossary-term">
    <dt>Golden Cross</dt>
    <dd>When the 50-day moving average crosses above the 200-day moving average. Signals a structural uptrend. The scanner requires this condition for pattern detection (except during market-wide corrections).</dd>
</div>
<div class="glossary-term">
    <dt>Sector Relative Strength</dt>
    <dd>How a market sector (Technology, Healthcare, etc.) performs compared to the S&amp;P 500. Leading sectors produce more winning breakouts. Measured using the same multi-timeframe formula as individual stock RS.</dd>
</div>
```

**Step 4: Update "Reading Your Results" section**

Add guidance for the new columns to the existing bullet list:

```html
<li><strong>Earnings "Beat" badge</strong> = recent earnings beat, confirming institutional demand</li>
<li><strong>Sector &uarr;</strong> = stock is in a leading sector, higher win probability</li>
<li><strong>Volume "Strong"</strong> = breakout backed by heavy institutional buying (80%+ surge)</li>
```

**Step 5: Verify app starts**

Run: `cd stock_pattern_scanner && python -c "from app import app; print('OK')"`
Expected: `OK`

**Step 6: Commit**

```bash
git add stock_pattern_scanner/templates/dashboard.html
git commit -m "feat(accuracy): update help panel with earnings, sector, and volume guide"
```

---

## Task 14: Run Full Test Suite and Integration Test

**Step 1: Run all tests**

Run: `cd stock_pattern_scanner && python -m pytest tests/ -v`
Expected: All tests PASS (existing 82 + new tests)

**Step 2: Verify app starts and all routes work**

Run: `cd stock_pattern_scanner && python -c "from app import app; print('Routes:', [r.path for r in app.routes])"`
Expected: All existing routes present

**Step 3: Verify FMP configuration**

Run: `cd stock_pattern_scanner && python -c "from earnings_analysis import EarningsAnalyzer; a = EarningsAnalyzer(); print('EarningsAnalyzer OK')"`

Run: `cd stock_pattern_scanner && python -c "from sector_strength import SectorAnalyzer; a = SectorAnalyzer(); print('SectorAnalyzer OK')"`

**Step 4: Commit if any fixes were needed**

```bash
git add -A
git commit -m "fix(accuracy): resolve issues from integration testing"
```

---

## Verification Checklist

After all tasks:

- [ ] `python -m pytest tests/ -v` — all tests pass
- [ ] App imports cleanly: `python -c "from app import app"`
- [ ] Dashboard loads with new Earnings and Sector columns
- [ ] Volume column shows graded labels instead of checkmarks
- [ ] Market correction shows penalty message instead of "Buy signals disabled"
- [ ] Help panel has "Earnings & Timing" and "Sector Strength" sections
- [ ] Glossary has 6 new terms (Climactic Volume through Sector RS)
- [ ] Tooltips on all new table headers
- [ ] FMP API key configurable via `FMP_API_KEY` environment variable
- [ ] Scanner skips tickers with < $5M avg dollar volume
- [ ] Scanner skips patterns with death cross (50MA < 200MA)
- [ ] Confidence scores rebalanced: depth=10, volume=15, earnings=10
- [ ] Sector overlay: +5 leading, -10 lagging
- [ ] Correction regime: -15 penalty (not blocking)

Files created:
- `stock_pattern_scanner/earnings_analysis.py`
- `stock_pattern_scanner/sector_strength.py`
- `stock_pattern_scanner/tests/test_earnings_analysis.py`
- `stock_pattern_scanner/tests/test_sector_strength.py`

Files modified:
- `stock_pattern_scanner/constants.py`
- `stock_pattern_scanner/database.py`
- `stock_pattern_scanner/pattern_scanner.py`
- `stock_pattern_scanner/breakout_rules.py`
- `stock_pattern_scanner/market_regime.py`
- `stock_pattern_scanner/app.py`
- `stock_pattern_scanner/templates/dashboard.html`

No new runtime dependencies (requests is already available). One new external service: FMP API (free key required, graceful degradation if absent).
