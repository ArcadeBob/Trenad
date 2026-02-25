# Stock Base Pattern Scanner — Design Document

**Date:** 2026-02-24
**Status:** Approved

## Overview

Python-based stock screening web app that identifies stocks building classic base patterns (CAN SLIM methodology). Fetches live market data via yfinance, detects patterns, calculates quality scores, and presents results through a FastAPI web app and CLI.

## Architecture

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Browser UI  │◄───►│  FastAPI Server   │◄───►│  Scanner Engine  │
│  (HTML/JS)   │ SSE │  - REST API       │     │  - PatternDetect │
│  Dark theme  │     │  - SSE progress   │     │  - Data fetching │
│  Filters     │     │  - Background     │     │  - Scoring       │
│  Sort/Search │     │    tasks          │     │  - RS Rating     │
└─────────────┘     └──────────────────┘     └─────────────────┘
                            │
                    ┌───────┴───────┐
                    │  SQLite Cache  │
                    │  (scan results │
                    │   + price data)│
                    └───────────────┘
```

## Pattern Definitions

### 1. Cup & Handle
- U-shaped base followed by small downward-drifting handle
- Cup depth: 12-33% correction from prior high
- Handle: 1-6 weeks, <15% decline, declining volume
- Duration: 7-65 weeks total
- Prior uptrend: 30%+ advance required
- Buy point: break above handle high on volume surge

### 2. Deep Cup & Handle
- Same as Cup & Handle but 33-50% cup depth
- Typically forms in volatile/bear markets

### 3. Double Bottom
- W-pattern with two lows within 3-5% of each other
- Second low may slightly undercut first (bullish shakeout)
- Depth: 20-30% typical correction
- Buy point: break above middle peak

### 4. Flat Base
- Tight sideways consolidation, <15% range
- Minimum 5 weeks duration
- Prior uptrend: 30%+ advance required
- Should form mostly above 50-day MA
- Buy point: break above base high

## Core Engine (shared by web + CLI)

### PatternDetector class
- `detect_cup_and_handle(df)` — returns pattern dict or None
- `detect_double_bottom(df)` — returns pattern dict or None
- `detect_flat_base(df)` — returns pattern dict or None
- `find_local_peaks(prices, window)` — helper for local maxima
- `find_local_troughs(prices, window)` — helper for local minima
- `calculate_relative_strength(stock_df, spy_df)` — RS rating 0-100

### StockScanner class
- Concurrent fetching via ThreadPoolExecutor with throttling
- Progress callback for UI updates
- Returns sorted list of PatternResult objects

### PatternResult dataclass
```python
@dataclass
class PatternResult:
    ticker: str
    pattern_type: str       # "Cup & Handle", "Deep Cup & Handle", "Double Bottom", "Flat Base"
    confidence_score: float  # 0-100
    buy_point: float
    current_price: float
    distance_to_pivot: float # percentage
    base_depth: float        # percentage correction
    base_length_weeks: int
    volume_confirmation: bool
    above_50ma: bool
    above_200ma: bool
    rs_rating: float         # 0-100 relative strength vs SPY
    pattern_details: Dict
```

### Confidence Scoring (0-100)
Based on: ideal characteristic match, volume confirmation, price vs moving averages, consolidation tightness, recovery percentage.

## Web App (FastAPI)

### API Endpoints
- `GET /` — dashboard (Jinja2 template)
- `POST /api/scan` — starts scan, returns scan_id. Params: watchlist preset, custom tickers, min score, filters
- `GET /api/scan/{scan_id}/progress` — SSE streaming progress
- `GET /api/scan/{scan_id}/results` — results JSON
- `GET /api/export/excel/{scan_id}` — download .xlsx
- `GET /api/watchlists` — available presets

### Background Tasks
Scans run as background tasks. Results cached in SQLite.

## Frontend

- Single-page, vanilla JS, dark trading terminal theme
- Top bar: watchlist dropdown, custom ticker input, Scan button
- SSE-driven progress bar showing current ticker
- Stats cards: total found, at pivot, near pivot, high quality
- Sortable/filterable results table
- Color-coded badges for pattern types and status
- Excel export download button

## CLI Runner

argparse interface:
```
python run_scanner.py                      # Default growth watchlist
python run_scanner.py --sp500              # Scan S&P 500
python run_scanner.py --nasdaq100          # Scan NASDAQ 100
python run_scanner.py --tickers AAPL MSFT  # Specific tickers
python run_scanner.py --file tickers.txt   # From file
python run_scanner.py --min-score 70       # Filter by score
python run_scanner.py --near-pivot         # Only within 5% of buy point
python run_scanner.py --top 20             # Show top N
python run_scanner.py --no-excel           # Skip Excel export
python run_scanner.py --output myfile.xlsx # Custom filename
```

## Ticker Lists

Dynamic S&P 500 / NASDAQ 100 lists fetched from Wikipedia at runtime with hardcoded fallback.

Default growth watchlist (~100 tickers): Software/Cloud, Semiconductors, Consumer/Retail, Healthcare, Fintech, Mega-cap Tech, Energy/Industrial.

## Data Source

- yfinance: 2 years historical price data
- Moving averages: 10, 20, 50, 200-day
- 50-day average volume
- SPY for relative strength

## Excel Export

- Sheet 1 "Pattern Scanner Results": full table, conditional formatting (green >=75, yellow 60-74)
- Sheet 2 "Pattern Guide": pattern definitions
- Sheet 3 "Top Picks": filtered actionable stocks

## File Structure

```
stock_pattern_scanner/
├── app.py                # FastAPI app, routes, SSE
├── pattern_scanner.py    # Core PatternDetector + StockScanner
├── excel_export.py       # Excel report generation
├── ticker_lists.py       # Dynamic S&P 500 / NASDAQ 100 fetching
├── database.py           # SQLite cache for scan results
├── run_scanner.py        # CLI entry point
├── templates/
│   └── dashboard.html    # Jinja2 (HTML + embedded CSS/JS)
├── requirements.txt
└── README.md
```

## Decisions

- **FastAPI + vanilla JS** over Streamlit/React for real-time capability + simplicity
- **Concurrent fetching** with ThreadPoolExecutor + throttling for performance
- **SQLite cache** for scan persistence across page reloads
- **SSE** for progress streaming (simpler than WebSockets for one-way updates)
- **Dynamic ticker lists** from Wikipedia with hardcoded fallback
- **Local-first** but structured for future deployment (env vars, no hardcoded paths)

## Deferred to Future Versions

- WebSocket live price streaming
- Scheduled background scanning
- User accounts / saved watchlists
- Docker deployment config
