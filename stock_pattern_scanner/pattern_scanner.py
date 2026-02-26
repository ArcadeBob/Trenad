"""Core pattern detection engine for stock base pattern scanning."""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Callable, Dict, Optional

import numpy as np
import pandas as pd
import yfinance as yf
from scipy.signal import argrelextrema

from breakout_rules import BreakoutAnalyzer
from constants import (
    BASE_LENGTH_OVER_PENALTY,
    CUP_DEEP_IDEAL_DEPTH_CENTER,
    CUP_DEEP_THRESHOLD_PCT,
    CUP_DEPTH_PENALTY,
    CUP_HANDLE_VOLUME_FACTOR,
    CUP_HIGH_RECOVERY_PCT,
    CUP_IDEAL_DEPTH_CENTER,
    CUP_IDEAL_WEEKS,
    CUP_LOOKBACK_BUFFER,
    CUP_MAX_DEPTH_PCT,
    CUP_MAX_LOOKBACK_DAYS,
    CUP_MAX_TOTAL_WEEKS,
    CUP_MIN_AFTER_LIP,
    CUP_MIN_AFTER_LOW,
    CUP_MIN_DEPTH_PCT,
    CUP_MIN_HANDLE_DAYS,
    CUP_MIN_RECOVERY_PCT,
    CUP_MIN_TOTAL_WEEKS,
    CUP_MODERATE_RECOVERY_PCT,
    CUP_PEAK_WINDOW,
    CUP_TIGHT_HANDLE_DEPTH_PCT,
    DEFAULT_HISTORY_PERIOD,
    DEFAULT_MAX_WORKERS,
    DOUBLE_BOTTOM_DEPTH_CENTER,
    DOUBLE_BOTTOM_DEPTH_PENALTY,
    DOUBLE_BOTTOM_IDEAL_DEPTH_HIGH,
    DOUBLE_BOTTOM_IDEAL_DEPTH_LOW,
    DOUBLE_BOTTOM_IDEAL_WEEKS,
    DOUBLE_BOTTOM_LOOKBACK_BUFFER,
    DOUBLE_BOTTOM_LOOKBACK_DAYS,
    DOUBLE_BOTTOM_LOW_DIFF_MAX_PCT,
    DOUBLE_BOTTOM_MAX_DEPTH_PCT,
    DOUBLE_BOTTOM_MIN_AFTER_HIGH,
    DOUBLE_BOTTOM_MIN_DEPTH_PCT,
    DOUBLE_BOTTOM_MIN_SEPARATION_DAYS,
    DOUBLE_BOTTOM_MODERATE_LOW_DIFF,
    DOUBLE_BOTTOM_TIGHT_LOW_DIFF,
    DOUBLE_BOTTOM_TROUGH_WINDOW,
    DOUBLE_BOTTOM_VOLUME_WINDOW,
    FLAT_BASE_DEPTH_PENALTY,
    FLAT_BASE_IDEAL_DEPTH_HIGH,
    FLAT_BASE_IDEAL_DEPTH_LOW,
    FLAT_BASE_IDEAL_WEEKS,
    FLAT_BASE_MA50_THRESHOLD,
    FLAT_BASE_MAX_DEPTH_PCT,
    FLAT_BASE_MAX_WINDOW_DAYS,
    FLAT_BASE_PRIOR_VOLUME_DAYS,
    FLAT_BASE_SEED_DAYS,
    FLAT_BASE_SEED_FLOOR_FACTOR,
    FLAT_BASE_TIGHT_DEPTH_PCT,
    FLAT_BASE_VOLUME_CONTRACTION,
    HANDLE_MAX_DECLINE_PCT,
    HANDLE_MAX_LENGTH_WEEKS,
    MIN_DATA_POINTS,
    PRIOR_UPTREND_LOOKBACK_DAYS,
    PRIOR_UPTREND_MIN_GAIN_PCT,
    PRIOR_UPTREND_MIN_SEGMENT_LEN,
    RS_BASELINE,
    RS_MAX,
    RS_MIN,
    RS_MODERATE,
    RS_PERIODS,
    RS_STRONG,
    RS_WEIGHTS,
    SCORE_ABOVE_200MA_MAX,
    SCORE_ABOVE_200MA_MAX_V2,
    SCORE_ABOVE_50MA_MAX,
    SCORE_ABOVE_50MA_MAX_V2,
    SCORE_BASE_LENGTH_MAX,
    SCORE_BASE_LENGTH_MAX_V2,
    SCORE_BREAKOUT_QUALITY_MAX,
    SCORE_DEPTH_MAX,
    SCORE_DEPTH_MAX_V2,
    SCORE_MINIMUM_VIABLE,
    SCORE_PATTERN_BONUS_MAX_V2,
    SCORE_RS_RATING_MAX,
    SCORE_TIGHTNESS_MAX,
    SCORE_TIGHTNESS_MAX_V2,
    SCORE_TREND_STRENGTH_MAX,
    SCORE_VOLUME_MAX,
    SCORE_VOLUME_PROFILE_MAX,
    STATUS_AT_PIVOT_THRESHOLD,
    STATUS_EXTENDED_THRESHOLD,
    STATUS_NEAR_PIVOT_LOWER,
    TIGHTNESS_LOOKBACK,
    TIGHTNESS_LOOSE,
    TIGHTNESS_MODERATE,
    TIGHTNESS_TIGHT,
    TRADING_DAYS_PER_YEAR,
)
from market_regime import MarketRegime
from trend_strength import TrendAnalyzer
from volume_analysis import VolumeAnalyzer

logger = logging.getLogger(__name__)


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
            # 1.0 < distance <= 5.0 (slightly above buy point but not extended)
            return "At Pivot"


class PatternDetector:
    """Detects CAN SLIM base patterns in stock price data."""

    def find_local_peaks(self, prices: pd.Series, window: int = 10) -> list[int]:
        """Find indices of local maxima in a price series."""
        arr = prices.values
        peaks = argrelextrema(arr, np.greater_equal, order=window)[0]
        return peaks.tolist()

    def find_local_troughs(self, prices: pd.Series, window: int = 10) -> list[int]:
        """Find indices of local minima in a price series."""
        arr = prices.values
        troughs = argrelextrema(arr, np.less_equal, order=window)[0]
        return troughs.tolist()

    def add_moving_averages(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add MA10, MA20, MA50, MA200, AvgVolume50 columns."""
        df = df.copy()
        df["MA10"] = df["Close"].rolling(window=10).mean()
        df["MA20"] = df["Close"].rolling(window=20).mean()
        df["MA50"] = df["Close"].rolling(window=50).mean()
        df["MA200"] = df["Close"].rolling(window=200).mean()
        df["AvgVolume50"] = df["Volume"].rolling(window=50).mean()
        return df

    def calculate_relative_strength(self, stock_df: pd.DataFrame, spy_df: pd.DataFrame) -> float:
        """Calculate relative strength rating (0-100) vs SPY.

        Uses weighted blend: 40% recent quarter, 20% each for 6/9/12 months.
        """
        periods = RS_PERIODS
        weights = RS_WEIGHTS

        stock_close = stock_df["Close"]
        spy_close = spy_df["Close"]

        stock_returns = []
        spy_returns = []

        for period in periods:
            if len(stock_close) >= period and len(spy_close) >= period:
                sr = (stock_close.iloc[-1] / stock_close.iloc[-period] - 1) * 100
                spr = (spy_close.iloc[-1] / spy_close.iloc[-period] - 1) * 100
                stock_returns.append(sr)
                spy_returns.append(spr)
            else:
                stock_returns.append(0)
                spy_returns.append(0)

        weighted_stock = sum(r * w for r, w in zip(stock_returns, weights))
        weighted_spy = sum(r * w for r, w in zip(spy_returns, weights))

        rs_raw = RS_BASELINE + (weighted_stock - weighted_spy)
        return max(RS_MIN, min(RS_MAX, round(rs_raw, 1)))

    def _has_prior_uptrend(self, df: pd.DataFrame, end_idx: int, min_gain: float = PRIOR_UPTREND_MIN_GAIN_PCT) -> bool:
        """Check for *min_gain*% uptrend in the 6 months before *end_idx*.

        The low must come before the high so that the move is an actual
        uptrend (not a decline that happens to span 30 %+).

        Parameters
        ----------
        df : pd.DataFrame
            Price data with a ``Close`` column.
        end_idx : int
            The positional index marking the end of the look-back window.
        min_gain : float, optional
            Minimum percentage gain required (default 30 %).

        Returns
        -------
        bool
            ``True`` when the conditions are met.
        """
        lookback = PRIOR_UPTREND_LOOKBACK_DAYS  # ~6 months of trading days
        start_idx = max(0, end_idx - lookback)
        segment = df["Close"].iloc[start_idx:end_idx]

        if len(segment) < PRIOR_UPTREND_MIN_SEGMENT_LEN:
            return False

        low_pos = int(segment.values.argmin())
        high_pos = int(segment.values.argmax())

        # High must come AFTER the low (uptrend direction)
        if high_pos <= low_pos:
            return False

        low_val = segment.values[low_pos]
        high_val = segment.values[high_pos]

        if low_val <= 0:
            return False

        gain_pct = (high_val - low_val) / low_val * 100
        return gain_pct >= min_gain

    def detect_flat_base(self, df: pd.DataFrame) -> dict | None:
        """Detect a flat-base pattern in *df*.

        Flat-base criteria
        ------------------
        * At least 200 data points available.
        * Within the most recent 75 trading days, find a tight
          consolidation range (high-to-low < 15 %).
        * Walk backward from the end to determine where the
          consolidation began; it must span at least 25 trading days
          (~5 weeks).
        * A 30 %+ prior uptrend in the 6 months before the base.
        * More than 50 % of base days must close above the 50-day MA.
        * Volume contraction: average volume in the base must be less
          than 90 % of the average volume in the 50 days before the base.

        Returns
        -------
        dict or None
            A dict describing the pattern, or ``None`` when no flat base
            is found.
        """
        if len(df) < MIN_DATA_POINTS:
            return None

        # --- Identify tight consolidation ------------------------------------
        # Start with a narrow window (25 days = 5 weeks minimum) to get the
        # core consolidation range, then expand backward while the range
        # stays tight (< 15 %).
        full_close = df["Close"].values
        end_pos = len(df) - 1
        max_window = min(FLAT_BASE_MAX_WINDOW_DAYS, len(df))

        # Seed range from the most recent 25 days
        seed = full_close[end_pos - (FLAT_BASE_SEED_DAYS - 1) : end_pos + 1]
        base_high = float(seed.max())
        base_low = float(seed.min())

        if base_low <= 0:
            return None

        # Expand backward day by day while price stays within the
        # consolidation band.  Allow the band to widen only up to 15 %
        # total depth, AND stop when a price falls below the seed low
        # minus a small tolerance (half the seed range).  This prevents
        # the base from creeping into a prior uptrend.
        seed_range = base_high - base_low
        floor = base_low - seed_range * FLAT_BASE_SEED_FLOOR_FACTOR

        base_start = end_pos - (FLAT_BASE_SEED_DAYS - 1)
        for i in range(end_pos - FLAT_BASE_SEED_DAYS, end_pos - max_window, -1):
            if i < 0:
                break
            price = full_close[i]
            if price < floor:
                break
            new_high = max(base_high, price)
            new_low = min(base_low, price)
            depth = (new_high - new_low) / new_high * 100
            if depth >= FLAT_BASE_MAX_DEPTH_PCT:
                break
            base_high = new_high
            base_low = new_low
            base_start = i

        depth_pct = (base_high - base_low) / base_high * 100

        if depth_pct >= FLAT_BASE_MAX_DEPTH_PCT:
            return None

        base_length = end_pos - base_start + 1

        # Must be at least 5 weeks (~25 trading days)
        if base_length < FLAT_BASE_SEED_DAYS:
            return None

        # --- Prior uptrend check ----------------------------------------
        if not self._has_prior_uptrend(df, base_start, min_gain=PRIOR_UPTREND_MIN_GAIN_PCT):
            return None

        # --- 50-day MA check --------------------------------------------
        if "MA50" not in df.columns:
            return None

        base_slice = df.iloc[base_start: end_pos + 1]
        ma50_valid = base_slice["MA50"].dropna()
        if len(ma50_valid) == 0:
            return None

        close_above_ma50 = (base_slice.loc[ma50_valid.index, "Close"] > ma50_valid).sum()
        if close_above_ma50 / len(ma50_valid) <= FLAT_BASE_MA50_THRESHOLD:
            return None

        # --- Volume contraction -----------------------------------------
        base_avg_vol = base_slice["Volume"].mean()
        prior_start = max(0, base_start - FLAT_BASE_PRIOR_VOLUME_DAYS)
        prior_avg_vol = df["Volume"].iloc[prior_start:base_start].mean()

        volume_ok = bool(base_avg_vol < prior_avg_vol * FLAT_BASE_VOLUME_CONTRACTION) if prior_avg_vol > 0 else False

        # --- Build result -----------------------------------------------
        current_price = float(full_close[-1])
        buy_point = float(base_high)
        distance_to_pivot = (current_price - buy_point) / buy_point * 100

        return {
            "pattern_type": "Flat Base",
            "buy_point": buy_point,
            "current_price": current_price,
            "distance_to_pivot": round(distance_to_pivot, 2),
            "base_depth": round(depth_pct, 2),
            "base_length_weeks": base_length // 5,
            "volume_confirmation": volume_ok,
            "base_high": buy_point,
            "base_low": float(base_low),
            "base_start_idx": base_start,
        }

    def detect_double_bottom(self, df: pd.DataFrame) -> dict | None:
        """Detect a double bottom (W-pattern) in recent price data.

        Criteria:
        - Two distinct lows within 5% of each other
        - Second low may slightly undercut first (bullish shakeout)
        - 15-40% depth from prior high
        - Middle peak forms resistance / buy point

        Returns:
            Pattern dict with details, or None if no pattern found.
        """
        if len(df) < MIN_DATA_POINTS:
            return None

        closes = df["Close"]

        # Look in the last ~9 months for the pattern
        lookback = min(DOUBLE_BOTTOM_LOOKBACK_DAYS, len(df) - DOUBLE_BOTTOM_LOOKBACK_BUFFER)
        recent = closes.iloc[-lookback:]

        # Find the prior high (highest point before the decline)
        prior_high_idx = recent.idxmax()
        prior_high = recent[prior_high_idx]
        prior_high_pos = recent.index.get_loc(prior_high_idx)

        # Need enough data after the high for the W pattern
        if prior_high_pos > lookback * 0.5:
            return None

        after_high = recent.iloc[prior_high_pos:]
        if len(after_high) < DOUBLE_BOTTOM_MIN_AFTER_HIGH:
            return None

        # Find troughs in the data after the high
        troughs = self.find_local_troughs(after_high, window=DOUBLE_BOTTOM_TROUGH_WINDOW)
        if len(troughs) < 2:
            return None

        # Get the two most prominent troughs (lowest prices)
        trough_prices = [(t, float(after_high.iloc[t])) for t in troughs]
        trough_prices.sort(key=lambda x: x[1])

        first_trough_idx, first_low = trough_prices[0]
        second_trough_idx, second_low = trough_prices[1]

        # Ensure chronological order
        if first_trough_idx > second_trough_idx:
            first_trough_idx, first_low, second_trough_idx, second_low = (
                second_trough_idx, second_low, first_trough_idx, first_low
            )

        # Check lows are within 5% of each other
        low_diff_pct = abs(first_low - second_low) / max(first_low, second_low) * 100
        if low_diff_pct > DOUBLE_BOTTOM_LOW_DIFF_MAX_PCT:
            return None

        # Need meaningful separation between the two lows (at least 3 weeks)
        if (second_trough_idx - first_trough_idx) < DOUBLE_BOTTOM_MIN_SEPARATION_DAYS:
            return None

        # Find the middle peak between the two troughs
        between = after_high.iloc[first_trough_idx:second_trough_idx + 1]
        if len(between) < 3:
            return None
        middle_peak = float(between.max())

        # Check depth from prior high
        base_low = min(first_low, second_low)
        depth = (prior_high - base_low) / prior_high * 100

        # Double bottom typically 15-40% deep
        if depth < DOUBLE_BOTTOM_MIN_DEPTH_PCT or depth > DOUBLE_BOTTOM_MAX_DEPTH_PCT:
            return None

        # Total base length
        total_days = second_trough_idx + 10
        base_length_weeks = total_days / 5

        # Volume confirmation: declining volume into second low
        volume_confirm = False
        abs_first = after_high.index[first_trough_idx]
        abs_second = after_high.index[second_trough_idx]
        first_pos = df.index.get_loc(abs_first)
        second_pos = df.index.get_loc(abs_second)
        if first_pos > DOUBLE_BOTTOM_VOLUME_WINDOW and second_pos > DOUBLE_BOTTOM_VOLUME_WINDOW:
            vol_around_first = df["Volume"].iloc[first_pos - DOUBLE_BOTTOM_VOLUME_WINDOW : first_pos + DOUBLE_BOTTOM_VOLUME_WINDOW].mean()
            vol_around_second = df["Volume"].iloc[second_pos - DOUBLE_BOTTOM_VOLUME_WINDOW : second_pos + DOUBLE_BOTTOM_VOLUME_WINDOW].mean()
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
        if len(df) < MIN_DATA_POINTS:
            return None

        closes = df["Close"]

        # Scan last 65 weeks (~325 trading days) for cup formation
        max_lookback = min(CUP_MAX_LOOKBACK_DAYS, len(df) - CUP_LOOKBACK_BUFFER)
        recent = closes.iloc[-max_lookback:]

        # Find the cup's left lip (highest point before decline)
        peaks = self.find_local_peaks(recent, window=CUP_PEAK_WINDOW)
        if not peaks:
            return None

        # Try each peak as potential left lip, starting from most recent viable ones
        for peak_idx in reversed(peaks):
            left_lip = float(recent.iloc[peak_idx])
            left_lip_pos = peak_idx

            # Need at least 35 days after left lip for cup + handle
            if len(recent) - left_lip_pos < CUP_MIN_AFTER_LIP:
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
            if depth < CUP_MIN_DEPTH_PCT or depth > CUP_MAX_DEPTH_PCT:
                continue

            # The cup low should be roughly in the middle, not at the very end
            after_low = after_lip.iloc[cup_low_pos:]
            if len(after_low) < CUP_MIN_AFTER_LOW:
                continue

            # Right side should recover close to left lip level
            right_high = float(after_low.max())
            right_high_pos = int(after_low.values.argmax())
            recovery_pct = (right_high - cup_low) / (left_lip - cup_low) * 100

            if recovery_pct < CUP_MIN_RECOVERY_PCT:
                continue  # Right side hasn't recovered enough

            # Look for handle: small pullback after right side recovery
            after_right_high = after_low.iloc[right_high_pos:]
            if len(after_right_high) < CUP_MIN_HANDLE_DAYS:
                # No handle yet, but cup is forming
                handle_low = float(after_low.iloc[-CUP_MIN_HANDLE_DAYS:].min()) if len(after_low) >= CUP_MIN_HANDLE_DAYS else cup_low
                handle_decline = (right_high - handle_low) / right_high * 100
            else:
                handle_low = float(after_right_high.min())
                handle_decline = (right_high - handle_low) / right_high * 100
                handle_length_days = len(after_right_high)
                handle_length_weeks = handle_length_days / 5

                if handle_length_weeks > HANDLE_MAX_LENGTH_WEEKS:
                    continue  # Handle too long
                if handle_decline > HANDLE_MAX_DECLINE_PCT:
                    continue  # Handle too deep

            # Total base length
            total_days = len(after_lip)
            total_weeks = total_days / 5
            if total_weeks < CUP_MIN_TOTAL_WEEKS or total_weeks > CUP_MAX_TOTAL_WEEKS:
                continue

            # Classify as regular or deep
            pattern_type = "Deep Cup & Handle" if depth > CUP_DEEP_THRESHOLD_PCT else "Cup & Handle"

            # Volume confirmation: declining volume in handle
            volume_confirm = False
            if "AvgVolume50" in df.columns and len(after_right_high) >= CUP_MIN_HANDLE_DAYS:
                abs_right_high_pos = len(df) - len(after_right_high)
                handle_vol = df["Volume"].iloc[abs_right_high_pos:].mean()
                cup_vol = df["Volume"].iloc[abs_pos:abs_right_high_pos].mean()
                if cup_vol > 0:
                    volume_confirm = handle_vol < cup_vol * CUP_HANDLE_VOLUME_FACTOR

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


class StockScanner:
    """Scans a list of tickers for base patterns using concurrent fetching."""

    def __init__(self, tickers: list[str], max_workers: int = DEFAULT_MAX_WORKERS):
        self.tickers = tickers
        self.max_workers = max_workers
        self.detector = PatternDetector()

    def _fetch_data(self, ticker: str) -> pd.DataFrame | None:
        """Fetch 2 years of historical data for a ticker."""
        try:
            t = yf.Ticker(ticker)
            df = t.history(period=DEFAULT_HISTORY_PERIOD)
            if df is None or len(df) < MIN_DATA_POINTS:
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
