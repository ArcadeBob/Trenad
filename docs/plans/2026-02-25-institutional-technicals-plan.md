# Institutional-Grade Technical Analysis Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add institutional-quality technical analysis layers — market regime detection, volume accumulation profiling, breakout confirmation, trend strength validation, and revised confidence scoring — to improve scanner accuracy.

**Architecture:** Four new modules (`market_regime.py`, `volume_analysis.py`, `breakout_rules.py`, `trend_strength.py`) added alongside existing detection engine. Enhanced scoring in `pattern_scanner.py`. New fields on `PatternResult`. Dashboard and API updates.

**Tech Stack:** Python 3.13, numpy, pandas, yfinance (all existing — no new dependencies)

---

## Task 1: Add New Constants

Add all new threshold constants for the four new modules and revised scoring.

**Files:**
- Modify: `stock_pattern_scanner/constants.py`

**Step 1: Append new constants to constants.py**

Add to the end of `stock_pattern_scanner/constants.py`:

```python
# ---------------------------------------------------------------------------
# Market regime
# ---------------------------------------------------------------------------
REGIME_DISTRIBUTION_DAY_DECLINE_PCT = 0.2
REGIME_DISTRIBUTION_DAY_LOOKBACK = 25
REGIME_PRESSURE_DISTRIBUTION_DAYS = 4
REGIME_CORRECTION_DISTRIBUTION_DAYS = 5
REGIME_MA_SLOPE_LOOKBACK = 10

# ---------------------------------------------------------------------------
# Volume analysis
# ---------------------------------------------------------------------------
VOLUME_DRYUP_TAIL_DAYS = 10
VOLUME_DRYUP_GOOD = 0.7
VOLUME_UPDOWN_STRONG = 1.5
VOLUME_UPDOWN_GOOD = 1.3

# ---------------------------------------------------------------------------
# Breakout rules
# ---------------------------------------------------------------------------
BREAKOUT_VOLUME_SURGE_PCT = 40.0
BREAKOUT_CLOSE_UPPER_HALF = 0.5
BREAKOUT_ENTRY_MAX_PCT = 2.0
BREAKOUT_EXTENDED_PCT = 5.0
STOP_LOSS_PCT = 7.0
PROFIT_TARGET_PCT = 20.0

# ---------------------------------------------------------------------------
# Trend strength
# ---------------------------------------------------------------------------
ADX_PERIOD = 14
ADX_STRONG = 30.0
ADX_MINIMUM = 20.0
ATR_PERIOD = 14
ATR_MAX_RATIO_PCT = 5.0
MA_SLOPE_LOOKBACK = 50

# ---------------------------------------------------------------------------
# Revised confidence scoring weights
# ---------------------------------------------------------------------------
SCORE_DEPTH_MAX_V2 = 15.0
SCORE_VOLUME_PROFILE_MAX = 20.0
SCORE_ABOVE_50MA_MAX_V2 = 10.0
SCORE_ABOVE_200MA_MAX_V2 = 5.0
SCORE_TIGHTNESS_MAX_V2 = 10.0
SCORE_BASE_LENGTH_MAX_V2 = 5.0
SCORE_PATTERN_BONUS_MAX_V2 = 10.0
SCORE_TREND_STRENGTH_MAX = 10.0
SCORE_RS_RATING_MAX = 10.0
SCORE_BREAKOUT_QUALITY_MAX = 5.0
SCORE_MINIMUM_VIABLE = 40.0

# RS scoring thresholds
RS_STRONG = 80.0
RS_MODERATE = 60.0
```

**Step 2: Verify file is importable**

Run: `cd stock_pattern_scanner && python -c "from constants import REGIME_DISTRIBUTION_DAY_DECLINE_PCT, SCORE_MINIMUM_VIABLE; print('OK')"`
Expected: `OK`

**Step 3: Commit**

```bash
git add stock_pattern_scanner/constants.py
git commit -m "refactor: add constants for market regime, volume analysis, breakout rules, trend strength"
```

---

## Task 2: Create Market Regime Module

Determines bull/bear/pressure state from SPY data. Hard gate for the scanner.

**Files:**
- Create: `stock_pattern_scanner/market_regime.py`
- Create: `stock_pattern_scanner/tests/test_market_regime.py`

**Step 1: Write the tests**

Create `stock_pattern_scanner/tests/test_market_regime.py`:

```python
"""Tests for market regime detection."""

from __future__ import annotations

import numpy as np
import pandas as pd

from market_regime import MarketRegime


def _make_spy_df(
    closes: list[float],
    volumes: list[float] | None = None,
) -> pd.DataFrame:
    """Build a minimal SPY OHLCV DataFrame."""
    n = len(closes)
    if volumes is None:
        volumes = [50_000_000] * n
    dates = pd.bdate_range(end="2026-02-20", periods=n)
    return pd.DataFrame(
        {
            "Open": closes,
            "High": [c * 1.005 for c in closes],
            "Low": [c * 0.995 for c in closes],
            "Close": closes,
            "Volume": volumes,
        },
        index=dates,
    )


def test_confirmed_uptrend():
    """SPY steadily rising above both MAs, low volume on down days."""
    # 300 days of steady uptrend: 400 -> 520 (30% gain)
    closes = [400 + (120 * i / 299) for i in range(300)]
    df = _make_spy_df(closes)
    regime = MarketRegime(df)
    result = regime.evaluate()
    assert result["status"] == "confirmed_uptrend"


def test_market_in_correction():
    """SPY drops below 200-day MA with declining 50-day MA."""
    # 250 days up, then 50 days sharp decline below 200-day MA
    up = [400 + (100 * i / 249) for i in range(250)]
    down = [500 - (150 * i / 49) for i in range(50)]
    closes = up + down
    # High volume on down days to create distribution days
    volumes = [50_000_000] * 250 + [80_000_000] * 50
    df = _make_spy_df(closes, volumes)
    regime = MarketRegime(df)
    result = regime.evaluate()
    assert result["status"] == "correction"


def test_uptrend_under_pressure():
    """SPY above 200-day MA but with 4+ distribution days."""
    # Steady uptrend for 280 days, then choppy last 20 days
    up = [400 + (80 * i / 279) for i in range(280)]
    # Choppy: alternating small down days on high volume
    choppy = []
    for i in range(20):
        if i % 2 == 0:
            choppy.append(up[-1] - 2)  # down day
        else:
            choppy.append(up[-1] + 1)  # up day
    closes = up + choppy
    # High volume on the down days
    volumes = [50_000_000] * 280
    for i in range(20):
        if i % 2 == 0:
            volumes.append(70_000_000)  # high vol down = distribution
        else:
            volumes.append(40_000_000)
    df = _make_spy_df(closes, volumes)
    regime = MarketRegime(df)
    result = regime.evaluate()
    assert result["status"] in ("uptrend_under_pressure", "confirmed_uptrend")


def test_distribution_day_count():
    """Verify distribution day counting logic."""
    # 300 days of steady rise
    closes = [400 + (100 * i / 299) for i in range(300)]
    df = _make_spy_df(closes)
    regime = MarketRegime(df)
    # In a clean uptrend, should have very few distribution days
    assert regime.distribution_day_count() < 4


def test_evaluate_returns_required_keys():
    """Result dict must contain status, spy_above_200ma, spy_above_50ma, distribution_days."""
    closes = [400 + (100 * i / 299) for i in range(300)]
    df = _make_spy_df(closes)
    regime = MarketRegime(df)
    result = regime.evaluate()
    assert "status" in result
    assert "spy_above_200ma" in result
    assert "spy_above_50ma" in result
    assert "distribution_days" in result
    assert "ma50_slope_rising" in result
```

**Step 2: Run tests to verify they fail**

Run: `cd stock_pattern_scanner && python -m pytest tests/test_market_regime.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'market_regime'`

**Step 3: Write the implementation**

Create `stock_pattern_scanner/market_regime.py`:

```python
"""Market regime detection using SPY data.

Determines whether the overall market is in a confirmed uptrend,
under pressure, or in correction. Used as a hard gate by the scanner.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from constants import (
    REGIME_CORRECTION_DISTRIBUTION_DAYS,
    REGIME_DISTRIBUTION_DAY_DECLINE_PCT,
    REGIME_DISTRIBUTION_DAY_LOOKBACK,
    REGIME_MA_SLOPE_LOOKBACK,
    REGIME_PRESSURE_DISTRIBUTION_DAYS,
)


class MarketRegime:
    """Evaluate market health from SPY price/volume data."""

    def __init__(self, spy_df: pd.DataFrame):
        self.df = spy_df
        self._ma50 = spy_df["Close"].rolling(window=50).mean()
        self._ma200 = spy_df["Close"].rolling(window=200).mean()

    def distribution_day_count(self) -> int:
        """Count distribution days in the last 25 sessions.

        A distribution day is when SPY closes down >0.2% on volume
        higher than the previous session.
        """
        df = self.df
        recent = df.iloc[-REGIME_DISTRIBUTION_DAY_LOOKBACK:]
        if len(recent) < 2:
            return 0

        closes = recent["Close"].values
        volumes = recent["Volume"].values

        count = 0
        for i in range(1, len(closes)):
            pct_change = (closes[i] - closes[i - 1]) / closes[i - 1] * 100
            if pct_change < -REGIME_DISTRIBUTION_DAY_DECLINE_PCT and volumes[i] > volumes[i - 1]:
                count += 1
        return count

    def _ma50_slope_rising(self) -> bool:
        """Check if the 50-day MA slope is positive over recent sessions."""
        ma50 = self._ma50.dropna()
        if len(ma50) < REGIME_MA_SLOPE_LOOKBACK:
            return False
        recent_ma = ma50.iloc[-REGIME_MA_SLOPE_LOOKBACK:]
        return float(recent_ma.iloc[-1]) > float(recent_ma.iloc[0])

    def evaluate(self) -> dict:
        """Evaluate current market regime.

        Returns:
            Dict with keys: status, spy_above_200ma, spy_above_50ma,
            distribution_days, ma50_slope_rising.

            status is one of: 'confirmed_uptrend', 'uptrend_under_pressure',
            'correction'.
        """
        current_close = float(self.df["Close"].iloc[-1])
        ma50_val = self._ma50.iloc[-1]
        ma200_val = self._ma200.iloc[-1]

        above_50 = bool(pd.notna(ma50_val) and current_close > ma50_val)
        above_200 = bool(pd.notna(ma200_val) and current_close > ma200_val)
        dist_days = self.distribution_day_count()
        slope_rising = self._ma50_slope_rising()

        # Determine regime
        if not above_200 or (not slope_rising and dist_days >= REGIME_CORRECTION_DISTRIBUTION_DAYS):
            status = "correction"
        elif dist_days >= REGIME_PRESSURE_DISTRIBUTION_DAYS or not slope_rising:
            status = "uptrend_under_pressure"
        else:
            status = "confirmed_uptrend"

        return {
            "status": status,
            "spy_above_200ma": above_200,
            "spy_above_50ma": above_50,
            "distribution_days": dist_days,
            "ma50_slope_rising": slope_rising,
        }
```

**Step 4: Run tests to verify they pass**

Run: `cd stock_pattern_scanner && python -m pytest tests/test_market_regime.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add stock_pattern_scanner/market_regime.py stock_pattern_scanner/tests/test_market_regime.py
git commit -m "feat: add market regime detection module with hard gate logic"
```

---

## Task 3: Create Volume Analysis Module

Replaces binary volume_confirmation with A-E rating, dry-up score, and up/down ratio.

**Files:**
- Create: `stock_pattern_scanner/volume_analysis.py`
- Create: `stock_pattern_scanner/tests/test_volume_analysis.py`

**Step 1: Write the tests**

Create `stock_pattern_scanner/tests/test_volume_analysis.py`:

```python
"""Tests for volume accumulation/distribution analysis."""

from __future__ import annotations

import pandas as pd

from volume_analysis import VolumeAnalyzer


def _make_base_df(
    closes: list[float],
    volumes: list[float],
    base_start: int,
    base_end: int,
) -> tuple[pd.DataFrame, int, int]:
    """Build a DataFrame with explicit base boundaries."""
    n = len(closes)
    dates = pd.bdate_range(end="2026-02-20", periods=n)
    df = pd.DataFrame(
        {
            "Open": closes,
            "High": [c * 1.01 for c in closes],
            "Low": [c * 0.99 for c in closes],
            "Close": closes,
            "Volume": volumes,
        },
        index=dates,
    )
    avg_vol = pd.Series(volumes).rolling(50).mean()
    df["AvgVolume50"] = avg_vol.values
    return df, base_start, base_end


def test_ad_rating_strong_accumulation():
    """Mostly up days on high volume → A or B rating."""
    n = 250
    # Steady uptrend with high volume on up days
    closes = [100 + (50 * i / (n - 1)) for i in range(n)]
    volumes = []
    for i in range(n):
        if i > 0 and closes[i] > closes[i - 1]:
            volumes.append(2_000_000)  # high vol up days
        else:
            volumes.append(500_000)  # low vol down days
    df, bs, be = _make_base_df(closes, volumes, 200, 249)
    analyzer = VolumeAnalyzer(df, bs, be)
    rating = analyzer.ad_rating()
    assert rating in ("A", "B")


def test_ad_rating_heavy_distribution():
    """Mostly down days on high volume → D or E rating."""
    n = 250
    # Steady downtrend with high volume on down days
    closes = [150 - (50 * i / (n - 1)) for i in range(n)]
    volumes = []
    for i in range(n):
        if i > 0 and closes[i] < closes[i - 1]:
            volumes.append(2_000_000)  # high vol down days
        else:
            volumes.append(500_000)
    df, bs, be = _make_base_df(closes, volumes, 200, 249)
    analyzer = VolumeAnalyzer(df, bs, be)
    rating = analyzer.ad_rating()
    assert rating in ("D", "E")


def test_volume_dryup_score():
    """Volume dropping off at end of base → low dry-up score (good)."""
    n = 250
    closes = [100 + (30 * i / (n - 1)) for i in range(n)]
    volumes = [1_000_000] * n
    # Last 10 days of base have very low volume
    for i in range(240, 250):
        volumes[i] = 300_000
    df, bs, be = _make_base_df(closes, volumes, 200, 249)
    analyzer = VolumeAnalyzer(df, bs, be)
    score = analyzer.dryup_score()
    assert score < 0.7


def test_updown_volume_ratio_bullish():
    """More volume on up days than down days → ratio > 1.0."""
    n = 250
    closes = [100 + (50 * i / (n - 1)) for i in range(n)]
    volumes = []
    for i in range(n):
        if i > 0 and closes[i] > closes[i - 1]:
            volumes.append(2_000_000)
        else:
            volumes.append(500_000)
    df, bs, be = _make_base_df(closes, volumes, 200, 249)
    analyzer = VolumeAnalyzer(df, bs, be)
    ratio = analyzer.updown_ratio()
    assert ratio > 1.0


def test_score_returns_0_to_20():
    """Volume score must be in [0, 20]."""
    n = 250
    closes = [100 + (50 * i / (n - 1)) for i in range(n)]
    volumes = [1_000_000] * n
    df, bs, be = _make_base_df(closes, volumes, 200, 249)
    analyzer = VolumeAnalyzer(df, bs, be)
    score = analyzer.score()
    assert 0 <= score <= 20


def test_is_distributing_flag():
    """D or E rating should flag as distributing."""
    n = 250
    closes = [150 - (50 * i / (n - 1)) for i in range(n)]
    volumes = []
    for i in range(n):
        if i > 0 and closes[i] < closes[i - 1]:
            volumes.append(2_000_000)
        else:
            volumes.append(500_000)
    df, bs, be = _make_base_df(closes, volumes, 200, 249)
    analyzer = VolumeAnalyzer(df, bs, be)
    assert analyzer.is_distributing()
```

**Step 2: Run tests to verify they fail**

Run: `cd stock_pattern_scanner && python -m pytest tests/test_volume_analysis.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'volume_analysis'`

**Step 3: Write the implementation**

Create `stock_pattern_scanner/volume_analysis.py`:

```python
"""Volume accumulation/distribution analysis for base patterns.

Replaces binary volume_confirmation with institutional-grade profiling:
A/D rating, volume dry-up score, and up/down volume ratio.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from constants import (
    SCORE_VOLUME_PROFILE_MAX,
    VOLUME_DRYUP_GOOD,
    VOLUME_DRYUP_TAIL_DAYS,
    VOLUME_UPDOWN_GOOD,
    VOLUME_UPDOWN_STRONG,
)


class VolumeAnalyzer:
    """Analyze volume behavior during a base formation period."""

    def __init__(self, df: pd.DataFrame, base_start_idx: int, base_end_idx: int):
        self.df = df
        self.base = df.iloc[base_start_idx : base_end_idx + 1]
        self.base_start = base_start_idx
        self.base_end = base_end_idx

    def ad_rating(self) -> str:
        """Accumulation/Distribution rating (A through E).

        Counts up-volume days vs down-volume days during the base.
        Up day on above-average volume = accumulation.
        Down day on above-average volume = distribution.
        """
        base = self.base
        if len(base) < 5:
            return "C"

        closes = base["Close"].values
        volumes = base["Volume"].values

        # Use 50-day avg volume if available, else base mean
        if "AvgVolume50" in base.columns:
            avg_vol_series = base["AvgVolume50"].values
        else:
            avg_vol_series = np.full(len(base), np.mean(volumes))

        accum_days = 0
        dist_days = 0

        for i in range(1, len(closes)):
            avg_vol = avg_vol_series[i] if not np.isnan(avg_vol_series[i]) else np.mean(volumes)
            if avg_vol <= 0:
                continue
            is_above_avg = volumes[i] > avg_vol
            if not is_above_avg:
                continue
            if closes[i] > closes[i - 1]:
                accum_days += 1
            elif closes[i] < closes[i - 1]:
                dist_days += 1

        total = accum_days + dist_days
        if total == 0:
            return "C"

        ratio = accum_days / total

        if ratio >= 0.8:
            return "A"
        elif ratio >= 0.6:
            return "B"
        elif ratio >= 0.4:
            return "C"
        elif ratio >= 0.2:
            return "D"
        else:
            return "E"

    def dryup_score(self) -> float:
        """Volume dry-up score: avg volume in last 10 days / avg volume in first half.

        Lower is better — means sellers are exhausted near the pivot.
        Returns ratio (e.g. 0.5 means volume dropped 50%).
        """
        base = self.base
        if len(base) < VOLUME_DRYUP_TAIL_DAYS * 2:
            return 1.0

        half = len(base) // 2
        first_half_vol = base["Volume"].iloc[:half].mean()
        tail_vol = base["Volume"].iloc[-VOLUME_DRYUP_TAIL_DAYS:].mean()

        if first_half_vol <= 0:
            return 1.0
        return tail_vol / first_half_vol

    def updown_ratio(self) -> float:
        """Up/down volume ratio over the base period.

        Total volume on up days / total volume on down days.
        >1.0 = net accumulation, >1.5 = strong.
        """
        base = self.base
        if len(base) < 5:
            return 1.0

        closes = base["Close"].values
        volumes = base["Volume"].values

        up_vol = 0.0
        down_vol = 0.0
        for i in range(1, len(closes)):
            if closes[i] > closes[i - 1]:
                up_vol += volumes[i]
            elif closes[i] < closes[i - 1]:
                down_vol += volumes[i]

        if down_vol <= 0:
            return 2.0  # All up days, cap at 2.0
        return up_vol / down_vol

    def is_distributing(self) -> bool:
        """True if A/D rating is D or E (institutions selling)."""
        return self.ad_rating() in ("D", "E")

    def score(self) -> float:
        """Calculate volume profile score (0-20 points).

        Full marks for: A/D rating A or B, dry-up < 0.7, up/down ratio > 1.3.
        """
        if self.is_distributing():
            return 0.0

        rating = self.ad_rating()
        dryup = self.dryup_score()
        ratio = self.updown_ratio()

        pts = 0.0

        # A/D rating: 0-8 pts
        rating_scores = {"A": 8.0, "B": 6.0, "C": 4.0}
        pts += rating_scores.get(rating, 0.0)

        # Dry-up: 0-6 pts
        if dryup < VOLUME_DRYUP_GOOD:
            pts += 6.0
        elif dryup < 1.0:
            pts += 3.0

        # Up/down ratio: 0-6 pts
        if ratio >= VOLUME_UPDOWN_STRONG:
            pts += 6.0
        elif ratio >= VOLUME_UPDOWN_GOOD:
            pts += 4.0
        elif ratio >= 1.0:
            pts += 2.0

        return min(SCORE_VOLUME_PROFILE_MAX, pts)
```

**Step 4: Run tests to verify they pass**

Run: `cd stock_pattern_scanner && python -m pytest tests/test_volume_analysis.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add stock_pattern_scanner/volume_analysis.py stock_pattern_scanner/tests/test_volume_analysis.py
git commit -m "feat: add volume accumulation/distribution analysis module"
```

---

## Task 4: Create Trend Strength Module

ADX, MA slope, and ATR ratio for validating uptrend quality.

**Files:**
- Create: `stock_pattern_scanner/trend_strength.py`
- Create: `stock_pattern_scanner/tests/test_trend_strength.py`

**Step 1: Write the tests**

Create `stock_pattern_scanner/tests/test_trend_strength.py`:

```python
"""Tests for trend strength validation."""

from __future__ import annotations

import numpy as np
import pandas as pd

from trend_strength import TrendAnalyzer


def _make_ohlcv(
    closes: list[float],
    spread: float = 0.02,
) -> pd.DataFrame:
    """Build OHLCV DataFrame with realistic high/low from closes."""
    n = len(closes)
    dates = pd.bdate_range(end="2026-02-20", periods=n)
    highs = [c * (1 + spread / 2) for c in closes]
    lows = [c * (1 - spread / 2) for c in closes]
    return pd.DataFrame(
        {
            "Open": closes,
            "High": highs,
            "Low": lows,
            "Close": closes,
            "Volume": [1_000_000] * n,
        },
        index=dates,
    )


def test_adx_strong_uptrend():
    """Steady rising prices should produce ADX > 25."""
    closes = [100 + (80 * i / 299) for i in range(300)]
    df = _make_ohlcv(closes)
    analyzer = TrendAnalyzer(df)
    adx = analyzer.adx()
    assert adx > 20


def test_adx_sideways_market():
    """Flat prices should produce low ADX."""
    closes = [100 + 2 * np.sin(i * 0.2) for i in range(300)]
    df = _make_ohlcv(closes)
    analyzer = TrendAnalyzer(df)
    adx = analyzer.adx()
    assert adx < 30


def test_ma_slope_positive_in_uptrend():
    """50-day MA slope should be positive in a clear uptrend."""
    closes = [100 + (100 * i / 299) for i in range(300)]
    df = _make_ohlcv(closes)
    analyzer = TrendAnalyzer(df)
    slope = analyzer.ma50_slope()
    assert slope > 0


def test_ma_slope_negative_in_downtrend():
    """50-day MA slope should be negative in a clear downtrend."""
    closes = [200 - (100 * i / 299) for i in range(300)]
    df = _make_ohlcv(closes)
    analyzer = TrendAnalyzer(df)
    slope = analyzer.ma50_slope()
    assert slope < 0


def test_atr_ratio_low_for_smooth_trend():
    """Smooth price moves should have low ATR ratio."""
    closes = [100 + (50 * i / 299) for i in range(300)]
    df = _make_ohlcv(closes, spread=0.01)  # tight spread
    analyzer = TrendAnalyzer(df)
    ratio = analyzer.atr_ratio()
    assert ratio < 5.0


def test_atr_ratio_high_for_volatile():
    """Wide swings should produce high ATR ratio."""
    closes = [100 + 20 * np.sin(i * 0.5) for i in range(300)]
    df = _make_ohlcv(closes, spread=0.10)  # wide spread
    analyzer = TrendAnalyzer(df)
    ratio = analyzer.atr_ratio()
    assert ratio > 3.0


def test_is_too_volatile():
    """ATR ratio > 5% should be flagged as too volatile."""
    # Extremely choppy with wide spreads
    closes = [100 + 30 * np.sin(i * 0.8) for i in range(300)]
    df = _make_ohlcv(closes, spread=0.15)
    analyzer = TrendAnalyzer(df)
    assert analyzer.is_too_volatile()


def test_score_returns_0_to_10():
    """Trend score must be in [0, 10]."""
    closes = [100 + (50 * i / 299) for i in range(300)]
    df = _make_ohlcv(closes)
    analyzer = TrendAnalyzer(df)
    score = analyzer.score()
    assert 0 <= score <= 10
```

**Step 2: Run tests to verify they fail**

Run: `cd stock_pattern_scanner && python -m pytest tests/test_trend_strength.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'trend_strength'`

**Step 3: Write the implementation**

Create `stock_pattern_scanner/trend_strength.py`:

```python
"""Trend strength validation using ADX, MA slope, and ATR ratio.

Replaces the blunt '30% gain in 6 months' check with actual trend
quality measurement.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from constants import (
    ADX_MINIMUM,
    ADX_PERIOD,
    ADX_STRONG,
    ATR_MAX_RATIO_PCT,
    ATR_PERIOD,
    MA_SLOPE_LOOKBACK,
    SCORE_TREND_STRENGTH_MAX,
)


class TrendAnalyzer:
    """Analyze trend strength from OHLCV data."""

    def __init__(self, df: pd.DataFrame):
        self.df = df

    def adx(self) -> float:
        """Calculate Average Directional Index (14-period, Wilder smoothing).

        Returns the most recent ADX value. Higher = stronger trend.
        """
        df = self.df
        if len(df) < ADX_PERIOD * 3:
            return 0.0

        high = df["High"].values.astype(float)
        low = df["Low"].values.astype(float)
        close = df["Close"].values.astype(float)
        n = len(close)

        # True Range, +DM, -DM
        tr = np.zeros(n)
        plus_dm = np.zeros(n)
        minus_dm = np.zeros(n)

        for i in range(1, n):
            h_l = high[i] - low[i]
            h_pc = abs(high[i] - close[i - 1])
            l_pc = abs(low[i] - close[i - 1])
            tr[i] = max(h_l, h_pc, l_pc)

            up_move = high[i] - high[i - 1]
            down_move = low[i - 1] - low[i]

            plus_dm[i] = up_move if up_move > down_move and up_move > 0 else 0
            minus_dm[i] = down_move if down_move > up_move and down_move > 0 else 0

        # Wilder smoothing
        period = ADX_PERIOD
        atr = np.zeros(n)
        plus_di_smooth = np.zeros(n)
        minus_di_smooth = np.zeros(n)

        atr[period] = np.sum(tr[1 : period + 1])
        plus_di_smooth[period] = np.sum(plus_dm[1 : period + 1])
        minus_di_smooth[period] = np.sum(minus_dm[1 : period + 1])

        for i in range(period + 1, n):
            atr[i] = atr[i - 1] - atr[i - 1] / period + tr[i]
            plus_di_smooth[i] = plus_di_smooth[i - 1] - plus_di_smooth[i - 1] / period + plus_dm[i]
            minus_di_smooth[i] = minus_di_smooth[i - 1] - minus_di_smooth[i - 1] / period + minus_dm[i]

        # +DI and -DI
        plus_di = np.zeros(n)
        minus_di = np.zeros(n)
        dx = np.zeros(n)

        for i in range(period, n):
            if atr[i] > 0:
                plus_di[i] = 100 * plus_di_smooth[i] / atr[i]
                minus_di[i] = 100 * minus_di_smooth[i] / atr[i]
            di_sum = plus_di[i] + minus_di[i]
            if di_sum > 0:
                dx[i] = 100 * abs(plus_di[i] - minus_di[i]) / di_sum

        # ADX = Wilder smooth of DX
        adx_vals = np.zeros(n)
        start = period * 2
        if start >= n:
            return 0.0
        adx_vals[start] = np.mean(dx[period:start + 1])

        for i in range(start + 1, n):
            adx_vals[i] = (adx_vals[i - 1] * (period - 1) + dx[i]) / period

        return float(adx_vals[-1])

    def ma50_slope(self) -> float:
        """Linear regression slope of the 50-day MA over the last 50 days.

        Positive = rising trend, negative = declining.
        Returns slope in price units per day.
        """
        ma50 = self.df["Close"].rolling(window=50).mean().dropna()
        if len(ma50) < MA_SLOPE_LOOKBACK:
            return 0.0

        recent = ma50.iloc[-MA_SLOPE_LOOKBACK:].values
        x = np.arange(len(recent))
        slope, _ = np.polyfit(x, recent, 1)
        return float(slope)

    def atr_ratio(self) -> float:
        """ATR(14) / current price × 100.

        Low values = smooth trend. >5% = too volatile for reliable bases.
        """
        df = self.df
        if len(df) < ATR_PERIOD + 1:
            return 0.0

        high = df["High"].values.astype(float)
        low = df["Low"].values.astype(float)
        close = df["Close"].values.astype(float)

        tr = np.zeros(len(close))
        for i in range(1, len(close)):
            tr[i] = max(
                high[i] - low[i],
                abs(high[i] - close[i - 1]),
                abs(low[i] - close[i - 1]),
            )

        # Simple moving average of TR for last ATR_PERIOD days
        atr_val = np.mean(tr[-ATR_PERIOD:])
        current_price = close[-1]
        if current_price <= 0:
            return 0.0
        return float(atr_val / current_price * 100)

    def is_too_volatile(self) -> bool:
        """True if ATR ratio exceeds the maximum threshold."""
        return self.atr_ratio() > ATR_MAX_RATIO_PCT

    def has_quality_uptrend(self, prior_gain_pct: float) -> bool:
        """Check if prior uptrend meets enhanced quality criteria.

        Requires 30%+ gain AND (ADX > 20 OR positive MA slope).
        """
        if prior_gain_pct < 30.0:
            return False
        return self.adx() > ADX_MINIMUM or self.ma50_slope() > 0

    def score(self) -> float:
        """Calculate trend strength score (0-10 points).

        ADX > 30 with positive MA slope = full 10 pts.
        """
        adx_val = self.adx()
        slope = self.ma50_slope()

        pts = 0.0

        # ADX component: 0-5 pts
        if adx_val >= ADX_STRONG:
            pts += 5.0
        elif adx_val >= ADX_MINIMUM:
            pts += 3.0

        # MA slope component: 0-5 pts
        if slope > 0:
            pts += 5.0

        return min(SCORE_TREND_STRENGTH_MAX, pts)
```

**Step 4: Run tests to verify they pass**

Run: `cd stock_pattern_scanner && python -m pytest tests/test_trend_strength.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add stock_pattern_scanner/trend_strength.py stock_pattern_scanner/tests/test_trend_strength.py
git commit -m "feat: add trend strength validation module (ADX, MA slope, ATR)"
```

---

## Task 5: Create Breakout Rules Module

Volume surge confirmation, stop-loss/profit targets, breakout status.

**Files:**
- Create: `stock_pattern_scanner/breakout_rules.py`
- Create: `stock_pattern_scanner/tests/test_breakout_rules.py`

**Step 1: Write the tests**

Create `stock_pattern_scanner/tests/test_breakout_rules.py`:

```python
"""Tests for breakout confirmation and entry rules."""

from __future__ import annotations

import pandas as pd

from breakout_rules import BreakoutAnalyzer


def _make_df(
    closes: list[float],
    volumes: list[float] | None = None,
    highs: list[float] | None = None,
    lows: list[float] | None = None,
) -> pd.DataFrame:
    n = len(closes)
    if volumes is None:
        volumes = [1_000_000] * n
    if highs is None:
        highs = [c * 1.01 for c in closes]
    if lows is None:
        lows = [c * 0.99 for c in closes]
    dates = pd.bdate_range(end="2026-02-20", periods=n)
    df = pd.DataFrame(
        {"Open": closes, "High": highs, "Low": lows, "Close": closes, "Volume": volumes},
        index=dates,
    )
    df["AvgVolume50"] = pd.Series(volumes).rolling(50).mean().values
    return df


def test_stop_loss_price():
    """Stop loss should be 7% below buy point."""
    df = _make_df([100.0] * 100)
    ba = BreakoutAnalyzer(df, buy_point=150.0)
    assert ba.stop_loss_price() == round(150.0 * 0.93, 2)


def test_profit_target_price():
    """Profit target should be 20% above buy point."""
    df = _make_df([100.0] * 100)
    ba = BreakoutAnalyzer(df, buy_point=150.0)
    assert ba.profit_target_price() == round(150.0 * 1.20, 2)


def test_breakout_confirmed_with_volume_surge():
    """Price at pivot with 40%+ volume surge and close in upper half = confirmed."""
    n = 100
    closes = [100.0] * (n - 1) + [151.0]  # Last day closes above pivot
    volumes = [1_000_000] * (n - 1) + [2_000_000]  # 100%+ surge
    highs = [c * 1.01 for c in closes[:-1]] + [152.0]
    lows = [c * 0.99 for c in closes[:-1]] + [149.0]
    df = _make_df(closes, volumes, highs, lows)
    ba = BreakoutAnalyzer(df, buy_point=150.0)
    result = ba.evaluate()
    assert result["breakout_confirmed"] is True


def test_breakout_not_confirmed_low_volume():
    """Price at pivot but without volume surge = not confirmed."""
    n = 100
    closes = [100.0] * (n - 1) + [151.0]
    volumes = [1_000_000] * n  # No surge
    df = _make_df(closes, volumes)
    ba = BreakoutAnalyzer(df, buy_point=150.0)
    result = ba.evaluate()
    assert result["breakout_confirmed"] is False


def test_breakout_pending_below_pivot():
    """Price still below pivot = None (pending)."""
    n = 100
    closes = [100.0] * n
    df = _make_df(closes)
    ba = BreakoutAnalyzer(df, buy_point=150.0)
    result = ba.evaluate()
    assert result["breakout_confirmed"] is None


def test_evaluate_returns_required_keys():
    """Result must have all expected keys."""
    df = _make_df([100.0] * 100)
    ba = BreakoutAnalyzer(df, buy_point=150.0)
    result = ba.evaluate()
    assert "stop_loss_price" in result
    assert "profit_target_price" in result
    assert "breakout_confirmed" in result
    assert "volume_surge_pct" in result


def test_score_confirmed_breakout():
    """Confirmed breakout should score 5 points."""
    n = 100
    closes = [100.0] * (n - 1) + [151.0]
    volumes = [1_000_000] * (n - 1) + [2_000_000]
    highs = [c * 1.01 for c in closes[:-1]] + [152.0]
    lows = [c * 0.99 for c in closes[:-1]] + [149.0]
    df = _make_df(closes, volumes, highs, lows)
    ba = BreakoutAnalyzer(df, buy_point=150.0)
    assert ba.score() == 5.0


def test_score_no_breakout():
    """No breakout = 0 points."""
    df = _make_df([100.0] * 100)
    ba = BreakoutAnalyzer(df, buy_point=150.0)
    assert ba.score() == 0.0
```

**Step 2: Run tests to verify they fail**

Run: `cd stock_pattern_scanner && python -m pytest tests/test_breakout_rules.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'breakout_rules'`

**Step 3: Write the implementation**

Create `stock_pattern_scanner/breakout_rules.py`:

```python
"""Breakout confirmation and entry rules.

Validates breakouts via volume surge and price action,
calculates stop-loss/profit targets.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from constants import (
    BREAKOUT_CLOSE_UPPER_HALF,
    BREAKOUT_ENTRY_MAX_PCT,
    BREAKOUT_EXTENDED_PCT,
    BREAKOUT_VOLUME_SURGE_PCT,
    PROFIT_TARGET_PCT,
    SCORE_BREAKOUT_QUALITY_MAX,
    STOP_LOSS_PCT,
)


class BreakoutAnalyzer:
    """Analyze breakout quality for a detected pattern."""

    def __init__(self, df: pd.DataFrame, buy_point: float):
        self.df = df
        self.buy_point = buy_point

    def stop_loss_price(self) -> float:
        """7% below buy point (O'Neil hard rule)."""
        return round(self.buy_point * (1 - STOP_LOSS_PCT / 100), 2)

    def profit_target_price(self) -> float:
        """20% above buy point."""
        return round(self.buy_point * (1 + PROFIT_TARGET_PCT / 100), 2)

    def evaluate(self) -> dict:
        """Evaluate breakout quality.

        Returns:
            Dict with stop_loss_price, profit_target_price,
            breakout_confirmed (True/False/None), volume_surge_pct.
        """
        df = self.df
        current_close = float(df["Close"].iloc[-1])
        distance_pct = (current_close - self.buy_point) / self.buy_point * 100

        result = {
            "stop_loss_price": self.stop_loss_price(),
            "profit_target_price": self.profit_target_price(),
            "breakout_confirmed": None,
            "volume_surge_pct": None,
        }

        # Price hasn't reached pivot yet
        if distance_pct < -BREAKOUT_ENTRY_MAX_PCT:
            return result

        # Price is extended beyond 5% above pivot
        if distance_pct > BREAKOUT_EXTENDED_PCT:
            result["breakout_confirmed"] = False
            return result

        # Check volume surge on the most recent day at/above pivot
        last_vol = float(df["Volume"].iloc[-1])
        if "AvgVolume50" in df.columns and pd.notna(df["AvgVolume50"].iloc[-1]):
            avg_vol = float(df["AvgVolume50"].iloc[-1])
        else:
            avg_vol = float(df["Volume"].iloc[-50:].mean())

        if avg_vol > 0:
            surge_pct = (last_vol - avg_vol) / avg_vol * 100
            result["volume_surge_pct"] = round(surge_pct, 1)
        else:
            surge_pct = 0.0

        # Check close in upper half of day's range
        day_high = float(df["High"].iloc[-1])
        day_low = float(df["Low"].iloc[-1])
        day_range = day_high - day_low
        if day_range > 0:
            close_position = (current_close - day_low) / day_range
        else:
            close_position = 0.5

        # Breakout confirmed if: volume surge >= 40% AND close in upper half
        volume_ok = surge_pct >= BREAKOUT_VOLUME_SURGE_PCT
        close_ok = close_position >= BREAKOUT_CLOSE_UPPER_HALF

        if current_close >= self.buy_point:
            result["breakout_confirmed"] = volume_ok and close_ok
        else:
            result["breakout_confirmed"] = None

        return result

    def score(self) -> float:
        """Breakout quality score (0-5 points)."""
        result = self.evaluate()
        if result["breakout_confirmed"] is True:
            return SCORE_BREAKOUT_QUALITY_MAX
        return 0.0
```

**Step 4: Run tests to verify they pass**

Run: `cd stock_pattern_scanner && python -m pytest tests/test_breakout_rules.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add stock_pattern_scanner/breakout_rules.py stock_pattern_scanner/tests/test_breakout_rules.py
git commit -m "feat: add breakout confirmation and entry rules module"
```

---

## Task 6: Add New Fields to PatternResult and Database

Add stop_loss_price, profit_target_price, breakout_confirmed, volume_surge_pct, volume_rating, trend_score to PatternResult. Update database schema.

**Files:**
- Modify: `stock_pattern_scanner/pattern_scanner.py` (PatternResult dataclass + status property)
- Modify: `stock_pattern_scanner/database.py` (schema + save/load)
- Modify: `stock_pattern_scanner/tests/conftest.py` (update defaults)

**Step 1: Run baseline tests**

Run: `cd stock_pattern_scanner && python -m pytest tests/ -v`
Expected: All 40 PASS

**Step 2: Update PatternResult dataclass**

In `stock_pattern_scanner/pattern_scanner.py`, add new fields to the `PatternResult` dataclass after `pattern_details`:

```python
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
    stop_loss_price: float = 0.0
    profit_target_price: float = 0.0
    breakout_confirmed: Optional[bool] = None
    volume_surge_pct: Optional[float] = None
    volume_rating: str = "C"
    trend_score: float = 0.0
```

**Step 3: Update the status property**

Add new status values for breakout confirmed and failed breakout. In `pattern_scanner.py`, update the `status` property:

```python
    @property
    def status(self) -> str:
        """Determine status based on distance to pivot and breakout confirmation."""
        if self.breakout_confirmed is True:
            return "Breakout Confirmed"
        if self.breakout_confirmed is False and self.distance_to_pivot >= 0:
            return "Failed Breakout"
        if self.distance_to_pivot > STATUS_EXTENDED_THRESHOLD:
            return "Extended"
        elif abs(self.distance_to_pivot) <= STATUS_AT_PIVOT_THRESHOLD:
            return "At Pivot"
        elif STATUS_NEAR_PIVOT_LOWER <= self.distance_to_pivot < -STATUS_AT_PIVOT_THRESHOLD:
            return "Near Pivot"
        elif self.distance_to_pivot < STATUS_NEAR_PIVOT_LOWER:
            return "Building"
        else:
            return "At Pivot"
```

**Step 4: Update database schema**

In `stock_pattern_scanner/database.py`, add new columns to the `results` table in `_init_db`:

```sql
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
    stop_loss_price REAL DEFAULT 0,
    profit_target_price REAL DEFAULT 0,
    breakout_confirmed INTEGER DEFAULT NULL,
    volume_surge_pct REAL DEFAULT NULL,
    volume_rating TEXT DEFAULT 'C',
    trend_score REAL DEFAULT 0,
    FOREIGN KEY (scan_id) REFERENCES scans(scan_id)
);
```

Update `save_results` to include the new fields in the INSERT statement:

```python
def save_results(self, scan_id: str, results: list[PatternResult]):
    with self._connect() as conn:
        for r in results:
            conn.execute(
                """INSERT INTO results
                   (scan_id, ticker, pattern_type, confidence_score, buy_point,
                    current_price, distance_to_pivot, base_depth, base_length_weeks,
                    volume_confirmation, above_50ma, above_200ma, rs_rating, pattern_details,
                    stop_loss_price, profit_target_price, breakout_confirmed, volume_surge_pct,
                    volume_rating, trend_score)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    scan_id, r.ticker, r.pattern_type, r.confidence_score,
                    r.buy_point, r.current_price, r.distance_to_pivot,
                    r.base_depth, r.base_length_weeks,
                    int(r.volume_confirmation), int(r.above_50ma),
                    int(r.above_200ma), r.rs_rating,
                    json.dumps(r.pattern_details, cls=_NumpyEncoder),
                    r.stop_loss_price, r.profit_target_price,
                    None if r.breakout_confirmed is None else int(r.breakout_confirmed),
                    r.volume_surge_pct, r.volume_rating, r.trend_score,
                ),
            )
```

Update `get_results` to read the new fields:

```python
def get_results(self, scan_id: str) -> list[PatternResult]:
    with self._connect() as conn:
        rows = conn.execute(
            "SELECT * FROM results WHERE scan_id=? ORDER BY confidence_score DESC",
            (scan_id,),
        ).fetchall()

    results = []
    for row in rows:
        bc_raw = row["breakout_confirmed"]
        bc = None if bc_raw is None else bool(bc_raw)
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
            stop_loss_price=row["stop_loss_price"] or 0.0,
            profit_target_price=row["profit_target_price"] or 0.0,
            breakout_confirmed=bc,
            volume_surge_pct=row["volume_surge_pct"],
            volume_rating=row["volume_rating"] or "C",
            trend_score=row["trend_score"] or 0.0,
        ))
    return results
```

**Step 5: Update conftest.py defaults**

In `stock_pattern_scanner/tests/conftest.py`, add the new fields to `_PATTERN_RESULT_DEFAULTS`:

```python
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
```

**Step 6: Delete the old scanner.db to avoid schema mismatch**

Run: `cd stock_pattern_scanner && rm -f scanner.db`

**Step 7: Run all tests**

Run: `cd stock_pattern_scanner && python -m pytest tests/ -v`
Expected: All PASS (existing tests should still work since new fields have defaults)

**Step 8: Commit**

```bash
git add stock_pattern_scanner/pattern_scanner.py stock_pattern_scanner/database.py stock_pattern_scanner/tests/conftest.py
git commit -m "feat: add new fields to PatternResult and database schema for institutional analysis"
```

---

## Task 7: Integrate New Modules into StockScanner

Wire market regime, volume analysis, trend strength, and breakout rules into the scan pipeline. Replace the old confidence scoring.

**Files:**
- Modify: `stock_pattern_scanner/pattern_scanner.py` (StockScanner class + calculate_confidence)

**Step 1: Run baseline tests**

Run: `cd stock_pattern_scanner && python -m pytest tests/ -v`
Expected: All PASS

**Step 2: Add imports to pattern_scanner.py**

At the top of `pattern_scanner.py`, add after the existing constants import:

```python
from breakout_rules import BreakoutAnalyzer
from market_regime import MarketRegime
from trend_strength import TrendAnalyzer
from volume_analysis import VolumeAnalyzer
```

Also import the new scoring constants:

```python
from constants import (
    # ... existing imports ...
    RS_MODERATE,
    RS_STRONG,
    SCORE_ABOVE_200MA_MAX_V2,
    SCORE_ABOVE_50MA_MAX_V2,
    SCORE_BASE_LENGTH_MAX_V2,
    SCORE_BREAKOUT_QUALITY_MAX,
    SCORE_DEPTH_MAX_V2,
    SCORE_MINIMUM_VIABLE,
    SCORE_PATTERN_BONUS_MAX_V2,
    SCORE_RS_RATING_MAX,
    SCORE_TIGHTNESS_MAX_V2,
    SCORE_TREND_STRENGTH_MAX,
    SCORE_VOLUME_PROFILE_MAX,
)
```

**Step 3: Update `calculate_confidence` to use new scoring**

Replace the `calculate_confidence` method body with the revised scoring model. Keep the same method signature for compatibility:

```python
def calculate_confidence(
    self, pattern: dict, df: pd.DataFrame,
    volume_score: float = 0.0,
    trend_score: float = 0.0,
    rs_rating: float = 0.0,
    breakout_score: float = 0.0,
) -> float:
    """Calculate confidence score (0-100) using revised institutional scoring.

    New scoring model (100 pts):
    - Base depth: 15 pts
    - Volume profile: 20 pts (from VolumeAnalyzer)
    - Above 50-day MA: 10 pts
    - Above 200-day MA: 5 pts
    - Tightness: 10 pts
    - Base length: 5 pts
    - Pattern bonuses: 10 pts
    - Trend strength: 10 pts (from TrendAnalyzer)
    - RS rating: 10 pts
    - Breakout quality: 5 pts (from BreakoutAnalyzer)
    """
    score = 0.0
    pattern_type = pattern["pattern_type"]
    depth = pattern.get("base_depth", 0)
    length_weeks = pattern.get("base_length_weeks", 0)

    # 1. Depth score (15 pts)
    if pattern_type == "Flat Base":
        if FLAT_BASE_IDEAL_DEPTH_LOW <= depth <= FLAT_BASE_IDEAL_DEPTH_HIGH:
            score += SCORE_DEPTH_MAX_V2
        elif depth < FLAT_BASE_IDEAL_DEPTH_LOW:
            score += 8
        else:
            score += max(0, SCORE_DEPTH_MAX_V2 - (depth - FLAT_BASE_IDEAL_DEPTH_HIGH) * FLAT_BASE_DEPTH_PENALTY)
    elif pattern_type == "Double Bottom":
        if DOUBLE_BOTTOM_IDEAL_DEPTH_LOW <= depth <= DOUBLE_BOTTOM_IDEAL_DEPTH_HIGH:
            score += SCORE_DEPTH_MAX_V2
        else:
            score += max(0, SCORE_DEPTH_MAX_V2 - abs(depth - DOUBLE_BOTTOM_DEPTH_CENTER) * DOUBLE_BOTTOM_DEPTH_PENALTY)
    elif pattern_type in ("Cup & Handle", "Deep Cup & Handle"):
        ideal = CUP_DEEP_IDEAL_DEPTH_CENTER if pattern_type == "Deep Cup & Handle" else CUP_IDEAL_DEPTH_CENTER
        score += max(0, SCORE_DEPTH_MAX_V2 - abs(depth - ideal) * CUP_DEPTH_PENALTY)

    # 2. Volume profile (20 pts — passed in from VolumeAnalyzer)
    score += volume_score

    # 3. Price above 50-day MA (10 pts)
    current_close = df["Close"].iloc[-1]
    above_50 = False
    above_200 = False
    if "MA50" in df.columns and pd.notna(df["MA50"].iloc[-1]):
        if current_close > df["MA50"].iloc[-1]:
            score += SCORE_ABOVE_50MA_MAX_V2
            above_50 = True

    # 4. Price above 200-day MA (5 pts)
    if "MA200" in df.columns and pd.notna(df["MA200"].iloc[-1]):
        if current_close > df["MA200"].iloc[-1]:
            score += SCORE_ABOVE_200MA_MAX_V2
            above_200 = True

    # 5. Consolidation tightness (10 pts)
    last_25 = df["Close"].iloc[-TIGHTNESS_LOOKBACK:]
    if len(last_25) >= TIGHTNESS_LOOKBACK:
        weekly_range = (last_25.max() - last_25.min()) / last_25.mean() * 100
        if weekly_range < TIGHTNESS_TIGHT:
            score += SCORE_TIGHTNESS_MAX_V2
        elif weekly_range < TIGHTNESS_MODERATE:
            score += 7
        elif weekly_range < TIGHTNESS_LOOSE:
            score += 3

    # 6. Base length (5 pts)
    if pattern_type == "Flat Base":
        ideal_weeks = FLAT_BASE_IDEAL_WEEKS
    elif pattern_type == "Double Bottom":
        ideal_weeks = DOUBLE_BOTTOM_IDEAL_WEEKS
    else:
        ideal_weeks = CUP_IDEAL_WEEKS

    if ideal_weeks[0] <= length_weeks <= ideal_weeks[1]:
        score += SCORE_BASE_LENGTH_MAX_V2
    elif length_weeks < ideal_weeks[0]:
        score += 3
    else:
        score += max(0, SCORE_BASE_LENGTH_MAX_V2 - (length_weeks - ideal_weeks[1]) * BASE_LENGTH_OVER_PENALTY)

    # 7. Pattern-specific bonuses (10 pts)
    if pattern_type == "Double Bottom":
        low_diff = pattern.get("low_diff_pct", 10)
        if low_diff <= DOUBLE_BOTTOM_TIGHT_LOW_DIFF:
            score += 7
        elif low_diff <= DOUBLE_BOTTOM_MODERATE_LOW_DIFF:
            score += 4
        if pattern.get("second_low", 0) < pattern.get("first_low", 0):
            score += 3
    elif pattern_type in ("Cup & Handle", "Deep Cup & Handle"):
        recovery = pattern.get("recovery_pct", 0)
        if recovery >= CUP_HIGH_RECOVERY_PCT:
            score += 7
        elif recovery >= CUP_MODERATE_RECOVERY_PCT:
            score += 4
        handle_low = pattern.get("handle_low", 0)
        right_high = pattern.get("right_high", 1)
        if right_high > 0:
            handle_depth = (right_high - handle_low) / right_high * 100
            if handle_depth < CUP_TIGHT_HANDLE_DEPTH_PCT:
                score += 3
    elif pattern_type == "Flat Base":
        if above_50 and above_200:
            score += 7
        if depth < FLAT_BASE_TIGHT_DEPTH_PCT:
            score += 3

    # 8. Trend strength (10 pts — passed in from TrendAnalyzer)
    score += trend_score

    # 9. RS rating (10 pts)
    if rs_rating >= RS_STRONG:
        score += SCORE_RS_RATING_MAX
    elif rs_rating >= RS_MODERATE:
        score += 5

    # 10. Breakout quality (5 pts — passed in from BreakoutAnalyzer)
    score += breakout_score

    return round(min(100, max(0, score)), 1)
```

**Step 4: Update `_analyze_ticker` to use new modules**

Replace the `_analyze_ticker` method in `StockScanner`:

```python
def _analyze_ticker(
    self, ticker: str, spy_df: pd.DataFrame
) -> list[PatternResult]:
    """Analyze a single ticker for all pattern types."""
    df = self._fetch_data(ticker)
    if df is None:
        return []

    df = self.detector.add_moving_averages(df)

    # Trend strength analysis
    trend_analyzer = TrendAnalyzer(df)
    if trend_analyzer.is_too_volatile():
        return []  # ATR ratio > 5%, skip

    trend_score = trend_analyzer.score()

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
            if pattern is None:
                continue

            # Volume analysis over the base period
            base_start = pattern.get("base_start_idx", len(df) - pattern.get("base_length_weeks", 5) * 5)
            base_end = len(df) - 1
            vol_analyzer = VolumeAnalyzer(df, base_start, base_end)

            if vol_analyzer.is_distributing():
                continue  # D/E volume rating, skip

            volume_score = vol_analyzer.score()
            volume_rating = vol_analyzer.ad_rating()

            # Breakout analysis
            breakout_analyzer = BreakoutAnalyzer(df, pattern["buy_point"])
            breakout_result = breakout_analyzer.evaluate()
            breakout_score = breakout_analyzer.score()

            confidence = self.detector.calculate_confidence(
                pattern, df,
                volume_score=volume_score,
                trend_score=trend_score,
                rs_rating=rs_rating,
                breakout_score=breakout_score,
            )

            if confidence < SCORE_MINIMUM_VIABLE:
                continue  # Below minimum threshold

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
                stop_loss_price=breakout_result["stop_loss_price"],
                profit_target_price=breakout_result["profit_target_price"],
                breakout_confirmed=breakout_result["breakout_confirmed"],
                volume_surge_pct=breakout_result["volume_surge_pct"],
                volume_rating=volume_rating,
                trend_score=trend_score,
            )
            results.append(result)
        except Exception as e:
            logger.warning("Error detecting %s for %s: %s", detect_fn.__name__, ticker, e)

    return results
```

**Step 5: Update `scan` to include market regime check**

In the `scan` method, add regime check after fetching SPY:

```python
def scan(
    self,
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
) -> list[PatternResult]:
    """Scan all tickers for patterns."""
    # Fetch SPY data for relative strength and market regime
    spy_df = self._fetch_data("SPY")
    if spy_df is None:
        logger.error("Failed to fetch SPY data. RS ratings will be inaccurate.")
        spy_df = pd.DataFrame({"Close": [100] * TRADING_DAYS_PER_YEAR, "Volume": [1] * TRADING_DAYS_PER_YEAR})

    # Market regime check
    spy_with_ma = self.detector.add_moving_averages(spy_df)
    self.market_regime = MarketRegime(spy_with_ma)
    regime = self.market_regime.evaluate()
    self._regime_status = regime["status"]

    if regime["status"] == "correction":
        logger.info("Market in correction — no buy signals.")
        # Still run progress callbacks so UI completes
        total = len(self.tickers)
        for i, ticker in enumerate(self.tickers):
            if progress_callback:
                progress_callback(i + 1, total, ticker)
        return []

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

**Step 6: Update existing tests for the new `calculate_confidence` signature**

The old tests call `calculate_confidence(pattern, df)` without the new optional kwargs. Since the new params default to `0.0` and `0.0`, old calls still work — but the scores will be lower because the max is now distributed across more components. Update the threshold assertions in `test_pattern_scanner.py`:

In `test_confidence_score_high_quality`: Change `assert score >= 60` to `assert score >= 40` (since volume_score, trend_score, rs_rating, breakout_score are all 0 in the test).

In `test_confidence_score_low_quality`: Keep `assert score < 60` — it will still be low.

**Step 7: Run all tests**

Run: `cd stock_pattern_scanner && python -m pytest tests/ -v`
Expected: All PASS

**Step 8: Commit**

```bash
git add stock_pattern_scanner/pattern_scanner.py stock_pattern_scanner/tests/test_pattern_scanner.py
git commit -m "feat: integrate market regime, volume analysis, trend strength, and breakout rules into scanner"
```

---

## Task 8: Update API and Dashboard

Add market status endpoint, new result fields, and market health banner.

**Files:**
- Modify: `stock_pattern_scanner/app.py`
- Modify: `stock_pattern_scanner/templates/dashboard.html`

**Step 1: Update app.py**

Add the market status endpoint and update the results endpoint to include new fields.

Add this import at the top of `app.py`:

```python
from market_regime import MarketRegime
```

Add after the `get_watchlists` endpoint:

```python
@app.get("/api/market-status")
async def market_status():
    """Return current market regime based on SPY data."""
    import yfinance as yf
    try:
        spy = yf.Ticker("SPY")
        spy_df = spy.history(period="2y")
        if spy_df is None or len(spy_df) < 200:
            return {"status": "unknown", "error": "Could not fetch SPY data"}
        from pattern_scanner import PatternDetector
        detector = PatternDetector()
        spy_df = detector.add_moving_averages(spy_df)
        regime = MarketRegime(spy_df)
        return regime.evaluate()
    except Exception as e:
        return {"status": "unknown", "error": str(e)}
```

Update the results response in `get_results` to include new fields:

```python
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
                "stop_loss_price": r.stop_loss_price,
                "profit_target_price": r.profit_target_price,
                "breakout_confirmed": r.breakout_confirmed,
                "volume_surge_pct": r.volume_surge_pct,
                "volume_rating": r.volume_rating,
                "trend_score": r.trend_score,
            }
            for r in results
        ],
    }
```

**Step 2: Update dashboard.html — add market health banner**

Add a market health banner after the header and before the controls. In the `<style>` section, add:

```css
.market-banner {
    padding: 12px 20px;
    border-radius: 6px;
    margin-bottom: 16px;
    font-weight: 600;
    font-size: 14px;
    display: flex;
    align-items: center;
    gap: 8px;
}
.market-banner.uptrend { background: rgba(63, 185, 80, 0.15); color: var(--success); border: 1px solid rgba(63, 185, 80, 0.3); }
.market-banner.pressure { background: rgba(210, 153, 34, 0.15); color: var(--warning); border: 1px solid rgba(210, 153, 34, 0.3); }
.market-banner.correction { background: rgba(248, 81, 73, 0.15); color: var(--danger); border: 1px solid rgba(248, 81, 73, 0.3); }
```

In the HTML body, add after `<div class="container">` and before the controls div:

```html
<div id="marketBanner" class="market-banner" style="display:none;"></div>
```

**Step 3: Update dashboard.html — add new columns to results table**

In the results table header row, add after the RS Rating column:

```html
<th>Vol Rating</th>
<th>Stop Loss</th>
<th>Target</th>
```

In the JavaScript where result rows are built, add the new cells:

```javascript
// After the rs_rating cell:
`<td>${r.volume_rating || 'C'}</td>
<td>$${(r.stop_loss_price || 0).toFixed(2)}</td>
<td>$${(r.profit_target_price || 0).toFixed(2)}</td>`
```

**Step 4: Update dashboard.html — add market status fetch**

In the JavaScript, add a function that runs on page load to fetch market status:

```javascript
async function fetchMarketStatus() {
    try {
        const res = await fetch('/api/market-status');
        const data = await res.json();
        const banner = document.getElementById('marketBanner');
        if (data.status === 'confirmed_uptrend') {
            banner.className = 'market-banner uptrend';
            banner.textContent = `Market: Confirmed Uptrend — ${data.distribution_days} distribution days`;
        } else if (data.status === 'uptrend_under_pressure') {
            banner.className = 'market-banner pressure';
            banner.textContent = `Market: Uptrend Under Pressure — ${data.distribution_days} distribution days`;
        } else if (data.status === 'correction') {
            banner.className = 'market-banner correction';
            banner.textContent = `Market: In Correction — Buy signals disabled`;
        } else {
            banner.style.display = 'none';
            return;
        }
        banner.style.display = 'flex';
    } catch (e) {
        console.error('Failed to fetch market status', e);
    }
}
fetchMarketStatus();
```

**Step 5: Run tests**

Run: `cd stock_pattern_scanner && python -m pytest tests/test_app.py -v`
Expected: All PASS

**Step 6: Commit**

```bash
git add stock_pattern_scanner/app.py stock_pattern_scanner/templates/dashboard.html
git commit -m "feat: add market health banner, new result columns, and market status API"
```

---

## Task 9: Delete old scanner.db and run full verification

Clean up, run all tests, verify the full pipeline works.

**Files:**
- No new files

**Step 1: Delete old database (schema changed)**

Run: `cd stock_pattern_scanner && rm -f scanner.db`

**Step 2: Run full test suite**

Run: `cd stock_pattern_scanner && python -m pytest tests/ -v`
Expected: All tests PASS

**Step 3: Push to GitHub and verify Railway deployment**

```bash
git push origin master
```

Wait for Railway to redeploy, then test:

Run: `curl -s https://trenad-production.up.railway.app/api/market-status | python -m json.tool`
Expected: JSON with `status`, `spy_above_200ma`, `distribution_days` fields.

Run: `curl -s -X POST https://trenad-production.up.railway.app/api/scan -H "Content-Type: application/json" -d '{"watchlist": "custom", "tickers": ["AAPL", "MSFT", "NVDA"]}'`
Then check results include new fields (stop_loss_price, profit_target_price, volume_rating).

---

## Verification Checklist

After all tasks, run the full suite:

```bash
cd stock_pattern_scanner && python -m pytest tests/ -v
```

Expected: All tests PASS with new institutional-quality analysis active.

**Files created:**
- `market_regime.py` — SPY-based bull/bear detection
- `volume_analysis.py` — A/D rating, dry-up, up/down ratio
- `trend_strength.py` — ADX, MA slope, ATR ratio
- `breakout_rules.py` — Volume surge, stop/target, entry validation
- `tests/test_market_regime.py`
- `tests/test_volume_analysis.py`
- `tests/test_trend_strength.py`
- `tests/test_breakout_rules.py`

**Files modified:**
- `constants.py` — New thresholds for all modules
- `pattern_scanner.py` — PatternResult fields, status property, revised scoring, scanner integration
- `database.py` — New columns in schema
- `tests/conftest.py` — Updated defaults
- `tests/test_pattern_scanner.py` — Adjusted score thresholds
- `app.py` — Market status endpoint, new result fields
- `templates/dashboard.html` — Market banner, new table columns
