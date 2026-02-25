"""Core pattern detection engine for stock base pattern scanning."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict

import numpy as np
import pandas as pd
from scipy.signal import argrelextrema


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
        periods = [63, 126, 189, 252]
        weights = [0.4, 0.2, 0.2, 0.2]

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

        rs_raw = 50 + (weighted_stock - weighted_spy)
        return max(1, min(99, round(rs_raw, 1)))

    def _has_prior_uptrend(self, df: pd.DataFrame, end_idx: int, min_gain: float = 30.0) -> bool:
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
        lookback = 126  # ~6 months of trading days
        start_idx = max(0, end_idx - lookback)
        segment = df["Close"].iloc[start_idx:end_idx]

        if len(segment) < 20:
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
        if len(df) < 200:
            return None

        # --- Identify tight consolidation ------------------------------------
        # Start with a narrow window (25 days = 5 weeks minimum) to get the
        # core consolidation range, then expand backward while the range
        # stays tight (< 15 %).
        full_close = df["Close"].values
        end_pos = len(df) - 1
        max_window = min(75, len(df))

        # Seed range from the most recent 25 days
        seed = full_close[end_pos - 24 : end_pos + 1]
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
        floor = base_low - seed_range * 0.5

        base_start = end_pos - 24
        for i in range(end_pos - 25, end_pos - max_window, -1):
            if i < 0:
                break
            price = full_close[i]
            if price < floor:
                break
            new_high = max(base_high, price)
            new_low = min(base_low, price)
            depth = (new_high - new_low) / new_high * 100
            if depth >= 15.0:
                break
            base_high = new_high
            base_low = new_low
            base_start = i

        depth_pct = (base_high - base_low) / base_high * 100

        if depth_pct >= 15.0:
            return None

        base_length = end_pos - base_start + 1

        # Must be at least 5 weeks (~25 trading days)
        if base_length < 25:
            return None

        # --- Prior uptrend check ----------------------------------------
        if not self._has_prior_uptrend(df, base_start, min_gain=30.0):
            return None

        # --- 50-day MA check --------------------------------------------
        if "MA50" not in df.columns:
            return None

        base_slice = df.iloc[base_start: end_pos + 1]
        ma50_valid = base_slice["MA50"].dropna()
        if len(ma50_valid) == 0:
            return None

        close_above_ma50 = (base_slice.loc[ma50_valid.index, "Close"] > ma50_valid).sum()
        if close_above_ma50 / len(ma50_valid) <= 0.50:
            return None

        # --- Volume contraction -----------------------------------------
        base_avg_vol = base_slice["Volume"].mean()
        prior_start = max(0, base_start - 50)
        prior_avg_vol = df["Volume"].iloc[prior_start:base_start].mean()

        volume_ok = bool(base_avg_vol < prior_avg_vol * 0.90) if prior_avg_vol > 0 else False

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
        if len(df) < 200:
            return None

        closes = df["Close"]

        # Look in the last ~9 months for the pattern
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

        # Double bottom typically 15-40% deep
        if depth < 15 or depth > 40:
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
            right_high_pos = int(after_low.values.argmax())
            recovery_pct = (right_high - cup_low) / (left_lip - cup_low) * 100

            if recovery_pct < 70:
                continue  # Right side hasn't recovered enough

            # Look for handle: small pullback after right side recovery
            after_right_high = after_low.iloc[right_high_pos:]
            if len(after_right_high) < 5:
                # No handle yet, but cup is forming
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
