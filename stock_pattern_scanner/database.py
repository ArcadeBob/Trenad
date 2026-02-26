"""SQLite database for caching scan results."""

from __future__ import annotations

import json
import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime
from typing import Optional

import numpy as np

from pattern_scanner import PatternResult


class _NumpyEncoder(json.JSONEncoder):
    """Handle numpy types when serializing pattern details to JSON."""

    def default(self, obj):
        if isinstance(obj, (np.bool_,)):
            return bool(obj)
        if isinstance(obj, (np.integer,)):
            return int(obj)
        if isinstance(obj, (np.floating,)):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return super().default(obj)


class ScanDatabase:
    """SQLite-backed storage for scan state and results."""

    def __init__(self, db_path: str = "scanner.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        self._init_db()

    @contextmanager
    def _connect(self):
        """Yield a connection that auto-commits/rollbacks and always closes."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def _init_db(self):
        with self._connect() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS scans (
                    scan_id TEXT PRIMARY KEY,
                    watchlist TEXT,
                    tickers TEXT,
                    status TEXT DEFAULT 'pending',
                    created_at TEXT,
                    completed_at TEXT,
                    progress_current INTEGER DEFAULT 0,
                    progress_total INTEGER DEFAULT 0,
                    progress_ticker TEXT DEFAULT ''
                );
                CREATE TABLE IF NOT EXISTS results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    scan_id TEXT,
                    ticker TEXT,
                    pattern_type TEXT,
                    confidence_score REAL,
                    buy_point REAL,
                    current_price REAL,
                    distance_to_pivot REAL,
                    base_depth REAL,
                    base_length_weeks INTEGER,
                    volume_confirmation INTEGER,
                    above_50ma INTEGER,
                    above_200ma INTEGER,
                    rs_rating REAL,
                    pattern_details TEXT,
                    stop_loss_price REAL DEFAULT 0,
                    profit_target_price REAL DEFAULT 0,
                    breakout_confirmed INTEGER DEFAULT NULL,
                    volume_surge_pct REAL DEFAULT NULL,
                    volume_rating TEXT DEFAULT 'C',
                    trend_score REAL DEFAULT 0,
                    FOREIGN KEY (scan_id) REFERENCES scans(scan_id)
                );
            """)
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
            # Migrate: add columns that may be missing from older schemas
            migrations = [
                ("results", "stop_loss_price", "REAL DEFAULT 0"),
                ("results", "profit_target_price", "REAL DEFAULT 0"),
                ("results", "breakout_confirmed", "INTEGER DEFAULT NULL"),
                ("results", "volume_surge_pct", "REAL DEFAULT NULL"),
                ("results", "volume_rating", "TEXT DEFAULT 'C'"),
                ("results", "trend_score", "REAL DEFAULT 0"),
            ]
            for table, col, col_type in migrations:
                try:
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}")
                except sqlite3.OperationalError:
                    pass  # Column already exists

    def create_scan(self, watchlist: str, tickers: list[str]) -> str:
        scan_id = str(uuid.uuid4())[:8]
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO scans (scan_id, watchlist, tickers, status, created_at, progress_total) VALUES (?, ?, ?, ?, ?, ?)",
                (scan_id, watchlist, json.dumps(tickers), "running", datetime.now().isoformat(), len(tickers)),
            )
        return scan_id

    def update_progress(self, scan_id: str, current: int, total: int, ticker: str):
        with self._connect() as conn:
            conn.execute(
                "UPDATE scans SET progress_current=?, progress_total=?, progress_ticker=? WHERE scan_id=?",
                (current, total, ticker, scan_id),
            )

    def get_progress(self, scan_id: str) -> dict:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM scans WHERE scan_id=?", (scan_id,)).fetchone()
        if row is None:
            return {"current": 0, "total": 0, "ticker": "", "status": "not_found"}
        return {
            "current": row["progress_current"],
            "total": row["progress_total"],
            "ticker": row["progress_ticker"],
            "status": row["status"],
        }

    def update_status(self, scan_id: str, status: str):
        completed_at = datetime.now().isoformat() if status == "completed" else None
        with self._connect() as conn:
            conn.execute(
                "UPDATE scans SET status=?, completed_at=? WHERE scan_id=?",
                (status, completed_at, scan_id),
            )

    def get_scan_status(self, scan_id: str) -> Optional[str]:
        with self._connect() as conn:
            row = conn.execute("SELECT status FROM scans WHERE scan_id=?", (scan_id,)).fetchone()
        return row["status"] if row else None

    def save_results(self, scan_id: str, results: list[PatternResult]):
        with self._connect() as conn:
            for r in results:
                conn.execute(
                    """INSERT INTO results
                       (scan_id, ticker, pattern_type, confidence_score, buy_point,
                        current_price, distance_to_pivot, base_depth, base_length_weeks,
                        volume_confirmation, above_50ma, above_200ma, rs_rating, pattern_details,
                        stop_loss_price, profit_target_price, breakout_confirmed, volume_surge_pct,
                        volume_rating, trend_score)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        scan_id, r.ticker, r.pattern_type, r.confidence_score,
                        r.buy_point, r.current_price, r.distance_to_pivot,
                        r.base_depth, r.base_length_weeks,
                        int(r.volume_confirmation), int(r.above_50ma),
                        int(r.above_200ma), r.rs_rating,
                        json.dumps(r.pattern_details, cls=_NumpyEncoder),
                        r.stop_loss_price, r.profit_target_price,
                        None if r.breakout_confirmed is None else int(r.breakout_confirmed),
                        r.volume_surge_pct, r.volume_rating, r.trend_score,
                    ),
                )

    def get_results(self, scan_id: str) -> list[PatternResult]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM results WHERE scan_id=? ORDER BY confidence_score DESC",
                (scan_id,),
            ).fetchall()

        results = []
        for row in rows:
            bc_raw = row["breakout_confirmed"]
            bc = None if bc_raw is None else bool(bc_raw)
            results.append(PatternResult(
                ticker=row["ticker"],
                pattern_type=row["pattern_type"],
                confidence_score=row["confidence_score"],
                buy_point=row["buy_point"],
                current_price=row["current_price"],
                distance_to_pivot=row["distance_to_pivot"],
                base_depth=row["base_depth"],
                base_length_weeks=row["base_length_weeks"],
                volume_confirmation=bool(row["volume_confirmation"]),
                above_50ma=bool(row["above_50ma"]),
                above_200ma=bool(row["above_200ma"]),
                rs_rating=row["rs_rating"],
                pattern_details=json.loads(row["pattern_details"]),
                stop_loss_price=row["stop_loss_price"] or 0.0,
                profit_target_price=row["profit_target_price"] or 0.0,
                breakout_confirmed=bc,
                volume_surge_pct=row["volume_surge_pct"],
                volume_rating=row["volume_rating"] or "C",
                trend_score=row["trend_score"] or 0.0,
            ))
        return results

    # ------------------------------------------------------------------
    # Backtest methods
    # ------------------------------------------------------------------

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
