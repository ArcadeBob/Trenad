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
