"""Sector relative strength analysis.

Compares 11 GICS sector ETFs against SPY to classify sectors
as leading, neutral, or lagging. Applies confidence score
adjustments based on sector strength.
"""

from __future__ import annotations

import logging

import pandas as pd
import yfinance

from constants import (
    RS_BASELINE,
    RS_PERIODS,
    RS_WEIGHTS,
    SECTOR_ETF_MAP,
    SECTOR_LAGGING_PENALTY,
    SECTOR_LAGGING_THRESHOLD,
    SECTOR_LEADING_BONUS,
    SECTOR_LEADING_THRESHOLD,
)

logger = logging.getLogger(__name__)


# Static ticker-to-sector mapping for common growth stocks
# Uses yfinance sector names (not GICS names)
_TICKER_SECTOR_MAP = {
    # Technology
    "AAPL": "Technology", "MSFT": "Technology", "NVDA": "Technology",
    "AMD": "Technology", "AVGO": "Technology", "QCOM": "Technology",
    "CRM": "Technology", "NOW": "Technology", "ADBE": "Technology",
    "ORCL": "Technology", "INTU": "Technology", "SNOW": "Technology",
    "NET": "Technology", "ZS": "Technology", "CRWD": "Technology",
    "PANW": "Technology", "FTNT": "Technology", "DDOG": "Technology",
    "MDB": "Technology", "SHOP": "Technology", "SQ": "Technology",
    "AMAT": "Technology", "KLAC": "Technology", "LRCX": "Technology",
    "MRVL": "Technology", "ON": "Technology", "MPWR": "Technology",
    "SNPS": "Technology", "CDNS": "Technology", "ANSS": "Technology",
    "TXN": "Technology", "MU": "Technology", "INTC": "Technology",
    # Communication Services
    "META": "Communication Services", "GOOGL": "Communication Services",
    "GOOG": "Communication Services", "NFLX": "Communication Services",
    "DIS": "Communication Services", "CMCSA": "Communication Services",
    "TMUS": "Communication Services",
    # Consumer Cyclical
    "AMZN": "Consumer Cyclical", "TSLA": "Consumer Cyclical",
    "HD": "Consumer Cyclical", "NKE": "Consumer Cyclical",
    "SBUX": "Consumer Cyclical", "TJX": "Consumer Cyclical",
    "BKNG": "Consumer Cyclical", "ABNB": "Consumer Cyclical",
    "LULU": "Consumer Cyclical", "CMG": "Consumer Cyclical",
    "DECK": "Consumer Cyclical", "RCL": "Consumer Cyclical",
    # Healthcare
    "UNH": "Healthcare", "LLY": "Healthcare", "JNJ": "Healthcare",
    "ABBV": "Healthcare", "MRK": "Healthcare", "PFE": "Healthcare",
    "TMO": "Healthcare", "ABT": "Healthcare", "ISRG": "Healthcare",
    "DXCM": "Healthcare", "VEEV": "Healthcare", "ALGN": "Healthcare",
    # Financial Services
    "JPM": "Financial Services", "BAC": "Financial Services",
    "GS": "Financial Services", "MS": "Financial Services",
    "V": "Financial Services", "MA": "Financial Services",
    "AXP": "Financial Services", "BLK": "Financial Services",
    "COIN": "Financial Services",
    # Industrials
    "CAT": "Industrials", "UNP": "Industrials", "HON": "Industrials",
    "GE": "Industrials", "RTX": "Industrials", "LMT": "Industrials",
    "DE": "Industrials", "BA": "Industrials", "FDX": "Industrials",
    "UPS": "Industrials",
    # Consumer Defensive
    "PG": "Consumer Defensive", "KO": "Consumer Defensive",
    "PEP": "Consumer Defensive", "COST": "Consumer Defensive",
    "WMT": "Consumer Defensive", "PM": "Consumer Defensive",
    # Energy
    "XOM": "Energy", "CVX": "Energy", "COP": "Energy",
    "SLB": "Energy", "EOG": "Energy",
    # Utilities
    "NEE": "Utilities", "DUK": "Utilities", "SO": "Utilities",
    # Real Estate
    "AMT": "Real Estate", "PLD": "Real Estate", "CCI": "Real Estate",
    # Basic Materials
    "LIN": "Basic Materials", "APD": "Basic Materials",
    "SHW": "Basic Materials", "FCX": "Basic Materials",
}


class SectorAnalyzer:
    """Analyze sector relative strength for pattern confidence scoring."""

    def __init__(self, spy_df: pd.DataFrame | None = None):
        self._spy_df = spy_df
        self._sector_rs_cache: dict[str, float] = {}
        self._sector_class_cache: dict[str, str] = {}
        self._etf_data_cache: dict[str, pd.DataFrame] = {}
        self._ticker_sector_cache: dict[str, str] = {}
        self._sector_overrides = _TICKER_SECTOR_MAP.copy()

    def _get_sector(self, ticker: str) -> str | None:
        """Get sector for a ticker. Uses static map, falls back to yfinance."""
        if ticker in self._ticker_sector_cache:
            return self._ticker_sector_cache[ticker]

        if ticker in self._sector_overrides:
            sector = self._sector_overrides[ticker]
            self._ticker_sector_cache[ticker] = sector
            return sector

        # Fallback: fetch from yfinance
        try:
            info = yfinance.Ticker(ticker).info
            sector = info.get("sector")
            if sector:
                self._ticker_sector_cache[ticker] = sector
                return sector
        except Exception:
            logger.debug("Failed to fetch sector for %s", ticker, exc_info=True)
        return None

    def _fetch_etf_data(self, etf: str) -> pd.DataFrame | None:
        """Fetch 1 year of daily data for a sector ETF."""
        if etf in self._etf_data_cache:
            return self._etf_data_cache[etf]
        try:
            df = yfinance.download(etf, period="1y", progress=False)
            if df is not None and len(df) >= 60:
                self._etf_data_cache[etf] = df
                return df
        except Exception:
            logger.debug("Failed to fetch ETF data for %s", etf, exc_info=True)
        return None

    def _compute_rs(self, sector_df: pd.DataFrame,
                    spy_df: pd.DataFrame) -> float:
        """Compute RS of sector ETF vs SPY using same formula as stock RS."""
        sector_close = sector_df["Close"]
        spy_close = spy_df["Close"]

        weighted_sector = 0.0
        weighted_spy = 0.0

        for period, weight in zip(RS_PERIODS, RS_WEIGHTS):
            if len(sector_close) >= period and len(spy_close) >= period:
                s_ret = float(sector_close.iloc[-1]) / float(sector_close.iloc[-period]) - 1
                spy_ret = float(spy_close.iloc[-1]) / float(spy_close.iloc[-period]) - 1
                weighted_sector += s_ret * 100 * weight
                weighted_spy += spy_ret * 100 * weight
            else:
                weighted_sector += 0.0
                weighted_spy += 0.0

        rs_raw = RS_BASELINE + (weighted_sector - weighted_spy)
        return max(1, min(99, rs_raw))

    def _classify(self, rs: float) -> str:
        """Classify sector RS as leading/neutral/lagging."""
        if rs >= SECTOR_LEADING_THRESHOLD:
            return "leading"
        if rs < SECTOR_LAGGING_THRESHOLD:
            return "lagging"
        return "neutral"

    def load_sector_data(self, spy_df: pd.DataFrame):
        """Pre-load all sector ETF data and compute RS scores.

        Call once at start of scan to avoid repeated fetches.
        """
        self._spy_df = spy_df
        for sector_name, etf in SECTOR_ETF_MAP.items():
            etf_df = self._fetch_etf_data(etf)
            if etf_df is not None and spy_df is not None:
                rs = self._compute_rs(etf_df, spy_df)
                self._sector_rs_cache[sector_name] = rs
                self._sector_class_cache[sector_name] = self._classify(rs)

    def get_sector_info(self, ticker: str) -> dict:
        """Get sector RS info for a ticker.

        Returns:
            dict with keys: sector, sector_rs, sector_class
        """
        sector = self._get_sector(ticker)
        if not sector or sector not in self._sector_rs_cache:
            return {
                "sector": sector or "Unknown",
                "sector_rs": None,
                "sector_class": "neutral",
            }
        return {
            "sector": sector,
            "sector_rs": round(self._sector_rs_cache[sector], 1),
            "sector_class": self._sector_class_cache[sector],
        }

    @staticmethod
    def confidence_adjustment(sector_class: str) -> float:
        """Return confidence score adjustment for sector classification."""
        if sector_class == "leading":
            return SECTOR_LEADING_BONUS
        if sector_class == "lagging":
            return SECTOR_LAGGING_PENALTY
        return 0
