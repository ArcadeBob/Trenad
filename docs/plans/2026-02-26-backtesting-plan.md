# Backtesting Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a walk-forward backtest engine that replays pattern detection on historical data, simulates trades with configurable stop-loss/profit-target, and displays breakdown metrics in a new dashboard tab.

**Architecture:** New `backtest.py` module reuses existing `PatternDetector`, `MarketRegime`, `VolumeAnalyzer`, `TrendAnalyzer`, and `BreakoutAnalyzer`. New DB tables (`backtests`, `backtest_trades`) in existing `ScanDatabase`. Three new API endpoints. New "Backtest" tab in the dashboard HTML.

**Tech Stack:** Python 3.13, pandas, numpy, yfinance, FastAPI, SQLite (all existing — no new dependencies)

---

## Task 1: Add Backtest Constants

**Files:**
- Modify: `stock_pattern_scanner/constants.py`

**Step 1: Append backtest constants to constants.py**

Add to the end of `stock_pattern_scanner/constants.py`:

```python
# ---------------------------------------------------------------------------
# Backtesting
# ---------------------------------------------------------------------------
BACKTEST_SCAN_INTERVAL_DAYS = 5
BACKTEST_DEFAULT_STOP_LOSS_PCT = 7.0
BACKTEST_DEFAULT_PROFIT_TARGET_PCT = 20.0
BACKTEST_DEFAULT_MIN_CONFIDENCE = 40.0
BACKTEST_MAX_OPEN_TRADES_PER_TICKER = 1
```

**Step 2: Verify importable**

Run: `cd stock_pattern_scanner && python -c "from constants import BACKTEST_SCAN_INTERVAL_DAYS; print('OK')"`
Expected: `OK`

**Step 3: Commit**

```bash
git add stock_pattern_scanner/constants.py
git commit -m "feat(backtest): add backtest constants"
```

---

## Task 2: Add Backtest DB Tables

**Files:**
- Modify: `stock_pattern_scanner/database.py`
- Test: `stock_pattern_scanner/tests/test_database.py`

**Step 1: Write failing tests for backtest DB methods**

Add to the end of `stock_pattern_scanner/tests/test_database.py`:

```python
def test_create_backtest(tmp_db):
    bt_id = tmp_db.create_backtest(
        watchlist="default",
        tickers=["AAPL", "MSFT"],
        stop_loss_pct=7.0,
        profit_target_pct=20.0,
        min_confidence=40.0,
    )
    assert isinstance(bt_id, str)
    assert len(bt_id) > 0


def test_backtest_progress(tmp_db):
    bt_id = tmp_db.create_backtest(
        watchlist="default", tickers=["AAPL"],
        stop_loss_pct=7.0, profit_target_pct=20.0, min_confidence=40.0,
    )
    tmp_db.update_backtest_progress(bt_id, current=5, total=50)
    progress = tmp_db.get_backtest_progress(bt_id)
    assert progress["current"] == 5
    assert progress["total"] == 50
    assert progress["status"] == "running"


def test_save_and_get_backtest_trades(tmp_db):
    bt_id = tmp_db.create_backtest(
        watchlist="default", tickers=["AAPL"],
        stop_loss_pct=7.0, profit_target_pct=20.0, min_confidence=40.0,
    )
    trades = [
        {
            "ticker": "AAPL",
            "pattern_type": "Flat Base",
            "confidence_score": 72.0,
            "detection_date": "2025-06-15",
            "entry_date": "2025-06-18",
            "entry_price": 150.0,
            "exit_date": "2025-07-10",
            "exit_price": 180.0,
            "exit_reason": "target",
            "pnl_pct": 20.0,
            "market_regime": "confirmed_uptrend",
        },
    ]
    tmp_db.save_backtest_trades(bt_id, trades)
    tmp_db.update_backtest_status(bt_id, "completed")
    tmp_db.save_backtest_summary(bt_id, total_trades=1, win_rate=100.0, profit_factor=999.0)

    result = tmp_db.get_backtest_trades(bt_id)
    assert len(result) == 1
    assert result[0]["ticker"] == "AAPL"
    assert result[0]["pnl_pct"] == 20.0

    summary = tmp_db.get_backtest_summary(bt_id)
    assert summary["total_trades"] == 1
    assert summary["win_rate"] == 100.0
    assert summary["status"] == "completed"
```

**Step 2: Run tests to verify they fail**

Run: `cd stock_pattern_scanner && python -m pytest tests/test_database.py::test_create_backtest -v`
Expected: FAIL — `AttributeError: 'ScanDatabase' object has no attribute 'create_backtest'`

**Step 3: Add backtest tables and methods to database.py**

In `stock_pattern_scanner/database.py`, add the new tables inside `_init_db` after the existing `CREATE TABLE` statements, and add the new methods.

Add inside `_init_db`, after the existing `executescript` call but before the migration block:

```python
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS backtests (
                    backtest_id TEXT PRIMARY KEY,
                    watchlist TEXT,
                    tickers TEXT,
                    stop_loss_pct REAL,
                    profit_target_pct REAL,
                    min_confidence REAL,
                    status TEXT DEFAULT 'running',
                    created_at TEXT,
                    completed_at TEXT,
                    progress_current INTEGER DEFAULT 0,
                    progress_total INTEGER DEFAULT 0,
                    total_trades INTEGER DEFAULT 0,
                    win_rate REAL DEFAULT 0,
                    profit_factor REAL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS backtest_trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    backtest_id TEXT,
                    ticker TEXT,
                    pattern_type TEXT,
                    confidence_score REAL,
                    detection_date TEXT,
                    entry_date TEXT,
                    entry_price REAL,
                    exit_date TEXT,
                    exit_price REAL,
                    exit_reason TEXT,
                    pnl_pct REAL,
                    market_regime TEXT,
                    FOREIGN KEY (backtest_id) REFERENCES backtests(backtest_id)
                );
            """)
```

Add these methods to the `ScanDatabase` class:

```python
    def create_backtest(
        self, watchlist: str, tickers: list[str],
        stop_loss_pct: float, profit_target_pct: float, min_confidence: float,
    ) -> str:
        bt_id = str(uuid.uuid4())[:8]
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO backtests
                   (backtest_id, watchlist, tickers, stop_loss_pct, profit_target_pct,
                    min_confidence, status, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (bt_id, watchlist, json.dumps(tickers), stop_loss_pct,
                 profit_target_pct, min_confidence, "running",
                 datetime.now().isoformat()),
            )
        return bt_id

    def update_backtest_progress(self, bt_id: str, current: int, total: int):
        with self._connect() as conn:
            conn.execute(
                "UPDATE backtests SET progress_current=?, progress_total=? WHERE backtest_id=?",
                (current, total, bt_id),
            )

    def get_backtest_progress(self, bt_id: str) -> dict:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM backtests WHERE backtest_id=?", (bt_id,),
            ).fetchone()
        if row is None:
            return {"current": 0, "total": 0, "status": "not_found"}
        return {
            "current": row["progress_current"],
            "total": row["progress_total"],
            "status": row["status"],
        }

    def update_backtest_status(self, bt_id: str, status: str):
        completed_at = datetime.now().isoformat() if status == "completed" else None
        with self._connect() as conn:
            conn.execute(
                "UPDATE backtests SET status=?, completed_at=? WHERE backtest_id=?",
                (status, completed_at, bt_id),
            )

    def save_backtest_trades(self, bt_id: str, trades: list[dict]):
        with self._connect() as conn:
            for t in trades:
                conn.execute(
                    """INSERT INTO backtest_trades
                       (backtest_id, ticker, pattern_type, confidence_score,
                        detection_date, entry_date, entry_price, exit_date,
                        exit_price, exit_reason, pnl_pct, market_regime)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (bt_id, t["ticker"], t["pattern_type"], t["confidence_score"],
                     t["detection_date"], t["entry_date"], t["entry_price"],
                     t["exit_date"], t["exit_price"], t["exit_reason"],
                     t["pnl_pct"], t["market_regime"]),
                )

    def save_backtest_summary(self, bt_id: str, total_trades: int, win_rate: float, profit_factor: float):
        with self._connect() as conn:
            conn.execute(
                "UPDATE backtests SET total_trades=?, win_rate=?, profit_factor=? WHERE backtest_id=?",
                (total_trades, win_rate, profit_factor, bt_id),
            )

    def get_backtest_trades(self, bt_id: str) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM backtest_trades WHERE backtest_id=? ORDER BY detection_date",
                (bt_id,),
            ).fetchall()
        return [
            {
                "ticker": row["ticker"],
                "pattern_type": row["pattern_type"],
                "confidence_score": row["confidence_score"],
                "detection_date": row["detection_date"],
                "entry_date": row["entry_date"],
                "entry_price": row["entry_price"],
                "exit_date": row["exit_date"],
                "exit_price": row["exit_price"],
                "exit_reason": row["exit_reason"],
                "pnl_pct": row["pnl_pct"],
                "market_regime": row["market_regime"],
            }
            for row in rows
        ]

    def get_backtest_summary(self, bt_id: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM backtests WHERE backtest_id=?", (bt_id,),
            ).fetchone()
        if row is None:
            return None
        return {
            "backtest_id": row["backtest_id"],
            "watchlist": row["watchlist"],
            "tickers": json.loads(row["tickers"]),
            "stop_loss_pct": row["stop_loss_pct"],
            "profit_target_pct": row["profit_target_pct"],
            "min_confidence": row["min_confidence"],
            "status": row["status"],
            "created_at": row["created_at"],
            "completed_at": row["completed_at"],
            "total_trades": row["total_trades"],
            "win_rate": row["win_rate"],
            "profit_factor": row["profit_factor"],
        }
```

**Step 4: Run tests to verify they pass**

Run: `cd stock_pattern_scanner && python -m pytest tests/test_database.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add stock_pattern_scanner/database.py stock_pattern_scanner/tests/test_database.py
git commit -m "feat(backtest): add backtest DB tables and CRUD methods"
```

---

## Task 3: Create Backtest Engine

This is the core module. It walks forward through historical data, runs pattern detection at each checkpoint, and simulates trades.

**Files:**
- Create: `stock_pattern_scanner/backtest.py`
- Create: `stock_pattern_scanner/tests/test_backtest.py`

**Step 1: Write failing tests for the backtest engine**

Create `stock_pattern_scanner/tests/test_backtest.py`:

```python
"""Tests for the backtest engine."""

from __future__ import annotations

import pandas as pd
import numpy as np
import pytest

from backtest import BacktestEngine, BacktestConfig, compute_metrics


@pytest.fixture
def flat_uptrend_df():
    """Build ~300 days of data: 150 days of uptrend, then 150 days of flat consolidation.

    This should trigger a Flat Base detection when scanned at the end.
    """
    n = 300
    dates = pd.bdate_range(end="2026-01-15", periods=n)

    # Phase 1: uptrend from 80 to 150 (days 0-149)
    uptrend = np.linspace(80, 150, 150)
    # Phase 2: flat consolidation between 145-155 (days 150-299)
    rng = np.random.RandomState(42)
    flat = 150 + rng.uniform(-3, 3, 150)

    closes = np.concatenate([uptrend, flat])
    volumes = np.concatenate([
        rng.randint(800_000, 1_500_000, 150),
        rng.randint(400_000, 700_000, 150),  # volume contraction
    ]).astype(float)

    return pd.DataFrame({
        "Open": closes * 0.999,
        "High": closes * 1.005,
        "Low": closes * 0.995,
        "Close": closes,
        "Volume": volumes,
    }, index=dates)


@pytest.fixture
def spy_uptrend_df():
    """SPY in a steady uptrend (no correction regime)."""
    n = 500
    dates = pd.bdate_range(end="2026-01-15", periods=n)
    closes = np.linspace(400, 500, n)
    volumes = np.full(n, 50_000_000.0)
    return pd.DataFrame({
        "Open": closes * 0.999,
        "High": closes * 1.003,
        "Low": closes * 0.997,
        "Close": closes,
        "Volume": volumes,
    }, index=dates)


class TestBacktestConfig:
    def test_defaults(self):
        cfg = BacktestConfig()
        assert cfg.stop_loss_pct == 7.0
        assert cfg.profit_target_pct == 20.0
        assert cfg.min_confidence == 40.0

    def test_custom(self):
        cfg = BacktestConfig(stop_loss_pct=5.0, profit_target_pct=15.0)
        assert cfg.stop_loss_pct == 5.0
        assert cfg.profit_target_pct == 15.0


class TestComputeMetrics:
    def test_empty_trades(self):
        m = compute_metrics([])
        assert m["total_trades"] == 0
        assert m["win_rate"] == 0.0
        assert m["profit_factor"] == 0.0

    def test_all_wins(self):
        trades = [
            {"pnl_pct": 20.0, "exit_reason": "target", "pattern_type": "Flat Base",
             "confidence_score": 75.0, "market_regime": "confirmed_uptrend",
             "ticker": "AAPL", "detection_date": "2025-06-01",
             "entry_date": "2025-06-05", "entry_price": 100.0,
             "exit_date": "2025-07-01", "exit_price": 120.0},
            {"pnl_pct": 15.0, "exit_reason": "target", "pattern_type": "Cup & Handle",
             "confidence_score": 80.0, "market_regime": "confirmed_uptrend",
             "ticker": "MSFT", "detection_date": "2025-06-10",
             "entry_date": "2025-06-15", "entry_price": 200.0,
             "exit_date": "2025-07-20", "exit_price": 230.0},
        ]
        m = compute_metrics(trades)
        assert m["total_trades"] == 2
        assert m["win_rate"] == 100.0
        assert m["avg_return"] == 17.5
        assert m["profit_factor"] == float("inf")

    def test_mixed_trades(self):
        trades = [
            {"pnl_pct": 20.0, "exit_reason": "target", "pattern_type": "Flat Base",
             "confidence_score": 75.0, "market_regime": "confirmed_uptrend",
             "ticker": "AAPL", "detection_date": "2025-06-01",
             "entry_date": "2025-06-05", "entry_price": 100.0,
             "exit_date": "2025-07-01", "exit_price": 120.0},
            {"pnl_pct": -7.0, "exit_reason": "stop", "pattern_type": "Double Bottom",
             "confidence_score": 55.0, "market_regime": "uptrend_under_pressure",
             "ticker": "TSLA", "detection_date": "2025-07-01",
             "entry_date": "2025-07-05", "entry_price": 300.0,
             "exit_date": "2025-07-15", "exit_price": 279.0},
        ]
        m = compute_metrics(trades)
        assert m["total_trades"] == 2
        assert m["win_rate"] == 50.0
        assert m["profit_factor"] == pytest.approx(20.0 / 7.0, rel=0.01)
        assert m["avg_win"] == 20.0
        assert m["avg_loss"] == -7.0

    def test_breakdowns_by_pattern(self):
        trades = [
            {"pnl_pct": 20.0, "exit_reason": "target", "pattern_type": "Flat Base",
             "confidence_score": 75.0, "market_regime": "confirmed_uptrend",
             "ticker": "A", "detection_date": "2025-06-01",
             "entry_date": "2025-06-05", "entry_price": 100.0,
             "exit_date": "2025-07-01", "exit_price": 120.0},
            {"pnl_pct": -7.0, "exit_reason": "stop", "pattern_type": "Cup & Handle",
             "confidence_score": 55.0, "market_regime": "confirmed_uptrend",
             "ticker": "B", "detection_date": "2025-07-01",
             "entry_date": "2025-07-05", "entry_price": 100.0,
             "exit_date": "2025-07-15", "exit_price": 93.0},
        ]
        m = compute_metrics(trades)
        by_pattern = m["by_pattern"]
        assert "Flat Base" in by_pattern
        assert "Cup & Handle" in by_pattern
        assert by_pattern["Flat Base"]["win_rate"] == 100.0
        assert by_pattern["Cup & Handle"]["win_rate"] == 0.0

    def test_breakdowns_by_confidence(self):
        trades = [
            {"pnl_pct": 20.0, "exit_reason": "target", "pattern_type": "Flat Base",
             "confidence_score": 82.0, "market_regime": "confirmed_uptrend",
             "ticker": "A", "detection_date": "2025-06-01",
             "entry_date": "2025-06-05", "entry_price": 100.0,
             "exit_date": "2025-07-01", "exit_price": 120.0},
            {"pnl_pct": -7.0, "exit_reason": "stop", "pattern_type": "Flat Base",
             "confidence_score": 45.0, "market_regime": "confirmed_uptrend",
             "ticker": "B", "detection_date": "2025-07-01",
             "entry_date": "2025-07-05", "entry_price": 100.0,
             "exit_date": "2025-07-15", "exit_price": 93.0},
        ]
        m = compute_metrics(trades)
        by_conf = m["by_confidence"]
        assert "80-100" in by_conf
        assert "40-60" in by_conf
        assert by_conf["80-100"]["win_rate"] == 100.0
        assert by_conf["40-60"]["win_rate"] == 0.0


class TestBacktestEngine:
    def test_engine_runs_and_returns_trades(self, flat_uptrend_df, spy_uptrend_df):
        """Smoke test: engine runs on synthetic data and returns trade list."""
        config = BacktestConfig(stop_loss_pct=7.0, profit_target_pct=20.0, min_confidence=0.0)
        engine = BacktestEngine(
            ticker_data={"TEST": flat_uptrend_df},
            spy_data=spy_uptrend_df,
            config=config,
        )
        trades = engine.run()
        # We expect a list (possibly empty — synthetic data may or may not trigger)
        assert isinstance(trades, list)
        for t in trades:
            assert "ticker" in t
            assert "pnl_pct" in t
            assert "exit_reason" in t
            assert t["exit_reason"] in ("stop", "target", "open")

    def test_engine_progress_callback(self, flat_uptrend_df, spy_uptrend_df):
        """Verify progress callback is called."""
        config = BacktestConfig(min_confidence=0.0)
        engine = BacktestEngine(
            ticker_data={"TEST": flat_uptrend_df},
            spy_data=spy_uptrend_df,
            config=config,
        )
        calls = []
        engine.run(progress_callback=lambda cur, tot: calls.append((cur, tot)))
        assert len(calls) > 0
        # Last call should have current == total
        assert calls[-1][0] == calls[-1][1]

    def test_deduplication(self, flat_uptrend_df, spy_uptrend_df):
        """Same ticker shouldn't have overlapping open trades."""
        config = BacktestConfig(min_confidence=0.0)
        engine = BacktestEngine(
            ticker_data={"TEST": flat_uptrend_df},
            spy_data=spy_uptrend_df,
            config=config,
        )
        trades = engine.run()
        # Check no two trades on same ticker overlap in time
        for i, t1 in enumerate(trades):
            for t2 in trades[i + 1:]:
                if t1["ticker"] == t2["ticker"]:
                    # t2 entry should be after t1 exit (or t1 is "open")
                    if t1["exit_reason"] != "open":
                        assert t2["entry_date"] >= t1["exit_date"]
```

**Step 2: Run tests to verify they fail**

Run: `cd stock_pattern_scanner && python -m pytest tests/test_backtest.py::TestBacktestConfig::test_defaults -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'backtest'`

**Step 3: Create the backtest engine**

Create `stock_pattern_scanner/backtest.py`:

```python
"""Walk-forward backtest engine for pattern validation.

Replays pattern detection on historical data at weekly intervals,
simulates trades with configurable stop-loss and profit-target,
and computes performance metrics with breakdowns.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Callable, Optional

import pandas as pd

from breakout_rules import BreakoutAnalyzer
from constants import (
    BACKTEST_DEFAULT_MIN_CONFIDENCE,
    BACKTEST_DEFAULT_PROFIT_TARGET_PCT,
    BACKTEST_DEFAULT_STOP_LOSS_PCT,
    BACKTEST_SCAN_INTERVAL_DAYS,
    MIN_DATA_POINTS,
    SCORE_MINIMUM_VIABLE,
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
    ) -> dict:
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
            close = float(row["Close"])

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
```

**Step 4: Run tests**

Run: `cd stock_pattern_scanner && python -m pytest tests/test_backtest.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add stock_pattern_scanner/backtest.py stock_pattern_scanner/tests/test_backtest.py
git commit -m "feat(backtest): add walk-forward backtest engine with metrics"
```

---

## Task 4: Add Backtest API Endpoints

**Files:**
- Modify: `stock_pattern_scanner/app.py`
- Test: `stock_pattern_scanner/tests/test_app.py`

**Step 1: Write failing tests for new endpoints**

Add to `stock_pattern_scanner/tests/test_app.py`:

```python
def test_start_backtest():
    response = client.post("/api/backtest", json={
        "watchlist": "custom",
        "tickers": ["AAPL"],
        "stop_loss_pct": 7.0,
        "profit_target_pct": 20.0,
        "min_confidence": 40.0,
    })
    assert response.status_code == 200
    data = response.json()
    assert "backtest_id" in data


def test_get_backtest_results_not_found():
    response = client.get("/api/backtest/nonexistent/results")
    assert response.status_code == 200
    data = response.json()
    assert data["trades"] == []
```

**Step 2: Run tests to verify they fail**

Run: `cd stock_pattern_scanner && python -m pytest tests/test_app.py::test_start_backtest -v`
Expected: FAIL — 404 or route not found

**Step 3: Add API endpoints to app.py**

Add to `stock_pattern_scanner/app.py`, after existing imports add:

```python
from backtest import BacktestEngine, BacktestConfig, compute_metrics
```

Add the new Pydantic model after `ScanRequest`:

```python
class BacktestRequest(BaseModel):
    watchlist: str = "default"
    tickers: Optional[list[str]] = None
    stop_loss_pct: float = 7.0
    profit_target_pct: float = 20.0
    min_confidence: float = 40.0
```

Add the background runner function after `_run_scan`:

```python
def _run_backtest(bt_id: str, tickers: list[str], config: BacktestConfig):
    """Run backtest in a background thread."""
    import yfinance as yf

    try:
        # Fetch data for all tickers + SPY
        spy = yf.Ticker("SPY")
        spy_data = spy.history(period="2y")
        if spy_data is None or len(spy_data) < MIN_DATA_POINTS:
            db.update_backtest_status(bt_id, "failed: Could not fetch SPY data")
            return

        ticker_data = {}
        total_tickers = len(tickers)
        for i, ticker in enumerate(tickers):
            try:
                t = yf.Ticker(ticker)
                df = t.history(period="2y")
                if df is not None and len(df) >= MIN_DATA_POINTS:
                    ticker_data[ticker] = df
            except Exception as e:
                logger.warning("Failed to fetch %s for backtest: %s", ticker, e)

        if not ticker_data:
            db.update_backtest_status(bt_id, "failed: No valid ticker data")
            return

        engine = BacktestEngine(
            ticker_data=ticker_data,
            spy_data=spy_data,
            config=config,
        )

        def progress_cb(current: int, total: int):
            db.update_backtest_progress(bt_id, current, total)

        trades = engine.run(progress_callback=progress_cb)
        metrics = compute_metrics(trades)

        db.save_backtest_trades(bt_id, trades)
        db.save_backtest_summary(
            bt_id,
            total_trades=metrics["total_trades"],
            win_rate=metrics["win_rate"],
            profit_factor=metrics["profit_factor"] if metrics["profit_factor"] != float("inf") else 999.0,
        )
        db.update_backtest_status(bt_id, "completed")
    except Exception as e:
        logger.error("Backtest %s failed: %s", bt_id, e, exc_info=True)
        db.update_backtest_status(bt_id, f"failed: {e}")
```

Add the three new endpoints after the existing Excel export endpoint:

```python
@app.post("/api/backtest")
async def start_backtest(request: BacktestRequest):
    tickers = resolve_watchlist(request.watchlist, request.tickers)
    config = BacktestConfig(
        stop_loss_pct=request.stop_loss_pct,
        profit_target_pct=request.profit_target_pct,
        min_confidence=request.min_confidence,
    )
    bt_id = db.create_backtest(
        watchlist=request.watchlist,
        tickers=tickers,
        stop_loss_pct=config.stop_loss_pct,
        profit_target_pct=config.profit_target_pct,
        min_confidence=config.min_confidence,
    )

    thread = threading.Thread(
        target=_run_backtest,
        args=(bt_id, tickers, config),
        daemon=True,
    )
    thread.start()

    return {"backtest_id": bt_id, "total_tickers": len(tickers)}


@app.get("/api/backtest/{bt_id}/progress")
async def backtest_progress(bt_id: str):
    """SSE endpoint streaming backtest progress."""
    async def event_generator():
        while True:
            progress = db.get_backtest_progress(bt_id)
            data = json.dumps(progress)
            yield f"data: {data}\n\n"

            status = progress["status"]
            if status in ("completed", "not_found") or status.startswith("failed"):
                break
            await asyncio.sleep(SSE_POLL_INTERVAL)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


@app.get("/api/backtest/{bt_id}/results")
async def get_backtest_results(bt_id: str):
    trades = db.get_backtest_trades(bt_id)
    summary = db.get_backtest_summary(bt_id)
    metrics = compute_metrics(trades) if trades else {
        "total_trades": 0, "win_rate": 0.0, "avg_return": 0.0,
        "profit_factor": 0.0, "avg_win": 0.0, "avg_loss": 0.0,
        "expectancy": 0.0, "by_pattern": {}, "by_confidence": {},
        "by_regime": {},
    }
    return {
        "backtest_id": bt_id,
        "summary": summary,
        "metrics": metrics,
        "trades": trades,
    }
```

Also add `MIN_DATA_POINTS` to the constants import at the top of `app.py`:

```python
from constants import DEFAULT_MAX_WORKERS, MIN_DATA_POINTS, SSE_POLL_INTERVAL
```

**Step 4: Run tests**

Run: `cd stock_pattern_scanner && python -m pytest tests/test_app.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add stock_pattern_scanner/app.py stock_pattern_scanner/tests/test_app.py
git commit -m "feat(backtest): add backtest API endpoints"
```

---

## Task 5: Add Backtest Dashboard Tab

**Files:**
- Modify: `stock_pattern_scanner/templates/dashboard.html`

**Step 1: Add tab navigation to the header**

Replace the existing header `<div>`:

```html
    <div class="header">
        <h1><span>&#9632;</span> Stock Pattern Scanner</h1>
        <div class="header-tabs">
            <button class="tab-btn active" onclick="switchTab('scanner')">Scanner</button>
            <button class="tab-btn" onclick="switchTab('backtest')">Backtest</button>
        </div>
        <div class="header-right">CAN SLIM Base Pattern Detection</div>
    </div>
```

**Step 2: Add tab CSS**

Add to the `<style>` section:

```css
        /* Tabs */
        .header-tabs { display: flex; gap: 4px; }
        .tab-btn {
            background: transparent;
            border: 1px solid transparent;
            color: var(--text-secondary);
            padding: 6px 16px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 14px;
            font-weight: 600;
            font-family: inherit;
        }
        .tab-btn:hover { color: var(--text-primary); }
        .tab-btn.active {
            background: var(--bg-tertiary);
            border-color: var(--border);
            color: var(--text-primary);
        }
        .tab-content { display: none; }
        .tab-content.active { display: block; }

        /* Backtest specific */
        .metrics-grid {
            display: grid;
            grid-template-columns: repeat(5, 1fr);
            gap: 12px;
            margin-bottom: 16px;
        }
        .breakdown-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 16px;
            margin-bottom: 16px;
        }
        .breakdown-card {
            background: var(--bg-secondary);
            border: 1px solid var(--border);
            border-radius: 6px;
            padding: 16px;
        }
        .breakdown-card h3 {
            font-size: 13px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            color: var(--text-secondary);
            margin-bottom: 12px;
        }
        .breakdown-table { width: 100%; font-size: 13px; }
        .breakdown-table th {
            text-align: left;
            padding: 6px 8px;
            color: var(--text-secondary);
            font-weight: 600;
            border-bottom: 1px solid var(--border);
        }
        .breakdown-table td {
            padding: 6px 8px;
            border-bottom: 1px solid var(--border);
        }
        .pnl-positive { color: var(--success); }
        .pnl-negative { color: var(--danger); }
        .pnl-open { color: var(--warning); }

        @media (max-width: 768px) {
            .metrics-grid { grid-template-columns: repeat(2, 1fr); }
            .breakdown-grid { grid-template-columns: 1fr; }
        }
```

**Step 3: Wrap existing scanner content in a tab div**

Wrap everything inside `.container` (from market banner through empty state) in:

```html
    <div class="container">
        <!-- Scanner Tab -->
        <div id="scanner-tab" class="tab-content active">
            <!-- ... all existing scanner content stays here ... -->
        </div>

        <!-- Backtest Tab -->
        <div id="backtest-tab" class="tab-content">
            <!-- Backtest controls -->
            <div class="controls">
                <div class="control-group">
                    <label>Watchlist</label>
                    <select id="bt-watchlist">
                        <option value="default">Growth Watchlist</option>
                        <option value="sp500">S&P 500</option>
                        <option value="nasdaq100">NASDAQ 100</option>
                        <option value="custom">Custom Tickers</option>
                    </select>
                </div>
                <div class="control-group" id="bt-custom-group" style="display:none;">
                    <label>Tickers</label>
                    <textarea id="bt-custom-tickers" placeholder="AAPL, MSFT, NVDA..."></textarea>
                </div>
                <div class="control-group">
                    <label>Stop Loss %</label>
                    <input type="text" id="bt-stop-loss" value="7" style="width:60px;">
                </div>
                <div class="control-group">
                    <label>Profit Target %</label>
                    <input type="text" id="bt-profit-target" value="20" style="width:60px;">
                </div>
                <div class="control-group">
                    <label>Min Confidence</label>
                    <input type="text" id="bt-min-conf" value="40" style="width:60px;">
                </div>
                <div class="control-group">
                    <label>&nbsp;</label>
                    <button class="btn btn-primary" id="bt-run-btn" onclick="startBacktest()">Run Backtest</button>
                </div>
            </div>

            <!-- Backtest progress -->
            <div class="progress-section" id="bt-progress">
                <div class="progress-header">
                    <span class="progress-label">Running backtest...</span>
                    <span class="progress-count" id="bt-progress-count">0 / 0</span>
                </div>
                <div class="progress-bar-bg">
                    <div class="progress-bar-fill" id="bt-progress-bar"></div>
                </div>
                <div class="progress-ticker" id="bt-progress-status">Preparing...</div>
            </div>

            <!-- Backtest summary metrics -->
            <div class="metrics-grid" id="bt-metrics" style="display:none;">
                <div class="stat-card">
                    <div class="stat-value" id="bt-total-trades" style="color:var(--accent);">0</div>
                    <div class="stat-label">Total Trades</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value" id="bt-win-rate" style="color:var(--success);">0%</div>
                    <div class="stat-label">Win Rate</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value" id="bt-profit-factor-val" style="color:var(--accent);">0</div>
                    <div class="stat-label">Profit Factor</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value" id="bt-avg-return" style="color:var(--success);">0%</div>
                    <div class="stat-label">Avg Return</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value" id="bt-expectancy" style="color:var(--accent);">0%</div>
                    <div class="stat-label">Expectancy</div>
                </div>
            </div>

            <!-- Breakdowns -->
            <div class="breakdown-grid" id="bt-breakdowns" style="display:none;">
                <div class="breakdown-card">
                    <h3>By Pattern Type</h3>
                    <table class="breakdown-table" id="bt-by-pattern"><thead><tr><th>Pattern</th><th>Trades</th><th>Win Rate</th><th>Avg Return</th></tr></thead><tbody></tbody></table>
                </div>
                <div class="breakdown-card">
                    <h3>By Confidence Band</h3>
                    <table class="breakdown-table" id="bt-by-confidence"><thead><tr><th>Band</th><th>Trades</th><th>Win Rate</th><th>Avg Return</th></tr></thead><tbody></tbody></table>
                </div>
                <div class="breakdown-card">
                    <h3>By Market Regime</h3>
                    <table class="breakdown-table" id="bt-by-regime"><thead><tr><th>Regime</th><th>Trades</th><th>Win Rate</th><th>Avg Return</th></tr></thead><tbody></tbody></table>
                </div>
                <div class="breakdown-card">
                    <h3>Win/Loss Summary</h3>
                    <table class="breakdown-table" id="bt-winloss"><thead><tr><th>Metric</th><th>Value</th></tr></thead><tbody></tbody></table>
                </div>
            </div>

            <!-- Trade log -->
            <div class="table-wrapper" id="bt-trades-table" style="display:none;">
                <table>
                    <thead><tr>
                        <th>Ticker</th><th>Pattern</th><th>Score</th><th>Detected</th>
                        <th>Entry</th><th>Entry $</th><th>Exit</th><th>Exit $</th>
                        <th>Reason</th><th>P&L %</th><th>Regime</th>
                    </tr></thead>
                    <tbody id="bt-trades-body"></tbody>
                </table>
            </div>

            <!-- Empty state -->
            <div class="empty-state" id="bt-empty">
                <h3>No backtest results yet</h3>
                <p>Configure parameters and click Run Backtest to validate patterns.</p>
            </div>
        </div>
    </div>
```

**Step 4: Add backtest JavaScript**

Add to the `<script>` section, after the existing `fetchMarketStatus();` call:

```javascript
        // --- Tab switching ---
        function switchTab(tab) {
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            document.getElementById(tab + '-tab').classList.add('active');
            event.target.classList.add('active');
        }

        // --- Backtest ---
        document.getElementById('bt-watchlist').addEventListener('change', function() {
            document.getElementById('bt-custom-group').style.display =
                this.value === 'custom' ? '' : 'none';
        });

        async function startBacktest() {
            var btn = document.getElementById('bt-run-btn');
            btn.disabled = true;
            btn.textContent = 'Running...';

            var watchlist = document.getElementById('bt-watchlist').value;
            var body = {
                watchlist: watchlist,
                stop_loss_pct: parseFloat(document.getElementById('bt-stop-loss').value) || 7,
                profit_target_pct: parseFloat(document.getElementById('bt-profit-target').value) || 20,
                min_confidence: parseFloat(document.getElementById('bt-min-conf').value) || 40,
            };
            if (watchlist === 'custom') {
                var raw = document.getElementById('bt-custom-tickers').value;
                body.tickers = raw.split(/[,\s]+/).map(function(t) { return t.trim().toUpperCase(); }).filter(Boolean);
                if (body.tickers.length === 0) { btn.disabled = false; btn.textContent = 'Run Backtest'; return; }
            }

            document.getElementById('bt-progress').classList.add('visible');
            document.getElementById('bt-metrics').style.display = 'none';
            document.getElementById('bt-breakdowns').style.display = 'none';
            document.getElementById('bt-trades-table').style.display = 'none';
            document.getElementById('bt-empty').style.display = 'none';
            document.getElementById('bt-progress-bar').style.width = '0%';

            try {
                var resp = await fetch('/api/backtest', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(body),
                });
                var data = await resp.json();
                listenBacktestProgress(data.backtest_id);
            } catch (err) {
                btn.disabled = false;
                btn.textContent = 'Run Backtest';
                document.getElementById('bt-progress').classList.remove('visible');
                alert('Failed to start backtest: ' + err.message);
            }
        }

        function listenBacktestProgress(btId) {
            var evtSource = new EventSource('/api/backtest/' + btId + '/progress');

            evtSource.onmessage = function(event) {
                var data = JSON.parse(event.data);
                var current = data.current || 0;
                var total = data.total || 1;
                var pct = Math.round((current / total) * 100);

                document.getElementById('bt-progress-bar').style.width = pct + '%';
                document.getElementById('bt-progress-count').textContent = current + ' / ' + total;
                document.getElementById('bt-progress-status').textContent = 'Analyzing historical patterns... ' + pct + '%';

                if (data.status === 'completed') {
                    evtSource.close();
                    document.getElementById('bt-progress-status').textContent = 'Backtest complete!';
                    loadBacktestResults(btId);
                } else if (data.status && data.status.startsWith('failed')) {
                    evtSource.close();
                    document.getElementById('bt-progress-status').textContent = 'Backtest failed.';
                    document.getElementById('bt-run-btn').disabled = false;
                    document.getElementById('bt-run-btn').textContent = 'Run Backtest';
                }
            };

            evtSource.onerror = function() {
                evtSource.close();
                document.getElementById('bt-run-btn').disabled = false;
                document.getElementById('bt-run-btn').textContent = 'Run Backtest';
            };
        }

        async function loadBacktestResults(btId) {
            try {
                var resp = await fetch('/api/backtest/' + btId + '/results');
                var data = await resp.json();
                var m = data.metrics;
                var trades = data.trades || [];

                // Summary metrics
                document.getElementById('bt-total-trades').textContent = m.total_trades;
                document.getElementById('bt-win-rate').textContent = m.win_rate + '%';
                document.getElementById('bt-win-rate').style.color = m.win_rate >= 50 ? 'var(--success)' : 'var(--danger)';
                document.getElementById('bt-profit-factor-val').textContent = m.profit_factor === Infinity ? '∞' : m.profit_factor.toFixed(2);
                document.getElementById('bt-avg-return').textContent = (m.avg_return >= 0 ? '+' : '') + m.avg_return + '%';
                document.getElementById('bt-avg-return').style.color = m.avg_return >= 0 ? 'var(--success)' : 'var(--danger)';
                document.getElementById('bt-expectancy').textContent = (m.expectancy >= 0 ? '+' : '') + m.expectancy + '%';

                // Breakdowns
                renderBreakdown('bt-by-pattern', m.by_pattern);
                renderBreakdown('bt-by-confidence', m.by_confidence);
                renderBreakdown('bt-by-regime', m.by_regime);

                // Win/loss summary
                var wl = document.querySelector('#bt-winloss tbody');
                wl.innerHTML =
                    '<tr><td>Avg Win</td><td class="pnl-positive">+' + m.avg_win + '%</td></tr>' +
                    '<tr><td>Avg Loss</td><td class="pnl-negative">' + m.avg_loss + '%</td></tr>' +
                    '<tr><td>Profit Factor</td><td>' + (m.profit_factor === Infinity ? '∞' : m.profit_factor.toFixed(2)) + '</td></tr>';

                // Trade log
                var tbody = document.getElementById('bt-trades-body');
                tbody.innerHTML = trades.map(function(t) {
                    var pnlClass = t.exit_reason === 'open' ? 'pnl-open' : (t.pnl_pct >= 0 ? 'pnl-positive' : 'pnl-negative');
                    var reasonBadge = t.exit_reason === 'target' ? '<span class="status-badge status-breakout-confirmed">Target</span>' :
                                      t.exit_reason === 'stop' ? '<span class="status-badge status-at-pivot">Stop</span>' :
                                      '<span class="status-badge status-building">Open</span>';
                    return '<tr>' +
                        '<td><strong>' + esc(t.ticker) + '</strong></td>' +
                        '<td>' + patternBadge(t.pattern_type) + '</td>' +
                        '<td>' + Math.round(t.confidence_score) + '</td>' +
                        '<td>' + t.detection_date + '</td>' +
                        '<td>' + (t.entry_date || '-') + '</td>' +
                        '<td>$' + (t.entry_price ? t.entry_price.toFixed(2) : '-') + '</td>' +
                        '<td>' + (t.exit_date || '-') + '</td>' +
                        '<td>$' + (t.exit_price ? t.exit_price.toFixed(2) : '-') + '</td>' +
                        '<td>' + reasonBadge + '</td>' +
                        '<td class="' + pnlClass + '">' + (t.pnl_pct >= 0 ? '+' : '') + t.pnl_pct + '%</td>' +
                        '<td>' + formatRegime(t.market_regime) + '</td>' +
                        '</tr>';
                }).join('');

                // Show sections
                document.getElementById('bt-metrics').style.display = '';
                document.getElementById('bt-breakdowns').style.display = '';
                document.getElementById('bt-trades-table').style.display = trades.length > 0 ? '' : 'none';
                document.getElementById('bt-empty').style.display = trades.length === 0 ? '' : 'none';

                setTimeout(function() {
                    document.getElementById('bt-progress').classList.remove('visible');
                }, 1500);
            } catch (err) {
                alert('Failed to load backtest results: ' + err.message);
            }

            document.getElementById('bt-run-btn').disabled = false;
            document.getElementById('bt-run-btn').textContent = 'Run Backtest';
        }

        function renderBreakdown(tableId, data) {
            var tbody = document.querySelector('#' + tableId + ' tbody');
            if (!data || Object.keys(data).length === 0) {
                tbody.innerHTML = '<tr><td colspan="4" style="color:var(--text-muted);">No data</td></tr>';
                return;
            }
            tbody.innerHTML = Object.entries(data).map(function(entry) {
                var name = entry[0];
                var d = entry[1];
                var retClass = d.avg_return >= 0 ? 'pnl-positive' : 'pnl-negative';
                return '<tr><td>' + esc(name) + '</td><td>' + d.total + '</td><td>' + d.win_rate + '%</td><td class="' + retClass + '">' + (d.avg_return >= 0 ? '+' : '') + d.avg_return + '%</td></tr>';
            }).join('');
        }

        function formatRegime(r) {
            if (r === 'confirmed_uptrend') return '<span style="color:var(--success);">Uptrend</span>';
            if (r === 'uptrend_under_pressure') return '<span style="color:var(--warning);">Pressure</span>';
            return '<span style="color:var(--text-muted);">' + esc(r || 'unknown') + '</span>';
        }
```

**Step 5: Manually verify (no automated test for HTML)**

Run: `cd stock_pattern_scanner && python -c "from app import app; print('OK')"`
Expected: `OK`

**Step 6: Commit**

```bash
git add stock_pattern_scanner/templates/dashboard.html
git commit -m "feat(backtest): add backtest tab to dashboard with metrics and trade log"
```

---

## Task 6: Run Full Test Suite

**Step 1: Run all tests**

Run: `cd stock_pattern_scanner && python -m pytest tests/ -v`
Expected: All PASS (existing 67 + new backtest + new DB tests)

**Step 2: Verify app starts cleanly**

Run from repo root:
```bash
cd stock_pattern_scanner && python -c "from app import app; print('Routes:', [r.path for r in app.routes])"
```
Expected: Should list all routes including `/api/backtest`, `/api/backtest/{bt_id}/progress`, `/api/backtest/{bt_id}/results`.

**Step 3: Commit if any test fixes were needed**

If any fixes were required, commit them:
```bash
git add -A
git commit -m "fix(backtest): resolve test issues from integration"
```

---

## Verification Checklist

After all tasks:

- [ ] `python -m pytest tests/ -v` — all tests pass
- [ ] App imports cleanly: `python -c "from app import app"`
- [ ] Backtest engine imports cleanly: `python -c "from backtest import BacktestEngine, compute_metrics"`
- [ ] DB creates backtest tables: `python -c "from database import ScanDatabase; db = ScanDatabase(':memory:'); print('OK')"`
- [ ] Dashboard loads at `http://localhost:8000/` with Scanner and Backtest tabs

Files created:
- `stock_pattern_scanner/backtest.py`
- `stock_pattern_scanner/tests/test_backtest.py`

Files modified:
- `stock_pattern_scanner/constants.py` (5 new constants)
- `stock_pattern_scanner/database.py` (2 new tables, 7 new methods)
- `stock_pattern_scanner/app.py` (3 new endpoints, 1 new Pydantic model, 1 background runner)
- `stock_pattern_scanner/templates/dashboard.html` (tab navigation, backtest UI)
- `stock_pattern_scanner/tests/test_database.py` (3 new tests)
- `stock_pattern_scanner/tests/test_app.py` (2 new tests)
