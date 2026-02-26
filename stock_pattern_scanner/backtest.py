"""Walk-forward backtest engine for pattern validation.

Replays pattern detection on historical data at weekly intervals,
simulates trades with configurable stop-loss and profit-target,
and computes performance metrics with breakdowns.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Callable, Optional

import pandas as pd

from breakout_rules import BreakoutAnalyzer
from constants import (
    BACKTEST_DEFAULT_MIN_CONFIDENCE,
    BACKTEST_DEFAULT_PROFIT_TARGET_PCT,
    BACKTEST_DEFAULT_STOP_LOSS_PCT,
    BACKTEST_SCAN_INTERVAL_DAYS,
    MIN_DATA_POINTS,
)
from market_regime import MarketRegime
from pattern_scanner import PatternDetector
from trend_strength import TrendAnalyzer
from volume_analysis import VolumeAnalyzer

logger = logging.getLogger(__name__)


@dataclass
class BacktestConfig:
    """Configuration for a single backtest run."""

    stop_loss_pct: float = BACKTEST_DEFAULT_STOP_LOSS_PCT
    profit_target_pct: float = BACKTEST_DEFAULT_PROFIT_TARGET_PCT
    min_confidence: float = BACKTEST_DEFAULT_MIN_CONFIDENCE


class BacktestEngine:
    """Walk-forward backtest engine.

    Given pre-fetched OHLCV data for each ticker and SPY,
    walks forward through historical dates at weekly intervals,
    runs pattern detection on data available up to each date,
    and simulates trades.
    """

    def __init__(
        self,
        ticker_data: dict[str, pd.DataFrame],
        spy_data: pd.DataFrame,
        config: BacktestConfig | None = None,
    ):
        self.ticker_data = ticker_data
        self.spy_data = spy_data
        self.config = config or BacktestConfig()
        self.detector = PatternDetector()

    def _detect_patterns_at(
        self, ticker: str, df_slice: pd.DataFrame, spy_slice: pd.DataFrame
    ) -> list[dict]:
        """Run pattern detection on data up to a given date.

        Returns list of dicts with pattern info + confidence score.
        """
        if len(df_slice) < MIN_DATA_POINTS:
            return []

        df = self.detector.add_moving_averages(df_slice.copy())

        # Trend strength
        trend_analyzer = TrendAnalyzer(df)
        if trend_analyzer.is_too_volatile():
            return []
        trend_score = trend_analyzer.score()

        rs_rating = self.detector.calculate_relative_strength(df, spy_slice)

        results = []
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

                # Volume analysis
                base_start = pattern.get(
                    "base_start_idx",
                    len(df) - pattern.get("base_length_weeks", 5) * 5,
                )
                base_end = len(df) - 1
                vol_analyzer = VolumeAnalyzer(df, base_start, base_end)
                if vol_analyzer.is_distributing():
                    continue
                volume_score = vol_analyzer.score()

                # Breakout analysis
                breakout_analyzer = BreakoutAnalyzer(df, pattern["buy_point"])
                breakout_score = breakout_analyzer.score()

                confidence = self.detector.calculate_confidence(
                    pattern, df,
                    volume_score=volume_score,
                    trend_score=trend_score,
                    rs_rating=rs_rating,
                    breakout_score=breakout_score,
                )

                if confidence < self.config.min_confidence:
                    continue

                results.append({
                    "ticker": ticker,
                    "pattern_type": pattern["pattern_type"],
                    "confidence_score": round(confidence, 1),
                    "buy_point": pattern["buy_point"],
                })
            except Exception as e:
                logger.debug("Detection error for %s: %s", ticker, e)

        return results

    def _simulate_trade(
        self, ticker: str, buy_point: float, pattern_type: str,
        confidence_score: float, detection_date: str,
        df_after: pd.DataFrame, market_regime: str,
    ) -> dict | None:
        """Simulate a single trade from detection date forward.

        Walks through df_after day by day looking for:
        1. Entry: price crosses buy_point
        2. Exit: price hits stop-loss or profit-target
        """
        stop_price = buy_point * (1 - self.config.stop_loss_pct / 100)
        target_price = buy_point * (1 + self.config.profit_target_pct / 100)

        entry_date = None
        entry_price = None

        for i in range(len(df_after)):
            row = df_after.iloc[i]
            date_str = str(df_after.index[i].date())
            high = float(row["High"])
            low = float(row["Low"])

            # Phase 1: waiting for entry
            if entry_date is None:
                if high >= buy_point:
                    entry_date = date_str
                    entry_price = buy_point  # assume fill at pivot
                    # Check if same day hits stop or target
                    if low <= stop_price:
                        return self._trade_dict(
                            ticker, pattern_type, confidence_score,
                            detection_date, entry_date, entry_price,
                            date_str, stop_price, "stop",
                            market_regime,
                        )
                    if high >= target_price:
                        return self._trade_dict(
                            ticker, pattern_type, confidence_score,
                            detection_date, entry_date, entry_price,
                            date_str, target_price, "target",
                            market_regime,
                        )
                continue

            # Phase 2: in trade, check exits
            if low <= stop_price:
                return self._trade_dict(
                    ticker, pattern_type, confidence_score,
                    detection_date, entry_date, entry_price,
                    date_str, stop_price, "stop",
                    market_regime,
                )
            if high >= target_price:
                return self._trade_dict(
                    ticker, pattern_type, confidence_score,
                    detection_date, entry_date, entry_price,
                    date_str, target_price, "target",
                    market_regime,
                )

        # Trade never entered or never hit stop/target
        if entry_date is None:
            return None  # Price never reached buy_point

        # Still open at end of data
        last_close = float(df_after["Close"].iloc[-1])
        last_date = str(df_after.index[-1].date())
        return self._trade_dict(
            ticker, pattern_type, confidence_score,
            detection_date, entry_date, entry_price,
            last_date, last_close, "open",
            market_regime,
        )

    @staticmethod
    def _trade_dict(
        ticker: str, pattern_type: str, confidence_score: float,
        detection_date: str, entry_date: str, entry_price: float,
        exit_date: str, exit_price: float, exit_reason: str,
        market_regime: str,
    ) -> dict:
        pnl_pct = round((exit_price - entry_price) / entry_price * 100, 2)
        return {
            "ticker": ticker,
            "pattern_type": pattern_type,
            "confidence_score": confidence_score,
            "detection_date": detection_date,
            "entry_date": entry_date,
            "entry_price": round(entry_price, 2),
            "exit_date": exit_date,
            "exit_price": round(exit_price, 2),
            "exit_reason": exit_reason,
            "pnl_pct": pnl_pct,
            "market_regime": market_regime,
        }

    def run(
        self,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> list[dict]:
        """Execute the walk-forward backtest.

        Returns list of trade dicts.
        """
        interval = BACKTEST_SCAN_INTERVAL_DAYS

        # Find the common date range across all tickers
        all_dates = self.spy_data.index
        if len(all_dates) < MIN_DATA_POINTS + interval:
            return []

        # Scan checkpoints: every `interval` days after warmup
        start_idx = MIN_DATA_POINTS
        checkpoints = list(range(start_idx, len(all_dates), interval))
        total_steps = len(checkpoints) * len(self.ticker_data)
        step = 0

        # Track open trades per ticker for deduplication
        open_trades: dict[str, dict] = {}
        all_trades: list[dict] = []

        for cp_idx in checkpoints:
            cp_date = all_dates[cp_idx]

            # Get SPY data up to checkpoint for regime detection
            spy_slice = self.spy_data.iloc[:cp_idx + 1]
            spy_with_ma = self.detector.add_moving_averages(spy_slice.copy())

            regime = MarketRegime(spy_with_ma)
            regime_eval = regime.evaluate()
            regime_status = regime_eval["status"]

            # Check if any open trades should be closed by now
            for ticker in list(open_trades.keys()):
                trade = open_trades[ticker]
                full_df = self.ticker_data[ticker]
                # Get data from entry to current checkpoint
                mask = (full_df.index >= pd.Timestamp(trade["entry_date"])) & (
                    full_df.index <= cp_date
                )
                sub = full_df.loc[mask]
                stop_price = trade["entry_price"] * (1 - self.config.stop_loss_pct / 100)
                target_price = trade["entry_price"] * (1 + self.config.profit_target_pct / 100)

                closed = False
                for j in range(len(sub)):
                    row = sub.iloc[j]
                    d = str(sub.index[j].date())
                    if d <= trade["entry_date"]:
                        continue
                    if float(row["Low"]) <= stop_price:
                        trade["exit_date"] = d
                        trade["exit_price"] = round(stop_price, 2)
                        trade["exit_reason"] = "stop"
                        trade["pnl_pct"] = round(
                            (stop_price - trade["entry_price"]) / trade["entry_price"] * 100, 2
                        )
                        all_trades.append(trade)
                        del open_trades[ticker]
                        closed = True
                        break
                    if float(row["High"]) >= target_price:
                        trade["exit_date"] = d
                        trade["exit_price"] = round(target_price, 2)
                        trade["exit_reason"] = "target"
                        trade["pnl_pct"] = round(
                            (target_price - trade["entry_price"]) / trade["entry_price"] * 100, 2
                        )
                        all_trades.append(trade)
                        del open_trades[ticker]
                        closed = True
                        break

            # Skip pattern detection if market is in correction
            if regime_status == "correction":
                step += len(self.ticker_data)
                if progress_callback:
                    progress_callback(min(step, total_steps), total_steps)
                continue

            for ticker, full_df in self.ticker_data.items():
                step += 1

                # Skip if already have an open trade for this ticker
                if ticker in open_trades:
                    if progress_callback:
                        progress_callback(min(step, total_steps), total_steps)
                    continue

                # Slice data up to checkpoint date
                df_slice = full_df.loc[full_df.index <= cp_date]
                if len(df_slice) < MIN_DATA_POINTS:
                    if progress_callback:
                        progress_callback(min(step, total_steps), total_steps)
                    continue

                spy_for_rs = self.spy_data.loc[self.spy_data.index <= cp_date]

                patterns = self._detect_patterns_at(ticker, df_slice, spy_for_rs)

                for p in patterns:
                    # Simulate trade forward from this checkpoint
                    df_after = full_df.loc[full_df.index > cp_date]
                    if len(df_after) == 0:
                        continue

                    detection_date = str(cp_date.date())
                    trade = self._simulate_trade(
                        ticker=p["ticker"],
                        buy_point=p["buy_point"],
                        pattern_type=p["pattern_type"],
                        confidence_score=p["confidence_score"],
                        detection_date=detection_date,
                        df_after=df_after,
                        market_regime=regime_status,
                    )

                    if trade is None:
                        continue

                    if trade["exit_reason"] == "open":
                        # Track as open — will be resolved at next checkpoint or end
                        open_trades[ticker] = trade
                    else:
                        all_trades.append(trade)
                    break  # Only one trade per ticker per checkpoint

                if progress_callback:
                    progress_callback(min(step, total_steps), total_steps)

        # Close remaining open trades at last available price
        for ticker, trade in open_trades.items():
            full_df = self.ticker_data[ticker]
            last_close = float(full_df["Close"].iloc[-1])
            last_date = str(full_df.index[-1].date())
            trade["exit_date"] = last_date
            trade["exit_price"] = round(last_close, 2)
            trade["exit_reason"] = "open"
            trade["pnl_pct"] = round(
                (last_close - trade["entry_price"]) / trade["entry_price"] * 100, 2
            )
            all_trades.append(trade)

        # Sort by detection date
        all_trades.sort(key=lambda t: t["detection_date"])
        return all_trades


def compute_metrics(trades: list[dict]) -> dict:
    """Compute performance metrics and breakdowns from a list of trade dicts.

    Returns dict with overall metrics and breakdowns by pattern, confidence, regime.
    """
    if not trades:
        return {
            "total_trades": 0,
            "win_rate": 0.0,
            "avg_return": 0.0,
            "profit_factor": 0.0,
            "avg_win": 0.0,
            "avg_loss": 0.0,
            "expectancy": 0.0,
            "by_pattern": {},
            "by_confidence": {},
            "by_regime": {},
        }

    closed = [t for t in trades if t["exit_reason"] != "open"]
    wins = [t for t in closed if t["pnl_pct"] > 0]
    losses = [t for t in closed if t["pnl_pct"] <= 0]

    total = len(trades)
    total_closed = len(closed)
    win_rate = (len(wins) / total_closed * 100) if total_closed > 0 else 0.0
    avg_return = sum(t["pnl_pct"] for t in trades) / total if total > 0 else 0.0

    gross_wins = sum(t["pnl_pct"] for t in wins)
    gross_losses = abs(sum(t["pnl_pct"] for t in losses))
    profit_factor = (gross_wins / gross_losses) if gross_losses > 0 else float("inf") if gross_wins > 0 else 0.0

    avg_win = (sum(t["pnl_pct"] for t in wins) / len(wins)) if wins else 0.0
    avg_loss = (sum(t["pnl_pct"] for t in losses) / len(losses)) if losses else 0.0

    expectancy = avg_return

    result = {
        "total_trades": total,
        "win_rate": round(win_rate, 1),
        "avg_return": round(avg_return, 2),
        "profit_factor": round(profit_factor, 2) if profit_factor != float("inf") else float("inf"),
        "avg_win": round(avg_win, 2),
        "avg_loss": round(avg_loss, 2),
        "expectancy": round(expectancy, 2),
        "by_pattern": _breakdown(trades, "pattern_type"),
        "by_confidence": _breakdown_by_confidence(trades),
        "by_regime": _breakdown(trades, "market_regime"),
    }
    return result


def _breakdown(trades: list[dict], key: str) -> dict:
    """Group trades by a key and compute win rate + avg return for each group."""
    groups: dict[str, list[dict]] = {}
    for t in trades:
        val = t.get(key, "unknown")
        groups.setdefault(val, []).append(t)

    result = {}
    for name, group in sorted(groups.items()):
        closed = [t for t in group if t["exit_reason"] != "open"]
        wins = [t for t in closed if t["pnl_pct"] > 0]
        total = len(group)
        total_closed = len(closed)
        win_rate = (len(wins) / total_closed * 100) if total_closed > 0 else 0.0
        avg_ret = sum(t["pnl_pct"] for t in group) / total if total > 0 else 0.0
        result[name] = {
            "total": total,
            "win_rate": round(win_rate, 1),
            "avg_return": round(avg_ret, 2),
        }
    return result


def _breakdown_by_confidence(trades: list[dict]) -> dict:
    """Group trades into confidence bands: 40-60, 60-80, 80-100."""
    bands = {"40-60": [], "60-80": [], "80-100": []}
    for t in trades:
        score = t.get("confidence_score", 0)
        if score >= 80:
            bands["80-100"].append(t)
        elif score >= 60:
            bands["60-80"].append(t)
        else:
            bands["40-60"].append(t)

    result = {}
    for band_name, group in bands.items():
        if not group:
            continue
        closed = [t for t in group if t["exit_reason"] != "open"]
        wins = [t for t in closed if t["pnl_pct"] > 0]
        total = len(group)
        total_closed = len(closed)
        win_rate = (len(wins) / total_closed * 100) if total_closed > 0 else 0.0
        avg_ret = sum(t["pnl_pct"] for t in group) / total if total > 0 else 0.0
        result[band_name] = {
            "total": total,
            "win_rate": round(win_rate, 1),
            "avg_return": round(avg_ret, 2),
        }
    return result
