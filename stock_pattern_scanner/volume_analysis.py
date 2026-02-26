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
