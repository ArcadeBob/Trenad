"""Market regime detection using SPY data.

Determines whether the overall market is in a confirmed uptrend,
under pressure, or in correction. Used as a hard gate by the scanner.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from constants import (
    REGIME_CORRECTION_CONFIDENCE_PENALTY,
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
            distribution_days, ma50_slope_rising, confidence_penalty.

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

        # Confidence penalty by regime
        if status == "correction":
            penalty = REGIME_CORRECTION_CONFIDENCE_PENALTY
        else:
            penalty = 0

        return {
            "status": status,
            "spy_above_200ma": above_200,
            "spy_above_50ma": above_50,
            "distribution_days": dist_days,
            "ma50_slope_rising": slope_rising,
            "confidence_penalty": penalty,
        }
