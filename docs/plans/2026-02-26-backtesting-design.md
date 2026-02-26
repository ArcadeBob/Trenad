# Backtesting Design — Pattern Validation

## Goal

Add backtesting to validate whether detected patterns lead to profitable trades. The primary question: **which pattern types, confidence thresholds, and market conditions produce the best results?**

## Architecture

- New `backtest.py` module — walk-forward replay engine, trade simulation, metrics
- New DB tables `backtests` + `backtest_trades` in existing `scanner.db`
- New dashboard tab with launch form, SSE progress, summary metrics, breakdown tables, trade log
- New API endpoints: POST start, GET SSE progress, GET results

## Engine Design

**Walk-forward weekly replay using existing 2-year yfinance data:**

1. **Warmup:** Skip first 200 trading days (pattern detector minimum)
2. **Walk forward:** Every 5 trading days, run pattern detection on data up to that date
3. **Trade entry:** When a pattern is detected, record pending trade at buy_point
4. **Trade execution:** On subsequent days, if price crosses buy_point, trade is entered
5. **Trade exit:** Check daily for stop-loss or profit-target hit; mark as "open" if period ends
6. **Deduplication:** Skip new signals for a ticker that already has an open trade

**Inputs per run:**
- Ticker list (or watchlist name)
- Stop-loss % (default 7)
- Profit target % (default 20)
- Min confidence score (default 40)

## Trade Record Fields

- ticker, pattern_type, confidence_score
- detection_date, entry_date, entry_price
- exit_date, exit_price, exit_reason (stop/target/open)
- pnl_pct, market_regime

## Metrics

**Overall:** total trades, win rate %, avg return %, profit factor, avg win %, avg loss %, expectancy

**Breakdowns:**
- By pattern type: Flat Base vs Double Bottom vs Cup & Handle
- By confidence band: 40-60, 60-80, 80-100
- By market regime: Confirmed Uptrend vs Under Pressure
- By breakout status: Confirmed vs not

No equity curve or position sizing — focused on pattern validation.

## Database

**Table: `backtests`**
- backtest_id TEXT PK
- watchlist TEXT
- tickers TEXT (JSON)
- stop_loss_pct REAL
- profit_target_pct REAL
- min_confidence REAL
- status TEXT (running/completed/failed)
- created_at TEXT
- completed_at TEXT
- progress_current INTEGER
- progress_total INTEGER
- total_trades INTEGER
- win_rate REAL
- profit_factor REAL

**Table: `backtest_trades`**
- id INTEGER PK AUTOINCREMENT
- backtest_id TEXT FK
- ticker TEXT
- pattern_type TEXT
- confidence_score REAL
- detection_date TEXT
- entry_date TEXT
- entry_price REAL
- exit_date TEXT
- exit_price REAL
- exit_reason TEXT (stop/target/open)
- pnl_pct REAL
- market_regime TEXT

## Dashboard

- New "Backtest" tab alongside existing scanner
- Launch form: watchlist selector, stop-loss %, profit-target %, min confidence
- SSE progress bar (reuses existing pattern)
- Summary card: total trades, win rate, profit factor, avg return, expectancy
- Four breakdown tables: pattern type, confidence band, market regime, breakout status
- Sortable trade log with all individual trades
- Color coding: green wins, red losses, yellow open

## API Endpoints

- `POST /api/backtest` — start backtest run
- `GET /api/backtest/{id}/progress` — SSE stream
- `GET /api/backtest/{id}/results` — full results + metrics + breakdowns

## Constraints

- Uses existing 2-year yfinance data (no additional downloads beyond what scanner fetches)
- Weekly scan interval (every 5 trading days) to keep runtime reasonable
- Reuses existing PatternDetector, market regime, volume analysis, breakout rules
- No new dependencies
