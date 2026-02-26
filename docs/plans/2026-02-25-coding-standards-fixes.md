# Coding Standards Fixes Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix all coding standards violations found in the audit — critical DB connection leak, magic numbers, DRY violations, inconsistent types, error handling gaps, and test fragility.

**Architecture:** No structural changes. Extract constants to a new module, refactor DB class to use context managers, create shared test fixtures in conftest.py, and unify duplicated ticker resolution logic.

**Tech Stack:** Python 3.11+, sqlite3, pytest, FastAPI

---

## Task 1: Create Named Constants Module

Eliminates ~30 magic numbers scattered across `pattern_scanner.py`.

**Files:**
- Create: `stock_pattern_scanner/constants.py`

**Step 1: Create constants.py**

```python
"""Named constants for stock pattern detection.

All thresholds and configuration values used by the scanner.
"""

# ---------------------------------------------------------------------------
# Trading calendar
# ---------------------------------------------------------------------------
TRADING_DAYS_PER_WEEK = 5
TRADING_DAYS_PER_QUARTER = 63
TRADING_DAYS_PER_HALF_YEAR = 126
TRADING_DAYS_PER_9_MONTHS = 189
TRADING_DAYS_PER_YEAR = 252

# ---------------------------------------------------------------------------
# Data requirements
# ---------------------------------------------------------------------------
MIN_DATA_POINTS = 200

# ---------------------------------------------------------------------------
# Relative strength
# ---------------------------------------------------------------------------
RS_PERIODS = (63, 126, 189, 252)
RS_WEIGHTS = (0.4, 0.2, 0.2, 0.2)
RS_BASELINE = 50
RS_MIN = 1
RS_MAX = 99

# ---------------------------------------------------------------------------
# Prior uptrend
# ---------------------------------------------------------------------------
PRIOR_UPTREND_LOOKBACK_DAYS = 126
PRIOR_UPTREND_MIN_GAIN_PCT = 30.0
PRIOR_UPTREND_MIN_SEGMENT_LEN = 20

# ---------------------------------------------------------------------------
# Flat base
# ---------------------------------------------------------------------------
FLAT_BASE_MAX_DEPTH_PCT = 15.0
FLAT_BASE_SEED_DAYS = 25
FLAT_BASE_MAX_WINDOW_DAYS = 75
FLAT_BASE_SEED_FLOOR_FACTOR = 0.5
FLAT_BASE_MA50_THRESHOLD = 0.50
FLAT_BASE_VOLUME_CONTRACTION = 0.90
FLAT_BASE_PRIOR_VOLUME_DAYS = 50

# ---------------------------------------------------------------------------
# Double bottom
# ---------------------------------------------------------------------------
DOUBLE_BOTTOM_LOOKBACK_DAYS = 190
DOUBLE_BOTTOM_LOOKBACK_BUFFER = 50
DOUBLE_BOTTOM_MIN_AFTER_HIGH = 40
DOUBLE_BOTTOM_TROUGH_WINDOW = 8
DOUBLE_BOTTOM_LOW_DIFF_MAX_PCT = 5.0
DOUBLE_BOTTOM_MIN_SEPARATION_DAYS = 15
DOUBLE_BOTTOM_MIN_DEPTH_PCT = 15.0
DOUBLE_BOTTOM_MAX_DEPTH_PCT = 40.0
DOUBLE_BOTTOM_VOLUME_WINDOW = 5

# ---------------------------------------------------------------------------
# Cup & handle
# ---------------------------------------------------------------------------
CUP_MAX_LOOKBACK_DAYS = 325
CUP_LOOKBACK_BUFFER = 50
CUP_PEAK_WINDOW = 15
CUP_MIN_AFTER_LIP = 35
CUP_MIN_DEPTH_PCT = 12.0
CUP_MAX_DEPTH_PCT = 50.0
CUP_DEEP_THRESHOLD_PCT = 33.0
CUP_MIN_AFTER_LOW = 15
CUP_MIN_RECOVERY_PCT = 70.0
CUP_MIN_HANDLE_DAYS = 5
HANDLE_MAX_LENGTH_WEEKS = 6
HANDLE_MAX_DECLINE_PCT = 15.0
CUP_MIN_TOTAL_WEEKS = 7
CUP_MAX_TOTAL_WEEKS = 65
CUP_HANDLE_VOLUME_FACTOR = 0.85

# ---------------------------------------------------------------------------
# Status thresholds (distance to pivot)
# ---------------------------------------------------------------------------
STATUS_EXTENDED_THRESHOLD = 5.0
STATUS_AT_PIVOT_THRESHOLD = 1.0
STATUS_NEAR_PIVOT_LOWER = -5.0

# ---------------------------------------------------------------------------
# Confidence scoring weights
# ---------------------------------------------------------------------------
SCORE_DEPTH_MAX = 20.0
SCORE_VOLUME_MAX = 15.0
SCORE_ABOVE_50MA_MAX = 15.0
SCORE_ABOVE_200MA_MAX = 10.0
SCORE_TIGHTNESS_MAX = 15.0
SCORE_BASE_LENGTH_MAX = 10.0

# Flat base depth scoring
FLAT_BASE_IDEAL_DEPTH_LOW = 5.0
FLAT_BASE_IDEAL_DEPTH_HIGH = 12.0
FLAT_BASE_DEPTH_PENALTY = 2.0

# Double bottom depth scoring
DOUBLE_BOTTOM_IDEAL_DEPTH_LOW = 20.0
DOUBLE_BOTTOM_IDEAL_DEPTH_HIGH = 30.0
DOUBLE_BOTTOM_DEPTH_CENTER = 25.0
DOUBLE_BOTTOM_DEPTH_PENALTY = 1.5

# Cup depth scoring
CUP_IDEAL_DEPTH_CENTER = 20.0
CUP_DEEP_IDEAL_DEPTH_CENTER = 37.0
CUP_DEPTH_PENALTY = 1.0

# Tightness thresholds
TIGHTNESS_TIGHT = 8.0
TIGHTNESS_MODERATE = 12.0
TIGHTNESS_LOOSE = 18.0
TIGHTNESS_LOOKBACK = 25

# Base length ideal ranges (weeks)
FLAT_BASE_IDEAL_WEEKS = (6, 12)
DOUBLE_BOTTOM_IDEAL_WEEKS = (7, 20)
CUP_IDEAL_WEEKS = (8, 30)
BASE_LENGTH_OVER_PENALTY = 0.5

# Pattern-specific bonus thresholds
DOUBLE_BOTTOM_TIGHT_LOW_DIFF = 3.0
DOUBLE_BOTTOM_MODERATE_LOW_DIFF = 5.0
CUP_HIGH_RECOVERY_PCT = 90.0
CUP_MODERATE_RECOVERY_PCT = 80.0
CUP_TIGHT_HANDLE_DEPTH_PCT = 8.0
FLAT_BASE_TIGHT_DEPTH_PCT = 10.0

# ---------------------------------------------------------------------------
# Scanner defaults
# ---------------------------------------------------------------------------
DEFAULT_MAX_WORKERS = 5
DEFAULT_HISTORY_PERIOD = "2y"
SSE_POLL_INTERVAL = 0.5
PROGRESS_BAR_LENGTH = 30
DEFAULT_TOP_RESULTS = 50
NEAR_PIVOT_THRESHOLD = 5.0
```

**Step 2: Verify file is importable**

Run: `cd stock_pattern_scanner && python -c "from constants import *; print('OK')"`
Expected: `OK`

**Step 3: Commit**

```bash
git add stock_pattern_scanner/constants.py
git commit -m "refactor: add named constants module for all magic numbers"
```

---

## Task 2: Fix Database Connection Leak (CRITICAL)

Every method in `ScanDatabase` leaks connections on exception. Replace manual open/close with a context manager.

**Files:**
- Modify: `stock_pattern_scanner/database.py`

**Step 1: Run existing tests as baseline**

Run: `cd stock_pattern_scanner && python -m pytest tests/test_database.py -v`
Expected: All PASS

**Step 2: Add `_connect` context manager and rewrite all methods**

Replace the entire `database.py` with:

```python
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
```

**Step 3: Run tests**

Run: `cd stock_pattern_scanner && python -m pytest tests/test_database.py -v`
Expected: All PASS

**Step 4: Commit**

```bash
git add stock_pattern_scanner/database.py
git commit -m "fix: use context manager for DB connections to prevent leaks"
```

---

## Task 3: Create Shared Test Fixtures

Add `conftest.py` with factory fixtures for `PatternResult`, price DataFrames, and temp databases.

**Files:**
- Create: `stock_pattern_scanner/tests/conftest.py`

**Step 1: Create conftest.py**

```python
"""Shared test fixtures for stock_pattern_scanner tests."""

from __future__ import annotations

from typing import Any

import pandas as pd
import pytest

from database import ScanDatabase
from pattern_scanner import PatternResult

_PATTERN_RESULT_DEFAULTS = dict(
    ticker="AAPL",
    pattern_type="Flat Base",
    confidence_score=75.0,
    buy_point=150.0,
    current_price=148.0,
    distance_to_pivot=-1.33,
    base_depth=10.0,
    base_length_weeks=7,
    volume_confirmation=True,
    above_50ma=True,
    above_200ma=True,
    rs_rating=85.0,
    pattern_details={},
)


@pytest.fixture
def make_pattern_result():
    """Factory: builds PatternResult with sensible defaults, override any field."""
    def _factory(**overrides: Any) -> PatternResult:
        kwargs = {**_PATTERN_RESULT_DEFAULTS, **overrides}
        return PatternResult(**kwargs)
    return _factory


@pytest.fixture
def make_price_df():
    """Factory: builds a minimal OHLCV DataFrame from a list of close prices."""
    def _factory(
        closes: list[float],
        volumes: list[float] | None = None,
    ) -> pd.DataFrame:
        n = len(closes)
        if volumes is None:
            volumes = [1_000_000] * n
        dates = pd.bdate_range(end="2026-02-20", periods=n)
        return pd.DataFrame({
            "Open": closes,
            "High": [c * 1.01 for c in closes],
            "Low": [c * 0.99 for c in closes],
            "Close": closes,
            "Volume": volumes,
        }, index=dates)
    return _factory


@pytest.fixture
def tmp_db(tmp_path):
    """Provides a ScanDatabase backed by a temporary file."""
    return ScanDatabase(str(tmp_path / "test.db"))
```

**Step 2: Verify fixtures are discoverable**

Run: `cd stock_pattern_scanner && python -m pytest tests/ --collect-only 2>&1 | head -20`
Expected: Tests collected without errors

**Step 3: Commit**

```bash
git add stock_pattern_scanner/tests/conftest.py
git commit -m "test: add shared conftest.py with factory fixtures"
```

---

## Task 4: Replace Magic Numbers in pattern_scanner.py

Swap all inline numbers in `pattern_scanner.py` with named constants from `constants.py`. No logic changes.

**Files:**
- Modify: `stock_pattern_scanner/pattern_scanner.py`

**Step 1: Run existing tests as baseline**

Run: `cd stock_pattern_scanner && python -m pytest tests/test_pattern_scanner.py -v`
Expected: All PASS

**Step 2: Add constants imports and replace all magic numbers**

At the top of `pattern_scanner.py`, add the import block after existing imports:

```python
from constants import (
    CUP_DEEP_IDEAL_DEPTH_CENTER,
    CUP_DEEP_THRESHOLD_PCT,
    CUP_HANDLE_VOLUME_FACTOR,
    CUP_IDEAL_DEPTH_CENTER,
    CUP_IDEAL_WEEKS,
    CUP_LOOKBACK_BUFFER,
    CUP_MAX_DEPTH_PCT,
    CUP_MAX_LOOKBACK_DAYS,
    CUP_MAX_TOTAL_WEEKS,
    CUP_MIN_AFTER_LIP,
    CUP_MIN_AFTER_LOW,
    CUP_MIN_DEPTH_PCT,
    CUP_MIN_HANDLE_DAYS,
    CUP_MIN_RECOVERY_PCT,
    CUP_MIN_TOTAL_WEEKS,
    CUP_PEAK_WINDOW,
    CUP_DEPTH_PENALTY,
    CUP_HIGH_RECOVERY_PCT,
    CUP_MODERATE_RECOVERY_PCT,
    CUP_TIGHT_HANDLE_DEPTH_PCT,
    DOUBLE_BOTTOM_DEPTH_CENTER,
    DOUBLE_BOTTOM_DEPTH_PENALTY,
    DOUBLE_BOTTOM_IDEAL_DEPTH_HIGH,
    DOUBLE_BOTTOM_IDEAL_DEPTH_LOW,
    DOUBLE_BOTTOM_IDEAL_WEEKS,
    DOUBLE_BOTTOM_LOOKBACK_BUFFER,
    DOUBLE_BOTTOM_LOOKBACK_DAYS,
    DOUBLE_BOTTOM_LOW_DIFF_MAX_PCT,
    DOUBLE_BOTTOM_MAX_DEPTH_PCT,
    DOUBLE_BOTTOM_MIN_AFTER_HIGH,
    DOUBLE_BOTTOM_MIN_DEPTH_PCT,
    DOUBLE_BOTTOM_MIN_SEPARATION_DAYS,
    DOUBLE_BOTTOM_MODERATE_LOW_DIFF,
    DOUBLE_BOTTOM_TIGHT_LOW_DIFF,
    DOUBLE_BOTTOM_TROUGH_WINDOW,
    DOUBLE_BOTTOM_VOLUME_WINDOW,
    FLAT_BASE_DEPTH_PENALTY,
    FLAT_BASE_IDEAL_DEPTH_HIGH,
    FLAT_BASE_IDEAL_DEPTH_LOW,
    FLAT_BASE_IDEAL_WEEKS,
    FLAT_BASE_MA50_THRESHOLD,
    FLAT_BASE_MAX_DEPTH_PCT,
    FLAT_BASE_MAX_WINDOW_DAYS,
    FLAT_BASE_PRIOR_VOLUME_DAYS,
    FLAT_BASE_SEED_DAYS,
    FLAT_BASE_SEED_FLOOR_FACTOR,
    FLAT_BASE_TIGHT_DEPTH_PCT,
    FLAT_BASE_VOLUME_CONTRACTION,
    HANDLE_MAX_DECLINE_PCT,
    HANDLE_MAX_LENGTH_WEEKS,
    MIN_DATA_POINTS,
    PRIOR_UPTREND_LOOKBACK_DAYS,
    PRIOR_UPTREND_MIN_GAIN_PCT,
    PRIOR_UPTREND_MIN_SEGMENT_LEN,
    RS_BASELINE,
    RS_MAX,
    RS_MIN,
    RS_PERIODS,
    RS_WEIGHTS,
    SCORE_ABOVE_200MA_MAX,
    SCORE_ABOVE_50MA_MAX,
    SCORE_BASE_LENGTH_MAX,
    SCORE_DEPTH_MAX,
    SCORE_TIGHTNESS_MAX,
    SCORE_VOLUME_MAX,
    STATUS_AT_PIVOT_THRESHOLD,
    STATUS_EXTENDED_THRESHOLD,
    STATUS_NEAR_PIVOT_LOWER,
    TIGHTNESS_LOOKBACK,
    TIGHTNESS_LOOSE,
    TIGHTNESS_MODERATE,
    TIGHTNESS_TIGHT,
    BASE_LENGTH_OVER_PENALTY,
)
```

Then replace every magic number in each method:

**`PatternResult.status`** — replace `5.0`, `1.0`, `-5.0`:
```python
@property
def status(self) -> str:
    if self.distance_to_pivot > STATUS_EXTENDED_THRESHOLD:
        return "Extended"
    elif abs(self.distance_to_pivot) <= STATUS_AT_PIVOT_THRESHOLD:
        return "At Pivot"
    elif STATUS_NEAR_PIVOT_LOWER <= self.distance_to_pivot < -STATUS_AT_PIVOT_THRESHOLD:
        return "Near Pivot"
    elif self.distance_to_pivot < STATUS_NEAR_PIVOT_LOWER:
        return "Building"
    else:
        return "At Pivot"
```

**`calculate_relative_strength`** — replace `[63, 126, 189, 252]`, `[0.4, 0.2, 0.2, 0.2]`, `50`, `1`, `99`:
```python
def calculate_relative_strength(self, stock_df, spy_df) -> float:
    stock_close = stock_df["Close"]
    spy_close = spy_df["Close"]
    stock_returns = []
    spy_returns = []
    for period in RS_PERIODS:
        if len(stock_close) >= period and len(spy_close) >= period:
            sr = (stock_close.iloc[-1] / stock_close.iloc[-period] - 1) * 100
            spr = (spy_close.iloc[-1] / spy_close.iloc[-period] - 1) * 100
            stock_returns.append(sr)
            spy_returns.append(spr)
        else:
            stock_returns.append(0)
            spy_returns.append(0)
    weighted_stock = sum(r * w for r, w in zip(stock_returns, RS_WEIGHTS))
    weighted_spy = sum(r * w for r, w in zip(spy_returns, RS_WEIGHTS))
    rs_raw = RS_BASELINE + (weighted_stock - weighted_spy)
    return max(RS_MIN, min(RS_MAX, round(rs_raw, 1)))
```

**`_has_prior_uptrend`** — replace `126`, `20`:
```python
def _has_prior_uptrend(self, df, end_idx, min_gain=PRIOR_UPTREND_MIN_GAIN_PCT):
    lookback = PRIOR_UPTREND_LOOKBACK_DAYS
    start_idx = max(0, end_idx - lookback)
    segment = df["Close"].iloc[start_idx:end_idx]
    if len(segment) < PRIOR_UPTREND_MIN_SEGMENT_LEN:
        return False
    # ... rest unchanged
```

**`detect_flat_base`** — replace `200`, `75`, `24`, `0.5`, `15.0`, `25`, `30.0`, `0.50`, `50`, `0.90`:
```python
def detect_flat_base(self, df):
    if len(df) < MIN_DATA_POINTS:
        return None
    full_close = df["Close"].values
    end_pos = len(df) - 1
    max_window = min(FLAT_BASE_MAX_WINDOW_DAYS, len(df))
    seed = full_close[end_pos - (FLAT_BASE_SEED_DAYS - 1) : end_pos + 1]
    # ...
    seed_range = base_high - base_low
    floor = base_low - seed_range * FLAT_BASE_SEED_FLOOR_FACTOR
    base_start = end_pos - (FLAT_BASE_SEED_DAYS - 1)
    for i in range(end_pos - FLAT_BASE_SEED_DAYS, end_pos - max_window, -1):
        # ...
        if depth >= FLAT_BASE_MAX_DEPTH_PCT:
            break
        # ...
    if depth_pct >= FLAT_BASE_MAX_DEPTH_PCT:
        return None
    if base_length < FLAT_BASE_SEED_DAYS:
        return None
    if not self._has_prior_uptrend(df, base_start, min_gain=PRIOR_UPTREND_MIN_GAIN_PCT):
        return None
    # ...
    if close_above_ma50 / len(ma50_valid) <= FLAT_BASE_MA50_THRESHOLD:
        return None
    prior_start = max(0, base_start - FLAT_BASE_PRIOR_VOLUME_DAYS)
    volume_ok = bool(base_avg_vol < prior_avg_vol * FLAT_BASE_VOLUME_CONTRACTION) if prior_avg_vol > 0 else False
    # ...
```

**`detect_double_bottom`** — replace `200`, `190`, `50`, `40`, `8`, `5.0`, `15`, `3`, `15`, `40`, `5`:
All references to be replaced with their corresponding `DOUBLE_BOTTOM_*` constants.

**`detect_cup_and_handle`** — replace `200`, `325`, `50`, `15`, `35`, `12.0`, `50.0`, `15`, `70`, `5`, `6`, `15`, `7`, `65`, `33`, `0.85`:
All references to be replaced with their corresponding `CUP_*` / `HANDLE_*` constants.

**`calculate_confidence`** — replace all scoring magic numbers with `SCORE_*`, `FLAT_BASE_IDEAL_*`, `DOUBLE_BOTTOM_IDEAL_*`, `CUP_*`, `TIGHTNESS_*` constants.

**Step 3: Run tests**

Run: `cd stock_pattern_scanner && python -m pytest tests/test_pattern_scanner.py -v`
Expected: All PASS (behavior unchanged)

**Step 4: Commit**

```bash
git add stock_pattern_scanner/pattern_scanner.py
git commit -m "refactor: replace magic numbers with named constants"
```

---

## Task 5: Unify Ticker Resolution (DRY)

`app.py` and `run_scanner.py` both implement watchlist-to-ticker mapping. Extract to one shared function.

**Files:**
- Modify: `stock_pattern_scanner/ticker_lists.py`
- Modify: `stock_pattern_scanner/app.py`
- Modify: `stock_pattern_scanner/run_scanner.py`

**Step 1: Run baseline tests**

Run: `cd stock_pattern_scanner && python -m pytest tests/test_app.py tests/test_cli.py -v`
Expected: All PASS

**Step 2: Add `resolve_watchlist` to `ticker_lists.py`**

At the bottom of `ticker_lists.py`, add:

```python
def resolve_watchlist(watchlist: str, custom_tickers: list[str] | None = None) -> list[str]:
    """Resolve a watchlist name to a list of ticker symbols.

    Args:
        watchlist: One of 'default', 'sp500', 'nasdaq100', or 'custom'.
        custom_tickers: Required when watchlist is 'custom'.

    Returns:
        List of uppercase ticker strings.
    """
    if custom_tickers:
        return [t.upper() for t in custom_tickers]
    if watchlist == "sp500":
        return get_sp500_tickers()
    if watchlist == "nasdaq100":
        return get_nasdaq100_tickers()
    return list(DEFAULT_GROWTH_WATCHLIST)
```

Also fix the type hints at the top: change `from typing import List` to use `from __future__ import annotations` and replace `List[str]` with `list[str]` everywhere in the file (fixes the inconsistent type hints issue too).

**Step 3: Update `app.py` to use shared function**

Replace the `_resolve_tickers` function:

```python
from ticker_lists import (
    DEFAULT_GROWTH_WATCHLIST,
    get_sp500_tickers,
    get_nasdaq100_tickers,
    resolve_watchlist,
)

# Delete the _resolve_tickers function entirely.
# In start_scan, replace:
#   tickers = _resolve_tickers(request)
# with:
#   tickers = resolve_watchlist(request.watchlist, request.tickers)
```

**Step 4: Update `run_scanner.py` to use shared function**

Replace the `resolve_tickers` function:

```python
from ticker_lists import resolve_watchlist, DEFAULT_GROWTH_WATCHLIST

def resolve_tickers(args: argparse.Namespace) -> list[str]:
    if args.file:
        with open(args.file, encoding="utf-8") as f:
            return [line.strip().upper() for line in f if line.strip()]
    if args.tickers:
        return resolve_watchlist("custom", args.tickers)
    if args.sp500:
        print("Fetching S&P 500 ticker list...")
        return resolve_watchlist("sp500")
    if args.nasdaq100:
        print("Fetching NASDAQ 100 ticker list...")
        return resolve_watchlist("nasdaq100")
    return resolve_watchlist("default")
```

Note: CLI keeps its `resolve_tickers` wrapper because it handles `--file` (file-based input) and `print()` messages that don't exist in the web app. But the core watchlist mapping is now shared.

**Step 5: Run tests**

Run: `cd stock_pattern_scanner && python -m pytest tests/test_app.py tests/test_cli.py -v`
Expected: All PASS

**Step 6: Commit**

```bash
git add stock_pattern_scanner/ticker_lists.py stock_pattern_scanner/app.py stock_pattern_scanner/run_scanner.py
git commit -m "refactor: unify ticker resolution and fix type hints in ticker_lists"
```

---

## Task 6: Add Error Handling to CLI

`run_scanner.py` is missing file-open encoding, and has no top-level exception handling.

**Files:**
- Modify: `stock_pattern_scanner/run_scanner.py`

**Step 1: Add encoding to file open** (already done in Task 5 step 4)

Verify that `open(args.file, encoding="utf-8")` is present from Task 5.

**Step 2: Add top-level error handling in `main()`**

Wrap the scan logic in `main()`:

```python
def main():
    args = parse_args()

    if args.web:
        import uvicorn
        print("Starting web dashboard at http://localhost:8000")
        uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
        return

    try:
        tickers = resolve_tickers(args)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"\nStock Base Pattern Scanner")
    print(f"{'\u2550' * 40}")
    print(f"Scanning {len(tickers)} tickers...\n")

    try:
        start_time = time.time()
        scanner = StockScanner(tickers=tickers, max_workers=5)
        results = scanner.scan(progress_callback=print_progress)
        elapsed = time.time() - start_time
    except KeyboardInterrupt:
        print("\n\nScan interrupted.")
        sys.exit(130)
    except Exception as e:
        print(f"\n\nScan failed: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"\n\nScan complete in {elapsed:.1f}s \u2014 {len(results)} patterns found\n")

    # ... rest unchanged (filters, print, export)
```

**Step 3: Run tests**

Run: `cd stock_pattern_scanner && python -m pytest tests/test_cli.py -v`
Expected: All PASS

**Step 4: Commit**

```bash
git add stock_pattern_scanner/run_scanner.py
git commit -m "fix: add error handling for file open and scan failures in CLI"
```

---

## Task 7: Clean Up app.py

Remove empty lifespan handler. Add temp file cleanup for Excel exports.

**Files:**
- Modify: `stock_pattern_scanner/app.py`

**Step 1: Run baseline**

Run: `cd stock_pattern_scanner && python -m pytest tests/test_app.py -v`
Expected: All PASS

**Step 2: Remove empty lifespan, fix Excel temp file**

Remove the lifespan context manager and its usage:

```python
# Delete these lines:
# from contextlib import asynccontextmanager
# @asynccontextmanager
# async def lifespan(app: FastAPI):
#     yield
# app = FastAPI(title="Stock Pattern Scanner", lifespan=lifespan)

# Replace with:
app = FastAPI(title="Stock Pattern Scanner")
```

Fix the Excel export to use a temp file:

```python
import tempfile

@app.get("/api/export/excel/{scan_id}")
async def export_excel(scan_id: str):
    results = db.get_results(scan_id)
    if not results:
        return {"error": "No results found for this scan"}

    filepath = os.path.join(tempfile.gettempdir(), f"scan_{scan_id}.xlsx")
    export_to_excel(results, filepath)
    return FileResponse(
        filepath,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=f"pattern_scan_{scan_id}.xlsx",
    )
```

Also remove unused `asynccontextmanager` import.

**Step 3: Run tests**

Run: `cd stock_pattern_scanner && python -m pytest tests/test_app.py -v`
Expected: All PASS

**Step 4: Commit**

```bash
git add stock_pattern_scanner/app.py
git commit -m "refactor: remove empty lifespan, use temp dir for Excel exports"
```

---

## Task 8: Fix Test Fragility

Fix module-level env var in `test_app.py` and `cwd` dependency in `test_cli.py`. Migrate tests to use conftest fixtures.

**Files:**
- Modify: `stock_pattern_scanner/tests/test_app.py`
- Modify: `stock_pattern_scanner/tests/test_cli.py`
- Modify: `stock_pattern_scanner/tests/test_database.py`
- Modify: `stock_pattern_scanner/tests/test_excel_export.py`
- Modify: `stock_pattern_scanner/tests/test_pattern_scanner.py`

**Step 1: Fix test_app.py — use monkeypatch instead of module-level os.environ**

```python
# tests/test_app.py
import os
import tempfile

import pytest

# Move env setup into a fixture
@pytest.fixture(autouse=True)
def _set_test_db(monkeypatch, tmp_path):
    monkeypatch.setenv("SCANNER_DB_PATH", str(tmp_path / "test_app.db"))


# Import AFTER fixture is defined (but pytest handles ordering)
# The module-level import still happens at collection time, so we need
# to set the env var before import. Use a conftest-level approach instead.
```

Actually, because `app.py` reads `DB_PATH` at import time (`DB_PATH = os.environ.get(...)`), the cleanest fix is to move the env set into `conftest.py` with a session-scoped autouse fixture, or accept the module-level set but use `tmp_path` via `tempfile`. The simplest safe fix:

```python
# tests/test_app.py
import os
import tempfile

_test_db_dir = tempfile.mkdtemp()
os.environ["SCANNER_DB_PATH"] = os.path.join(_test_db_dir, "test_scanner_app.db")

from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from app import app

client = TestClient(app)


def test_dashboard_loads():
    response = client.get("/")
    assert response.status_code == 200
    assert "Stock Pattern Scanner" in response.text


def test_get_watchlists():
    response = client.get("/api/watchlists")
    assert response.status_code == 200
    data = response.json()
    assert "default" in data
    assert "sp500" in data
    assert "nasdaq100" in data


def test_start_scan():
    response = client.post("/api/scan", json={
        "watchlist": "custom",
        "tickers": ["AAPL", "MSFT"],
    })
    assert response.status_code == 200
    data = response.json()
    assert "scan_id" in data


def test_get_results_pending():
    response = client.get("/api/scan/nonexistent/results")
    assert response.status_code == 200
```

**Step 2: Fix test_cli.py — use absolute path for cwd**

```python
# tests/test_cli.py
import os
import subprocess
import sys

_SCANNER_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_cli_help():
    result = subprocess.run(
        [sys.executable, "run_scanner.py", "--help"],
        capture_output=True, text=True, cwd=_SCANNER_DIR,
    )
    assert result.returncode == 0
    assert "--sp500" in result.stdout
    assert "--nasdaq100" in result.stdout
    assert "--tickers" in result.stdout
    assert "--min-score" in result.stdout


def test_cli_version_or_default():
    result = subprocess.run(
        [sys.executable, "run_scanner.py", "--tickers", "FAKE_TICKER_XYZ", "--no-excel", "--top", "1"],
        capture_output=True, text=True, cwd=_SCANNER_DIR, timeout=120,
    )
    assert "Traceback" not in result.stderr or "Traceback" not in result.stdout
```

**Step 3: Migrate test_database.py to use conftest fixtures**

```python
# tests/test_database.py


def test_create_scan(tmp_db):
    scan_id = tmp_db.create_scan(watchlist="default", tickers=["AAPL", "MSFT"])
    assert isinstance(scan_id, str)
    assert len(scan_id) > 0


def test_update_scan_progress(tmp_db):
    scan_id = tmp_db.create_scan(watchlist="default", tickers=["AAPL"])
    tmp_db.update_progress(scan_id, current=1, total=2, ticker="AAPL")
    progress = tmp_db.get_progress(scan_id)
    assert progress["current"] == 1
    assert progress["total"] == 2
    assert progress["ticker"] == "AAPL"


def test_save_and_get_results(tmp_db, make_pattern_result):
    scan_id = tmp_db.create_scan(watchlist="default", tickers=["AAPL"])
    result = make_pattern_result(
        confidence_score=80.0,
        pattern_details={"base_high": 152.0},
    )
    tmp_db.save_results(scan_id, [result])
    tmp_db.update_status(scan_id, "completed")

    results = tmp_db.get_results(scan_id)
    assert len(results) == 1
    assert results[0].ticker == "AAPL"
    assert results[0].confidence_score == 80.0

    assert tmp_db.get_scan_status(scan_id) == "completed"
```

**Step 4: Migrate test_excel_export.py to use conftest fixtures**

```python
# tests/test_excel_export.py
import os
from openpyxl import load_workbook
from excel_export import export_to_excel


def _sample_results(make_pattern_result):
    return [
        make_pattern_result(
            ticker="AAPL", pattern_type="Cup & Handle", confidence_score=85.0,
            buy_point=195.0, current_price=193.0, distance_to_pivot=-1.0,
            base_depth=22.0, base_length_weeks=14, rs_rating=88.0,
            pattern_details={"cup_low": 160.0},
        ),
        make_pattern_result(
            ticker="NVDA", pattern_type="Flat Base", confidence_score=72.0,
            buy_point=500.0, current_price=485.0, distance_to_pivot=-3.0,
            base_depth=9.0, base_length_weeks=6, volume_confirmation=False,
            rs_rating=95.0,
        ),
    ]


def test_export_creates_file(tmp_path, make_pattern_result):
    results = _sample_results(make_pattern_result)
    path = str(tmp_path / "test_report.xlsx")
    export_to_excel(results, path)
    assert os.path.exists(path)


def test_export_has_three_sheets(tmp_path, make_pattern_result):
    results = _sample_results(make_pattern_result)
    path = str(tmp_path / "test_report.xlsx")
    export_to_excel(results, path)
    wb = load_workbook(path)
    assert "Pattern Scanner Results" in wb.sheetnames
    assert "Pattern Guide" in wb.sheetnames
    assert "Top Picks" in wb.sheetnames


def test_export_results_sheet_has_data(tmp_path, make_pattern_result):
    results = _sample_results(make_pattern_result)
    path = str(tmp_path / "test_report.xlsx")
    export_to_excel(results, path)
    wb = load_workbook(path)
    ws = wb["Pattern Scanner Results"]
    assert ws.max_row >= 3
    assert ws["A2"].value == "AAPL"
```

**Step 5: Clean up test_pattern_scanner.py — use `make_price_df` fixture**

Remove the module-level `_make_price_df` helper function. Update all tests that used it to accept the `make_price_df` fixture parameter instead. The function signature is identical, so only parameter passing changes.

For example:
```python
# Before:
def test_add_moving_averages():
    closes = list(range(100, 300))
    df = _make_price_df(closes)

# After:
def test_add_moving_averages(make_price_df):
    closes = list(range(100, 300))
    df = make_price_df(closes)
```

Apply this change to all tests that call `_make_price_df`: `test_add_moving_averages`, `test_calculate_relative_strength`, `test_detect_flat_base_valid`, `test_detect_flat_base_too_deep`, `test_detect_flat_base_no_prior_uptrend`, `test_detect_double_bottom_valid`, `test_detect_double_bottom_lows_too_far_apart`, `test_detect_cup_and_handle_valid`, `test_detect_cup_and_handle_deep`, `test_detect_cup_and_handle_too_shallow`, `test_confidence_score_high_quality`, `test_confidence_score_low_quality`.

**Step 6: Run all tests**

Run: `cd stock_pattern_scanner && python -m pytest tests/ -v`
Expected: All PASS

**Step 7: Commit**

```bash
git add stock_pattern_scanner/tests/
git commit -m "test: migrate to shared fixtures and fix test fragility"
```

---

## Task 9: Replace Scanner Magic Numbers

Replace remaining magic numbers in `StockScanner` class and `run_scanner.py`.

**Files:**
- Modify: `stock_pattern_scanner/pattern_scanner.py` (StockScanner class)
- Modify: `stock_pattern_scanner/run_scanner.py`
- Modify: `stock_pattern_scanner/app.py`

**Step 1: Update StockScanner defaults**

In `pattern_scanner.py`, import and use scanner constants:

```python
from constants import DEFAULT_MAX_WORKERS, DEFAULT_HISTORY_PERIOD

class StockScanner:
    def __init__(self, tickers: list[str], max_workers: int = DEFAULT_MAX_WORKERS):
        # ...

    def _fetch_data(self, ticker: str) -> pd.DataFrame | None:
        try:
            t = yf.Ticker(ticker)
            df = t.history(period=DEFAULT_HISTORY_PERIOD)
            if df is None or len(df) < MIN_DATA_POINTS:
                return None
            # ...
```

**Step 2: Update app.py**

```python
from constants import DEFAULT_MAX_WORKERS, SSE_POLL_INTERVAL

# In _run_scan:
scanner = StockScanner(tickers=tickers, max_workers=DEFAULT_MAX_WORKERS)

# In scan_progress:
await asyncio.sleep(SSE_POLL_INTERVAL)
```

**Step 3: Update run_scanner.py**

```python
from constants import PROGRESS_BAR_LENGTH, DEFAULT_TOP_RESULTS, NEAR_PIVOT_THRESHOLD, DEFAULT_MAX_WORKERS

# In parse_args:
parser.add_argument("--top", type=int, default=DEFAULT_TOP_RESULTS, ...)

# In print_progress:
bar_len = PROGRESS_BAR_LENGTH

# In main:
scanner = StockScanner(tickers=tickers, max_workers=DEFAULT_MAX_WORKERS)

# In near_pivot filter:
results = [r for r in results if abs(r.distance_to_pivot) <= NEAR_PIVOT_THRESHOLD]
```

**Step 4: Run all tests**

Run: `cd stock_pattern_scanner && python -m pytest tests/ -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add stock_pattern_scanner/pattern_scanner.py stock_pattern_scanner/app.py stock_pattern_scanner/run_scanner.py
git commit -m "refactor: replace remaining magic numbers in scanner, app, and CLI"
```

---

## Verification Checklist

After all tasks, run the full suite:

```bash
cd stock_pattern_scanner && python -m pytest tests/ -v
```

Expected: All tests PASS with zero behavior changes.

Files modified:
- `constants.py` (new)
- `database.py` (context manager fix)
- `pattern_scanner.py` (constants)
- `ticker_lists.py` (shared resolve + type hints)
- `app.py` (cleanup + shared resolve)
- `run_scanner.py` (error handling + shared resolve + constants)
- `tests/conftest.py` (new)
- `tests/test_app.py` (env var fix)
- `tests/test_cli.py` (cwd fix)
- `tests/test_database.py` (fixtures)
- `tests/test_excel_export.py` (fixtures)
- `tests/test_pattern_scanner.py` (fixtures)
