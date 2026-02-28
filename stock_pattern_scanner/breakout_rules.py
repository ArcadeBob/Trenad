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
    SCORE_BREAKOUT_CLIMACTIC,
    SCORE_BREAKOUT_CONFIRMED,
    SCORE_BREAKOUT_MODERATE,
    SCORE_BREAKOUT_QUALITY_MAX,
    SCORE_BREAKOUT_STRONG,
    SCORE_BREAKOUT_WEAK,
    STOP_LOSS_PCT,
    VOLUME_SURGE_CLIMACTIC_PCT,
    VOLUME_SURGE_MODERATE_PCT,
    VOLUME_SURGE_STRONG_PCT,
    VOLUME_SURGE_WEAK_PCT,
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

    def evaluate(self) -> dict:
        """Evaluate breakout quality.

        Returns:
            Dict with stop_loss_price, profit_target_price,
            breakout_confirmed (True/False/None), volume_surge_pct,
            volume_grade, volume_grade_score.
        """
        df = self.df
        current_close = float(df["Close"].iloc[-1])
        distance_pct = (current_close - self.buy_point) / self.buy_point * 100

        result = {
            "stop_loss_price": self.stop_loss_price(),
            "profit_target_price": self.profit_target_price(),
            "breakout_confirmed": None,
            "volume_surge_pct": None,
            "volume_grade": "Weak",
            "volume_grade_score": SCORE_BREAKOUT_WEAK,
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

        # Grade volume surge
        grade_label, grade_score = self._volume_grade(result["volume_surge_pct"])
        result["volume_grade"] = grade_label
        result["volume_grade_score"] = grade_score

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
            return result["volume_grade_score"]
        return 0.0
