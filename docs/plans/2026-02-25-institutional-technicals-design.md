# Institutional-Grade Technical Analysis — Design

**Goal:** Improve scanner accuracy by adding institutional-quality technical analysis: market regime detection, volume accumulation profiling, breakout confirmation rules, trend strength validation, and revised confidence scoring.

**Architecture:** Layered enhancement — four new modules added alongside existing detection engine. Each module is independent and testable in isolation. No rewrite of existing pattern detection logic.

**Tech Stack:** Python 3.13, numpy (already installed), yfinance (existing), no new dependencies.

---

## Module 1: Market Regime Detection (`market_regime.py`)

Hard gate that determines whether buy signals should be shown based on overall market health.

**Signals checked using SPY daily data:**
- SPY price vs 200-day MA (above = bullish, below = bearish)
- SPY price vs 50-day MA (short-term trend)
- Distribution day count in last 25 sessions (high-volume down days >0.2%)
- 50-day MA slope (rising vs falling)

**Three states:**
- **Confirmed Uptrend** — SPY above 200-day MA, 50-day MA rising, <4 distribution days. All patterns allowed.
- **Uptrend Under Pressure** — SPY above 200-day MA but 4+ distribution days or 50-day MA flattening. Patterns shown with warning.
- **Market in Correction** — SPY below 200-day MA or 50-day MA declining + 5+ distribution days. Hard gate: no buy signals.

**Distribution day definition:** SPY closes down >0.2% on volume higher than the previous session (IBD standard).

**Integration:** `StockScanner.scan()` calls `MarketRegime.evaluate()` first. If correction, returns empty results with status message.

---

## Module 2: Volume Accumulation/Distribution Analysis (`volume_analysis.py`)

Replaces binary volume confirmation with institutional-grade volume profiling over the base formation period.

**Three indicators:**

1. **Accumulation/Distribution Rating (A-E)** — Count up-volume days vs down-volume days during base formation. Up day on above-average volume = accumulation. Down day on above-average volume = distribution. Grade A = heavy accumulation, E = heavy distribution.

2. **Volume Dry-Up Score** — Avg volume in last 10 days of base / avg volume in first half of base. Measures seller exhaustion at the pivot. Lower = better.

3. **Up/Down Volume Ratio** — Total volume on up days / total volume on down days over base period. >1.0 = net accumulation. >1.5 = strong.

**Scoring (0-20 pts):**
- A/D Rating A or B + dry-up < 0.7 + up/down ratio > 1.3 = full 20 pts
- Graduated scale down from there
- D or E rating = 0 pts

**Hard filter:** A/D Rating of D or E discards the pattern entirely (institutions selling).

---

## Module 3: Breakout Confirmation & Entry Rules (`breakout_rules.py`)

Validates breakouts and calculates risk/reward for every pattern.

**Breakout validation (when price is within 2% above pivot):**

1. **Volume surge** — Breakout day volume must be ≥40% above 50-day average volume (O'Neil minimum threshold).
2. **Close in upper half** — Breakout day close must be in upper 50% of the day's range.
3. **Not extended** — Price must be within 5% above buy point.

**Risk/reward (applied to all patterns):**
- **Stop-loss:** 7% below buy point (O'Neil hard rule)
- **Profit target:** 20% above buy point
- **Risk/reward ratio:** ~1:3

**New PatternResult fields:**
- `stop_loss_price: float` — buy_point × 0.93
- `profit_target_price: float` — buy_point × 1.20
- `breakout_confirmed: bool | None` — True/False if breakout data available, None if not yet at pivot
- `volume_surge_pct: float | None` — breakout day volume vs 50-day avg

**New status values:**
- "Breakout Confirmed" — at pivot + volume surge + close in upper half
- "Failed Breakout" — crossed pivot but reversed on weak volume

---

## Module 4: Trend Strength Validation (`trend_strength.py`)

Replaces the blunt "30% gain in 6 months" check with actual trend quality measurement.

**Three measurements:**

1. **ADX (Average Directional Index)** — 14-period standard Wilder smoothing. ADX > 25 = strong trend, < 20 = weak. Calculated from daily high/low/close.

2. **50-day MA Slope** — Linear regression slope of the 50-day MA over the 50 days prior to base formation. Positive = institutional accumulation uptrend.

3. **ATR Ratio** — 14-day Average True Range / stock price. Smooth uptrends have low ATR ratios. > 5% = too volatile for reliable bases.

**Integration:**
- **Hard filter on prior uptrend:** Requires 30% gain AND (ADX > 20 OR positive MA slope). Filters out stocks that spiked then went sideways.
- **Scoring bonus:** ADX > 30 with positive MA slope = +5 pts
- **Volatility filter:** ATR ratio > 5% = discard pattern entirely.

No new dependencies — uses numpy with existing OHLC data.

---

## Module 5: Enhanced Confidence Scoring

Revised 0-100 scoring model integrating all new modules.

| Component | Points | Source |
|-----------|--------|--------|
| Base Depth | 15 | Existing logic, reweighted |
| Volume Profile | 20 | volume_analysis.py |
| Price Above 50-day MA | 10 | Existing |
| Price Above 200-day MA | 5 | Existing, reduced |
| Consolidation Tightness | 10 | Existing |
| Base Length | 5 | Existing, reduced |
| Pattern-Specific Bonuses | 10 | Existing |
| Trend Strength | 10 | trend_strength.py |
| RS Rating | 10 | RS > 80 = 10, 60-80 = 5, < 60 = 0 |
| Breakout Quality | 5 | breakout_rules.py |

**Minimum viable score:** Patterns below 40 are filtered out.

---

## Module 6: Dashboard & API Updates

**Market Health Banner:**
- Green: "Confirmed Uptrend" — scanning enabled
- Yellow: "Uptrend Under Pressure" — tighter criteria
- Red: "Market in Correction" — no buy signals

**New results table columns:** Volume Rating (A-E), Trend Strength, Stop Loss, Profit Target, Breakout Status.

**API changes:**
- `GET /api/market-status` — regime, SPY vs MAs, distribution count
- Existing results endpoint gets new fields (additive, non-breaking)

**Filters applied before returning results:**
- Score < 40 → excluded
- Volume rating D/E → excluded
- ATR ratio > 5% → excluded
- Market in correction → empty results with status message
