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
        """ATR(14) / current price * 100.

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
