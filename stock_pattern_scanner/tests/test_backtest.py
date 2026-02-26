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
