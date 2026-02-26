# Stock Base Pattern Scanner

Scans stocks for CAN SLIM base patterns (Cup & Handle, Deep Cup & Handle, Double Bottom, Flat Base) using live market data from yfinance. Includes a dark-themed web dashboard, CLI with table output, and Excel export.

## Quick Start

```bash
pip install -r requirements.txt

# Launch web dashboard
python run_scanner.py --web

# Or run a CLI scan
python run_scanner.py
```

## CLI Usage

```bash
# Scan the default growth watchlist
python run_scanner.py

# Scan S&P 500
python run_scanner.py --sp500

# Scan NASDAQ 100 with minimum score filter
python run_scanner.py --nasdaq100 --min-score 60

# Scan specific tickers
python run_scanner.py --tickers AAPL MSFT NVDA GOOGL

# Read tickers from a file
python run_scanner.py --file my_watchlist.txt

# Show only near-pivot stocks, top 10, skip Excel export
python run_scanner.py --near-pivot --top 10 --no-excel

# Custom Excel output filename
python run_scanner.py --output my_scan.xlsx
```

## Web Dashboard

```bash
python run_scanner.py --web
# Visit http://localhost:8000
```

Features:
- Dark theme with real-time SSE progress streaming
- Watchlist selection (Growth, S&P 500, NASDAQ 100, Custom)
- Min confidence score slider
- Sortable results table with color-coded pattern and status badges
- Filter by pattern type, status, or ticker search
- One-click Excel export

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Web dashboard |
| POST | `/api/scan` | Start a scan (body: `{watchlist, tickers, min_score}`) |
| GET | `/api/scan/{id}/progress` | SSE progress stream |
| GET | `/api/scan/{id}/results` | Scan results JSON |
| GET | `/api/export/excel/{id}` | Download Excel report |
| GET | `/api/watchlists` | Available watchlist presets |

## Patterns Detected

- **Cup & Handle** — U-shaped base (12-33% depth) with a small handle. 7-65 weeks.
- **Deep Cup & Handle** — Same shape but 33-50% depth. Typically forms in volatile markets.
- **Double Bottom** — W-pattern with two lows within 3-5% of each other. Buy point at middle peak.
- **Flat Base** — Tight sideways consolidation (<15% range), minimum 5 weeks.

## Running Tests

```bash
# Unit tests
python -m pytest tests/ -v -m "not integration"

# Integration test (hits network)
python -m pytest tests/ -v -m integration

# All tests
python -m pytest tests/ -v
```
