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
