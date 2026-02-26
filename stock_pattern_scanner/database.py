"""SQLite database for caching scan results."""

from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime
from typing import Optional

from pattern_scanner import PatternResult


class ScanDatabase:
    """SQLite-backed storage for scan state and results."""

    def __init__(self, db_path: str = "scanner.db"):
        self.db_path = db_path
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
                    FOREIGN KEY (scan_id) REFERENCES scans(scan_id)
                );
            """)

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
                        volume_confirmation, above_50ma, above_200ma, rs_rating, pattern_details)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        scan_id, r.ticker, r.pattern_type, r.confidence_score,
                        r.buy_point, r.current_price, r.distance_to_pivot,
                        r.base_depth, r.base_length_weeks,
                        int(r.volume_confirmation), int(r.above_50ma),
                        int(r.above_200ma), r.rs_rating,
                        json.dumps(r.pattern_details),
                    ),
                )

    def get_results(self, scan_id: str) -> list[PatternResult]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM results WHERE scan_id=? ORDER BY confidence_score DESC",
                (scan_id,),
            ).fetchall()

        return [
            PatternResult(
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
            )
            for row in rows
        ]
