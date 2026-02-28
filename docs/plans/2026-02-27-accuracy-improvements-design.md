# Accuracy Improvements Design

**Goal:** Add critical context signals and tighten existing filters so detected patterns are more likely to be real winners. Narrow scope, higher confidence.

**Approach:** 3 new signals (earnings, sector RS, liquidity floor) + 4 scoring/filter refinements (200MA gate, regime softening, volume grading, score rebalance) + help text for every new element.

---

## 1. Earnings Analysis (FMP Integration)

### New Module: `earnings_analysis.py`

**Data Source:** Financial Modeling Prep (FMP) API, free tier (250 req/day, free API key).

**Data Fetched Per Ticker (one FMP call each):**
- Next earnings date from FMP earnings calendar endpoint
- Last 4 quarters of EPS surprises — actual vs estimate, surprise percentage

### Signal A: Earnings Proximity Warning

- Earnings within 14 calendar days: flag as "Earnings Soon" (warning)
- Earnings within 7 days: flag as "Earnings Imminent" (strong warning)
- No upcoming date found: no flag (neutral)
- Warning only, not a score modifier — the investor decides whether to take the risk

### Signal B: Post-Earnings Momentum Score (0-10 pts)

Looks at the most recent completed quarter:
- EPS beat by 5%+: +3 pts
- EPS beat by 15%+: +5 pts (replaces the 3)
- Last 2 quarters both beats: +3 pts bonus
- Stock gapped up on earnings day (close > prior close by 3%+): +2 pts
- Max 10 points added to confidence score
- 0 points if missed estimates or data unavailable (no data = no penalty)

### FMP Rate Limiting

- Cache earnings data per ticker for 24 hours (SQLite)
- Batch requests with 300ms delay to stay under free tier limits
- If FMP call fails for a ticker, skip earnings scoring (0 pts, no warning) — graceful degradation

---

## 2. Sector Relative Strength

### New Module: `sector_strength.py`

**Data Source:** yfinance (already a dependency), 11 GICS sector ETFs.

### Sector ETF Mapping

| Sector | ETF |
|--------|-----|
| Technology | XLK |
| Healthcare | XLV |
| Financials | XLF |
| Consumer Discretionary | XLY |
| Communication Services | XLC |
| Industrials | XLI |
| Consumer Staples | XLP |
| Energy | XLE |
| Utilities | XLU |
| Real Estate | XLRE |
| Materials | XLB |

### How It Works

**Step 1: Map each ticker to its sector ETF**
- Static mapping dict for watchlist stocks (covers ~95%)
- Fallback: fetch sector from yfinance `.info['sector']` for unknown tickers
- Cache the mapping — sectors don't change

**Step 2: Compute sector RS**
- Fetch 1 year of daily data for all 11 sector ETFs (one batch on scan start, cached 24 hours)
- Calculate weighted returns vs SPY using the same 4-period formula already in pattern_scanner.py
- Produces a sector RS score (1-99) for each ETF

**Step 3: Classify and apply**

| Sector RS | Classification | Confidence Effect |
|-----------|---------------|-------------------|
| 70+ | Leading Sector | +5 pts |
| 50-69 | Neutral Sector | 0 pts |
| Below 50 | Lagging Sector | -10 pts (penalty) |

Asymmetric scoring: being in a lagging sector is a stronger negative signal than being in a leading sector is positive. Patterns in dying sectors fail at ~2x the rate. The penalty is applied as a post-scoring overlay (can push score below original, clamped to 1 minimum).

### Performance

- 11 ETF data fetches on scan start (cached 24 hours)
- Sector classification computed once per scan, applied to all tickers
- Negligible overhead

---

## 3. Liquidity Floor

**Where:** Early in scan pipeline, before pattern detection.

- Calculate: `avg_dollar_volume = 50-day avg volume × current price`
- If `avg_dollar_volume < $5,000,000`: skip ticker entirely
- Constant: `MIN_AVG_DOLLAR_VOLUME = 5_000_000` (configurable)
- Runs after data fetch but before pattern detection — saves scan time too
- Display in scan progress: "Skipped X tickers (low liquidity)"

---

## 4. 50MA > 200MA Hard Gate

**Current:** Stock above 200MA = +5 pts, above 50MA = +10 pts. Stocks below both can still score 85/100.

**New:** If `50MA < 200MA` (death cross), reject the pattern entirely. Don't score it, don't show it.

**Exception:** During market correction regime, relax this to a warning instead of a gate. Reason: during market-wide corrections, many good stocks temporarily lose their golden cross but form valid bases for the recovery.

**Display:** "Skipped X patterns (below 200MA)" in scan progress.

---

## 5. Market Regime Softening

**Current:** When market is "In Correction", all buy signals are disabled.

**New behavior:**

| Regime | Effect |
|--------|--------|
| Confirmed Uptrend | Full confidence scores, all signals active |
| Uptrend Under Pressure | Scores shown normally, "Caution" badge added |
| In Correction | Patterns still detected and shown, -15 pt confidence penalty, "Correction" badge |

**Why:** The best bases of the next bull market form during corrections. Hiding them means missing the setup. Penalizing scores is more useful — only the strongest survive the penalty.

---

## 6. Volume Confirmation Grading

**Current:** Binary — volume surged 40%+ = confirmed, else not. 5 pts or 0.

**New graded scale:**

| Volume Surge | Classification | Breakout Pts |
|-------------|---------------|-------------|
| < 20% above avg | Weak | 0 pts |
| 20-39% above avg | Moderate | 2 pts |
| 40-79% above avg | Confirmed | 4 pts |
| 80-149% above avg | Strong | 5 pts |
| 150%+ above avg | Climactic (warning) | 3 pts |

**Why climactic warning:** 150%+ volume on breakout often signals exhaustion — everyone who wanted to buy already did. Higher failure rate. Score drops from 5 to 3 and a warning badge appears.

---

## 7. Confidence Score Rebalance

### New Distribution (still 100 max)

| Factor | Old | New | Change |
|--------|-----|-----|--------|
| Base Depth | 15 | 10 | -5 |
| Volume Profile | 20 | 15 | -5 |
| Above 50MA | 10 | 10 | — |
| Above 200MA | 5 | 5 | — |
| Tightness | 10 | 10 | — |
| Base Length | 5 | 5 | — |
| Pattern Bonus | 10 | 10 | — |
| Trend Strength | 10 | 10 | — |
| RS Rating | 10 | 10 | — |
| Breakout Quality | 5 | 5 | — |
| **Earnings Momentum** | — | **10** | **+10** |
| **Total** | **100** | **100** | — |

Sector RS overlay is applied post-scoring (+5/-10), not part of the 100-point base.

---

## 8. Dashboard Changes

### Results Table — New Columns

**Earnings column:**
- Shows days until earnings (e.g., "12d") with color coding
- 14 days or less: yellow "Earnings Soon" badge
- 7 days or less: red "Earnings Imminent" badge
- If recent strong quarter: green "Beat" badge
- Tooltip: explains earnings proximity risk and post-earnings momentum

**Sector column:**
- Sector name + directional arrow: ↑ (leading), → (neutral), ↓ (lagging)
- Color coded: green for leading, default for neutral, red for lagging
- Tooltip: explains sector RS and why leading sectors produce more winners

**Volume column (updated):**
- Replace binary checkmark/X with graded labels: Weak, Mod, ✓, Strong, ⚠ Climactic
- Color coded: red (weak), yellow (moderate), green (confirmed/strong), orange (climactic)
- Tooltip updated for each grade

### Progress Bar Updates

- "Skipped X tickers (low liquidity)" after scan completes
- "Skipped Y patterns (below 200MA)" after scan completes

### Market Regime Badges

- Uptrend Under Pressure: "Caution" badge with tooltip
- In Correction: "Correction" badge with tooltip, replaces "Buy signals disabled"

### Help Panel Updates

**New sections:**
- "Earnings & Timing" — why earnings dates matter, how to read the Beat badge and proximity warning, how earnings momentum feeds into scoring
- "Sector Strength" — what sector rotation is, why leading sectors matter, how the ↑→↓ indicators work

**Updated sections:**
- "Reading Your Results" — add guidance for Earnings, Sector, and updated Volume columns
- "Glossary" — add terms: Earnings Surprise, Sector RS, Dollar Volume, Death Cross, Golden Cross, Climactic Volume

---

## 9. Implementation Scope

### New Files
- `stock_pattern_scanner/earnings_analysis.py`
- `stock_pattern_scanner/sector_strength.py`

### Modified Files
- `stock_pattern_scanner/pattern_scanner.py` — score rebalance, 200MA gate, sector overlay, earnings integration
- `stock_pattern_scanner/stock_scanner.py` — liquidity floor, skip counters, earnings/sector pipeline integration
- `stock_pattern_scanner/breakout_rules.py` — graded volume confirmation
- `stock_pattern_scanner/market_regime.py` — softened correction behavior
- `stock_pattern_scanner/database.py` — earnings cache table
- `stock_pattern_scanner/templates/dashboard.html` — new columns, badges, tooltips, help panel sections
- `stock_pattern_scanner/app.py` — FMP API key config, earnings cache endpoint (if needed)

### New Dependencies
- `requests` (for FMP API calls — likely already available)
- FMP API key (free, stored as environment variable `FMP_API_KEY`)

### What's NOT Changing
- Pattern detection algorithms (cup & handle, double bottom, flat base geometry)
- Backtest engine (inherits improved scoring automatically)
- API endpoint structure
- Watchlist system
- Export functionality

### Testing
- All existing 82 tests must continue to pass
- New unit tests for earnings_analysis.py and sector_strength.py
- Modified tests for updated scoring, volume grading, regime changes
- Integration test: full scan with earnings + sector data
