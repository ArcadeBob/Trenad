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
