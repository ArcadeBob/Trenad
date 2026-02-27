# Investor Guide & Tooltips Design

**Goal:** Make the dashboard fully understandable for a brand-new investor by adding contextual tooltips to every technical term and a slide-in help panel with pattern illustrations, explanations, and a glossary.

**Approach:** Combination of inline tooltips (quick answers) + a slide-in help panel (deeper learning). Conversational/practical tone with moderate depth (2-3 sentences, actionable context). SVG illustrations for each pattern type.

---

## 1. Tooltip System

Small `ⓘ` icons appear next to every technical term and column header. Hover (desktop) or tap (mobile) shows a popover with a 2-3 sentence explanation.

### Scanner Tab Tooltips

**Market Health Banner:**
- "Confirmed Uptrend" — The overall market is healthy and trending higher. This is the best environment for buying breakouts.
- "Uptrend Under Pressure" — The market is still in an uptrend but showing signs of stress. Be more selective with new buys.
- "In Correction" — The market is in a downtrend. Most breakouts fail in corrections — avoid new buys until the market confirms a new uptrend.
- "Distribution Days" — Days where the S&P 500 drops more than 0.2% on higher volume than the previous day. Too many (4-5) in a short period signals institutional selling and can trigger a market correction.

**Controls:**
- "Min Score" — Filters results to only show patterns with a confidence score at or above this value. The score (0-100) measures how closely a pattern matches the ideal textbook formation. Higher = more reliable.

**Stat Cards:**
- "Total Found" — How many base patterns the scan detected across all stocks in the watchlist.
- "At Pivot" — Stocks where the current price is within 1% of the buy point. These are actionable now — ready to buy if volume confirms.
- "Near Pivot" — Stocks within 1-5% below the buy point. Keep these on your watch list — they could reach the buy point soon.
- "High Quality" — Patterns scoring 75 or above out of 100. These most closely match the ideal formation and have the best historical success rate.

**Results Table Column Headers:**
- "Ticker" — The stock's ticker symbol (e.g., AAPL = Apple Inc.).
- "Pattern" — The type of base pattern detected. Each pattern has a different shape and characteristics, but all represent a period of consolidation before a potential move higher.
- "Score" — Confidence score from 0-100 measuring how closely this pattern matches the ideal formation. Based on depth, volume, trend strength, relative strength, and other factors. 75+ is high quality.
- "Status" — Where the stock is relative to its buy point. "At Pivot" means ready to buy. "Near Pivot" means it's close. "Building" means the pattern is still forming. "Extended" means it's already moved too far past the buy point.
- "Buy Point" — The price level where the pattern completes and a breakout occurs. This is the ideal entry price. For Cup & Handle patterns, it's the top of the cup (the "lip"). For Double Bottoms, it's the middle peak of the W.
- "Price" — The stock's most recent closing price.
- "Dist %" — How far the current price is from the buy point, as a percentage. Negative means below (still building), near zero means at the buy point, positive means it's already broken out.
- "Depth %" — How far the stock pulled back from its peak to form the base. Shallower bases (12-20%) are generally stronger. Deeper bases (33-50%) form in volatile markets and are riskier.
- "Weeks" — How long the base has been forming. Longer bases (7+ weeks) are generally more reliable because they show sustained institutional accumulation.
- "RS" — Relative Strength rating (1-99) comparing this stock's price performance to the S&P 500. Scores above 80 mean the stock is outperforming most of the market — that's what you want. Below 50 means it's lagging.
- "Vol Rating" — Volume accumulation/distribution grade (A through E). A = strong institutional buying. E = heavy institutional selling. Look for A or B ratings — they show big money is flowing into the stock.
- "Stop Loss" — Suggested price to sell if the trade goes against you. Set at 7% below the buy point by default. Always use a stop loss to protect your capital — small losses are recoverable, large losses are not.
- "Target" — Suggested profit target price. Set at 20% above the buy point by default. Consider taking at least partial profits when the stock reaches this level.
- "Vol" — Whether volume confirmed the pattern. A checkmark means trading volume supported the breakout (volume surged 40%+ above average). This is critical — breakouts without volume often fail.
- "50MA" — Whether the stock is trading above its 50-day moving average. The 50MA acts as a support level in healthy uptrends. Stocks below their 50MA are showing short-term weakness.
- "200MA" — Whether the stock is trading above its 200-day moving average. The 200MA represents the long-term trend. Stocks below it are in a long-term downtrend — avoid buying these.

**Pattern Badges:**
- "Cup & Handle" — A U-shaped consolidation pattern (the "cup") followed by a small pullback (the "handle"). The buy point is at the top of the cup. Ideal depth: 12-33%, duration: 7-65 weeks.
- "Deep Cup & Handle" — Same as Cup & Handle but with a deeper pullback (33-50%). These form in volatile or bear markets and carry more risk, but can produce large gains.
- "Double Bottom" — A W-shaped pattern with two distinct lows near the same price level. The buy point is at the middle peak of the W. Shows the stock found strong support at that price twice.
- "Flat Base" — A tight sideways consolidation where the stock trades in a narrow range (less than 15% from high to low). Usually forms after a prior advance. Shows the stock is being quietly accumulated by institutions.

**Status Badges:**
- "At Pivot" — The stock is right at its buy point (within 1%). If volume is strong, this could be a buying opportunity.
- "Near Pivot" — The stock is 1-5% below its buy point. Add it to your watch list and wait for it to reach the buy point with volume.
- "Building" — The pattern is still forming (more than 5% below the buy point). Too early to buy — check back later.
- "Extended" — The stock has moved more than 5% past its buy point. It's too late for an ideal entry — buying here increases risk of a pullback.
- "Breakout Confirmed" — The stock broke above the buy point with strong volume confirmation. The breakout is real.
- "Failed Breakout" — The stock moved above the buy point but fell back below. The breakout didn't hold — avoid or sell.

### Backtest Tab Tooltips

**Controls:**
- "Stop Loss %" — If a trade drops this percentage from your entry price, sell automatically to limit losses. 7% is the classic CAN SLIM rule — it keeps any single loss manageable.
- "Profit Target %" — If a trade gains this percentage from your entry price, sell to lock in profits. 20% is a common target, giving you roughly a 3:1 reward-to-risk ratio with a 7% stop.
- "Min Confidence" — Only test pattern signals with a confidence score at or above this value. Lower values include more signals (more trades, possibly lower quality). Higher values are more selective.

**Summary Metrics:**
- "Total Trades" — The number of trades the backtest would have taken based on your settings. More trades give more statistically reliable results.
- "Win Rate" — The percentage of trades that were profitable. Above 50% is good, but even strategies with 40% win rate can be profitable if the average win is much larger than the average loss.
- "Profit Factor" — Total profits divided by total losses. Above 1.0 means the strategy is profitable overall. Above 2.0 is very strong. Below 1.0 means losses exceeded profits.
- "Avg Return" — The average percentage return across all trades (wins and losses combined). This is your expected return per trade.
- "Expectancy" — The expected profit per trade in percentage terms, accounting for both win rate and win/loss sizes. Positive means the strategy makes money over time. Higher is better.

**Breakdown Cards:**
- "By Pattern Type" — Shows how each pattern performed independently. Some patterns may work better than others in certain market conditions.
- "By Confidence Band" — Shows how performance varies by signal quality. Higher confidence bands should ideally have better win rates — if they don't, the scoring model may need adjustment.
- "By Market Regime" — Shows how the strategy performed in different market conditions (uptrend vs correction). Most pattern strategies work best in confirmed uptrends.
- "Win/Loss Summary" — Compares average winning trade size vs average losing trade size. For a healthy strategy, your average win should be at least 2-3x your average loss.

**Trade Log Columns:**
- "Detected" — The date the pattern was first identified by the scanner.
- "Entry" — The date a trade would have been opened (when price hit the buy point).
- "Entry $" — The price at which the trade was entered.
- "Exit" — The date the trade was closed.
- "Exit $" — The price at which the trade was exited.
- "Reason" — Why the trade was closed. "Target" (green) = hit profit target. "Stop" (red) = hit stop loss. "Open" (gray) = trade is still active at the end of the test period.
- "P&L %" — Profit or loss as a percentage. Green = profitable, red = loss.
- "Regime" — The market regime at the time of entry. Helps you see whether the trade was taken in favorable conditions.

---

## 2. Help Panel (Slide-in Drawer)

### Trigger
A "?" button fixed in the top-right area of the header bar. Clicking opens a panel that slides in from the right edge (~400px wide on desktop, full-width on mobile). A semi-transparent backdrop covers the main content.

### Panel Behavior
- Scrolls independently from the main content
- Closes on: close button (×), clicking backdrop, pressing Escape
- Persists across tab switches (Scanner/Backtest)
- No localStorage tracking — always available fresh

### Panel Sections

**1. Quick Start**
Title: "What is this app?"
Content: Explains that the scanner finds stocks forming base patterns — specific price consolidation shapes that often precede major price moves. Based on the CAN SLIM methodology developed by William O'Neil in "How to Make Money in Stocks." The app scans stocks, scores patterns by quality, and shows you which ones are closest to a buy point.

**2. How to Use the Scanner**
Step-by-step walkthrough:
1. Pick a watchlist (Growth for curated picks, S&P 500 or NASDAQ 100 for broader scans)
2. Set a minimum score (start with 50+ to see quality patterns)
3. Click Scan and wait for results
4. Focus on "At Pivot" and "Near Pivot" stocks with scores of 75+
5. Check that RS is 80+, Vol Rating is A or B, and the stock is above its 50MA and 200MA
6. Use the buy point as your entry price, set a stop loss 7% below

**3. Pattern Guide**
Each of the 4 patterns gets:
- SVG illustration (see Section 3 below)
- 2-3 sentence description
- Key parameters (ideal depth, duration)
- "What to look for" actionable tip

**4. Understanding the Backtest**
Explains what backtesting is (replaying historical data to test strategy performance), how to interpret the metrics, and how to use the breakdowns to refine your approach. Warns that past performance doesn't guarantee future results.

**5. Glossary**
Alphabetical list of all technical terms used in the app with 1-2 sentence plain-language definitions:
- Accumulation/Distribution
- Base Pattern
- Buy Point / Pivot
- CAN SLIM
- Confidence Score
- Cup & Handle / Deep Cup & Handle / Double Bottom / Flat Base
- Depth
- Distribution Day
- Expectancy
- Failed Breakout
- Market Regime
- Moving Average (50-day, 200-day)
- Profit Factor
- Relative Strength (RS)
- Stop Loss
- Tightness
- Volume Confirmation
- Volume Rating
- Win Rate

---

## 3. SVG Pattern Illustrations

Four inline SVG diagrams (~300×150px each), embedded directly in the help panel HTML.

### Style
- Price line: `#58a6ff` (blue accent), 2px stroke
- Buy point line: `#3fb950` (green), 1px dashed horizontal
- Annotation labels: `#8b949e` (secondary gray), 11px font
- Background: transparent (inherits panel dark background)
- No animation or interactivity

### Diagrams

**Cup & Handle:**
Smooth U-shaped curve rising to a lip, small dip (handle), then price crossing above the lip. Labels: "Prior Uptrend" (left), "Cup (12-33% deep)" (bottom center), "Handle" (right dip), "Buy Point" (green dashed line at lip level).

**Deep Cup & Handle:**
Same shape but visibly deeper U. Labels: "Cup (33-50% deep)" (bottom center), "Handle" (right dip), "Buy Point" (green dashed line). Annotation: "Forms in volatile markets."

**Double Bottom:**
W-shape with two distinct lows at roughly the same level. Labels: "First Low" (left bottom), "Second Low" (right bottom), "Middle Peak" (center top), "Buy Point" (green dashed line at middle peak level).

**Flat Base:**
Rising line that transitions into a tight horizontal channel. Labels: "Prior Uptrend" (left rise), "Tight Range (<15%)" (horizontal section), "Buy Point" (green dashed line at top of range).

---

## 4. Implementation Scope

### Files Modified
- `stock_pattern_scanner/templates/dashboard.html` — the only file changed

### What's Added
- CSS: tooltip styles, help panel styles, SVG styles (~150 lines)
- HTML: ~50 tooltip `ⓘ` icons with popover content throughout both tabs
- HTML: help panel section with all content and 4 SVG diagrams (~200 lines)
- JS: panel open/close/escape logic (~30 lines)

### What's NOT Changed
- No Python backend changes
- No new API endpoints
- No new dependencies
- No new files
- No changes to existing functionality

### Testing
- All existing pytest tests pass (no backend changes)
- Manual verification: tooltips render without overlap, panel opens/closes, SVGs display correctly, mobile-friendly behavior
