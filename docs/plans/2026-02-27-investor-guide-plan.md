# Investor Guide & Tooltips Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add contextual tooltips and a slide-in help panel with SVG pattern illustrations to make the dashboard fully understandable for beginner investors.

**Architecture:** All changes are in the single HTML template file. CSS-only tooltips via `ⓘ` icons, a slide-in drawer panel toggled by a header button, and four inline SVG pattern diagrams. No backend changes, no new dependencies.

**Tech Stack:** HTML, CSS, JavaScript (all inline in existing template)

---

## Task 1: Add Tooltip CSS and Base Infrastructure

**Files:**
- Modify: `stock_pattern_scanner/templates/dashboard.html:7-413` (style block)

**Step 1: Add tooltip CSS to the style block**

Insert the following CSS just before the closing `</style>` tag (before line 413):

```css
/* Tooltips */
.tooltip-trigger {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 16px;
    height: 16px;
    border-radius: 50%;
    background: rgba(88, 166, 255, 0.15);
    color: var(--accent);
    font-size: 10px;
    font-weight: 700;
    cursor: help;
    position: relative;
    margin-left: 4px;
    vertical-align: middle;
    flex-shrink: 0;
}
.tooltip-trigger:hover { background: rgba(88, 166, 255, 0.3); }
.tooltip-trigger .tooltip-text {
    display: none;
    position: absolute;
    bottom: calc(100% + 8px);
    left: 50%;
    transform: translateX(-50%);
    background: var(--bg-tertiary);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 10px 14px;
    font-size: 12px;
    font-weight: 400;
    line-height: 1.5;
    color: var(--text-primary);
    width: 280px;
    text-transform: none;
    letter-spacing: normal;
    white-space: normal;
    z-index: 100;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.4);
    pointer-events: none;
}
.tooltip-trigger .tooltip-text::after {
    content: '';
    position: absolute;
    top: 100%;
    left: 50%;
    transform: translateX(-50%);
    border: 6px solid transparent;
    border-top-color: var(--border);
}
.tooltip-trigger:hover .tooltip-text,
.tooltip-trigger:focus .tooltip-text {
    display: block;
}
/* Prevent tooltips from going off-screen on the left/right */
.tooltip-trigger .tooltip-text.tooltip-right {
    left: 0;
    transform: none;
}
.tooltip-trigger .tooltip-text.tooltip-right::after {
    left: 12px;
    transform: none;
}
.tooltip-trigger .tooltip-text.tooltip-left {
    left: auto;
    right: 0;
    transform: none;
}
.tooltip-trigger .tooltip-text.tooltip-left::after {
    left: auto;
    right: 12px;
    transform: none;
}
/* Inline tooltip within table headers — needs to sit next to text */
thead th .tooltip-trigger {
    display: inline-flex;
    vertical-align: middle;
}
```

**Step 2: Add responsive tooltip rule**

Add inside the existing `@media (max-width: 768px)` block (around line 406-412):

```css
.tooltip-trigger .tooltip-text { width: 220px; }
```

**Step 3: Verify app starts cleanly**

Run: `cd stock_pattern_scanner && python -c "from app import app; print('OK')"`
Expected: `OK`

**Step 4: Commit**

```bash
git add stock_pattern_scanner/templates/dashboard.html
git commit -m "feat(guide): add tooltip CSS infrastructure"
```

---

## Task 2: Add Tooltips to Scanner Tab Controls and Stats

**Files:**
- Modify: `stock_pattern_scanner/templates/dashboard.html:428-549` (scanner tab HTML)

**Step 1: Add tooltip to market banner via JavaScript**

In the `fetchMarketStatus()` function (around line 957-980), modify the three status branches to append a tooltip after the text. Replace the `banner.textContent = ...` lines:

For confirmed uptrend (line 964), replace:
```javascript
banner.textContent = 'Market: Confirmed Uptrend \u2014 ' + data.distribution_days + ' distribution days';
```
with:
```javascript
banner.innerHTML = 'Market: Confirmed Uptrend \u2014 ' + data.distribution_days + ' distribution days <span class="tooltip-trigger" tabindex="0">i<span class="tooltip-text tooltip-left">The overall market is healthy and trending higher. This is the best environment for buying breakouts. Distribution days are days where the S&P 500 drops more than 0.2% on above-average volume \u2014 too many signal institutional selling.</span></span>';
```

For uptrend under pressure (line 967), replace:
```javascript
banner.textContent = 'Market: Uptrend Under Pressure \u2014 ' + data.distribution_days + ' distribution days';
```
with:
```javascript
banner.innerHTML = 'Market: Uptrend Under Pressure \u2014 ' + data.distribution_days + ' distribution days <span class="tooltip-trigger" tabindex="0">i<span class="tooltip-text tooltip-left">The market is still in an uptrend but showing signs of stress from institutional selling. Be more selective with new buys and keep positions smaller.</span></span>';
```

For correction (line 970), replace:
```javascript
banner.textContent = 'Market: In Correction \u2014 Buy signals disabled';
```
with:
```javascript
banner.innerHTML = 'Market: In Correction \u2014 Buy signals disabled <span class="tooltip-trigger" tabindex="0">i<span class="tooltip-text tooltip-left">The market is in a downtrend. Most breakouts fail during corrections \u2014 avoid new buys until the market confirms a new uptrend.</span></span>';
```

**Step 2: Add tooltip to Min Score label**

Replace line 450 (`<label>Min Score</label>`) with:
```html
<label>Min Score <span class="tooltip-trigger" tabindex="0">i<span class="tooltip-text">Filters results to only show patterns with a confidence score at or above this value. The score (0-100) measures how closely a pattern matches the ideal textbook formation. Higher scores are more reliable.</span></span></label>
```

**Step 3: Add tooltips to stat cards**

Replace the stat labels (lines 479, 483, 487, 491) with:

```html
<div class="stat-label">Total Found <span class="tooltip-trigger" tabindex="0">i<span class="tooltip-text">How many base patterns the scan detected across all stocks in the watchlist.</span></span></div>
```

```html
<div class="stat-label">At Pivot <span class="tooltip-trigger" tabindex="0">i<span class="tooltip-text">Stocks where the current price is within 1% of the buy point. These are actionable now \u2014 ready to buy if volume confirms the breakout.</span></span></div>
```

```html
<div class="stat-label">Near Pivot <span class="tooltip-trigger" tabindex="0">i<span class="tooltip-text">Stocks within 1-5% below the buy point. Keep these on your watch list \u2014 they could reach the buy point soon.</span></span></div>
```

```html
<div class="stat-label">High Quality <span class="tooltip-trigger" tabindex="0">i<span class="tooltip-text">Patterns scoring 75 or above out of 100. These most closely match the ideal formation and have the best historical success rate.</span></span></div>
```

**Step 4: Verify app starts**

Run: `cd stock_pattern_scanner && python -c "from app import app; print('OK')"`
Expected: `OK`

**Step 5: Commit**

```bash
git add stock_pattern_scanner/templates/dashboard.html
git commit -m "feat(guide): add tooltips to scanner controls and stat cards"
```

---

## Task 3: Add Tooltips to Scanner Results Table Headers

**Files:**
- Modify: `stock_pattern_scanner/templates/dashboard.html:521-540` (table head)

**Step 1: Replace all 16 table header cells with tooltip-enhanced versions**

Replace the entire `<tr id="table-head">` block (lines 522-539) with:

```html
<tr id="table-head">
    <th data-col="ticker">Ticker <span class="sort-arrow">&#9650;</span></th>
    <th data-col="pattern_type">Pattern <span class="tooltip-trigger" tabindex="0">i<span class="tooltip-text">The type of base pattern detected. Each represents a period of price consolidation before a potential move higher.</span></span> <span class="sort-arrow">&#9650;</span></th>
    <th data-col="confidence_score" class="sorted">Score <span class="tooltip-trigger" tabindex="0">i<span class="tooltip-text">Confidence score (0-100) measuring how closely this pattern matches the ideal formation. Based on depth, volume, trend strength, and relative strength. 75+ is high quality.</span></span> <span class="sort-arrow">&#9660;</span></th>
    <th data-col="status">Status <span class="tooltip-trigger" tabindex="0">i<span class="tooltip-text">Where the stock is relative to its buy point. "At Pivot" = ready to buy. "Near Pivot" = close, watch it. "Building" = still forming. "Extended" = moved too far past the buy point.</span></span> <span class="sort-arrow">&#9650;</span></th>
    <th data-col="buy_point">Buy Point <span class="tooltip-trigger" tabindex="0">i<span class="tooltip-text tooltip-left">The price where the pattern completes and a breakout occurs. This is the ideal entry price \u2014 buy when the stock crosses this level with strong volume.</span></span> <span class="sort-arrow">&#9650;</span></th>
    <th data-col="current_price">Price <span class="sort-arrow">&#9650;</span></th>
    <th data-col="distance_to_pivot">Dist % <span class="tooltip-trigger" tabindex="0">i<span class="tooltip-text tooltip-left">How far the current price is from the buy point. Negative = still below (building). Near zero = at the buy point. Positive = already broken out.</span></span> <span class="sort-arrow">&#9650;</span></th>
    <th data-col="base_depth">Depth % <span class="tooltip-trigger" tabindex="0">i<span class="tooltip-text tooltip-left">How far the stock pulled back from its peak to form the base. Shallower bases (12-20%) are generally stronger. Deeper bases (33-50%) are riskier.</span></span> <span class="sort-arrow">&#9650;</span></th>
    <th data-col="base_length_weeks">Weeks <span class="tooltip-trigger" tabindex="0">i<span class="tooltip-text tooltip-left">How long the base has been forming. Longer bases (7+ weeks) are generally more reliable because they represent sustained institutional accumulation.</span></span> <span class="sort-arrow">&#9650;</span></th>
    <th data-col="rs_rating">RS <span class="tooltip-trigger" tabindex="0">i<span class="tooltip-text tooltip-left">Relative Strength (1-99) \u2014 how this stock performs vs. the S&P 500. Above 80 = outperforming most stocks (good). Below 50 = lagging the market (avoid).</span></span> <span class="sort-arrow">&#9650;</span></th>
    <th data-col="volume_rating">Vol Rating <span class="tooltip-trigger" tabindex="0">i<span class="tooltip-text tooltip-left">Volume accumulation/distribution grade (A through E). A = strong institutional buying. E = heavy selling. Look for A or B \u2014 they show big money flowing in.</span></span> <span class="sort-arrow">&#9650;</span></th>
    <th data-col="stop_loss_price">Stop Loss <span class="tooltip-trigger" tabindex="0">i<span class="tooltip-text tooltip-left">Suggested sell price if the trade goes against you (7% below buy point). Always use a stop loss \u2014 small losses are recoverable, large ones are not.</span></span> <span class="sort-arrow">&#9650;</span></th>
    <th data-col="profit_target_price">Target <span class="tooltip-trigger" tabindex="0">i<span class="tooltip-text tooltip-left">Suggested profit target (20% above buy point). Consider taking at least partial profits when the stock reaches this level.</span></span> <span class="sort-arrow">&#9650;</span></th>
    <th data-col="volume_confirmation">Vol <span class="tooltip-trigger" tabindex="0">i<span class="tooltip-text tooltip-left">Whether trading volume confirmed the breakout (40%+ surge above average). Breakouts without volume confirmation often fail.</span></span> <span class="sort-arrow">&#9650;</span></th>
    <th data-col="above_50ma">50MA <span class="tooltip-trigger" tabindex="0">i<span class="tooltip-text tooltip-left">Is the stock above its 50-day moving average? The 50MA acts as support in healthy uptrends. Stocks below it show short-term weakness.</span></span> <span class="sort-arrow">&#9650;</span></th>
    <th data-col="above_200ma">200MA <span class="tooltip-trigger" tabindex="0">i<span class="tooltip-text tooltip-left">Is the stock above its 200-day moving average? The 200MA represents the long-term trend. Stocks below it are in a long-term downtrend \u2014 avoid.</span></span> <span class="sort-arrow">&#9650;</span></th>
</tr>
```

**Step 2: Verify app starts**

Run: `cd stock_pattern_scanner && python -c "from app import app; print('OK')"`
Expected: `OK`

**Step 3: Commit**

```bash
git add stock_pattern_scanner/templates/dashboard.html
git commit -m "feat(guide): add tooltips to scanner table headers"
```

---

## Task 4: Add Tooltips to Backtest Tab

**Files:**
- Modify: `stock_pattern_scanner/templates/dashboard.html:552-660` (backtest tab HTML)

**Step 1: Add tooltips to backtest control labels**

Replace the backtest Stop Loss label (line 570):
```html
<label>Stop Loss % <span class="tooltip-trigger" tabindex="0">i<span class="tooltip-text">If a trade drops this percentage from your entry price, sell to limit losses. 7% is the classic CAN SLIM rule \u2014 keeps any single loss manageable.</span></span></label>
```

Replace the Profit Target label (line 573):
```html
<label>Profit Target % <span class="tooltip-trigger" tabindex="0">i<span class="tooltip-text">If a trade gains this percentage, sell to lock in profits. 20% gives roughly a 3:1 reward-to-risk ratio with a 7% stop loss.</span></span></label>
```

Replace the Min Confidence label (line 578):
```html
<label>Min Confidence <span class="tooltip-trigger" tabindex="0">i<span class="tooltip-text">Only test pattern signals at or above this confidence score. Lower values include more trades (possibly lower quality). Higher values are more selective.</span></span></label>
```

**Step 2: Add tooltips to backtest metric labels**

Replace the five `<div class="stat-label">` elements inside `bt-metrics` (lines 603, 607, 611, 615, 619):

```html
<div class="stat-label">Total Trades <span class="tooltip-trigger" tabindex="0">i<span class="tooltip-text">Number of trades the backtest would have taken. More trades give more statistically reliable results.</span></span></div>
```

```html
<div class="stat-label">Win Rate <span class="tooltip-trigger" tabindex="0">i<span class="tooltip-text">Percentage of trades that were profitable. Above 50% is good, but even 40% win rates can be profitable if average wins are much larger than average losses.</span></span></div>
```

```html
<div class="stat-label">Profit Factor <span class="tooltip-trigger" tabindex="0">i<span class="tooltip-text">Total profits divided by total losses. Above 1.0 = profitable overall. Above 2.0 = very strong. Below 1.0 = losses exceeded profits.</span></span></div>
```

```html
<div class="stat-label">Avg Return <span class="tooltip-trigger" tabindex="0">i<span class="tooltip-text">Average percentage return across all trades (wins and losses combined). This is your expected return per trade.</span></span></div>
```

```html
<div class="stat-label">Expectancy <span class="tooltip-trigger" tabindex="0">i<span class="tooltip-text">Expected profit per trade accounting for both win rate and win/loss sizes. Positive = strategy makes money over time. Higher is better.</span></span></div>
```

**Step 3: Add tooltips to breakdown card headers**

Replace the four `<h3>` elements inside `bt-breakdowns` (lines 626, 630, 634, 638):

```html
<h3>By Pattern Type <span class="tooltip-trigger" tabindex="0">i<span class="tooltip-text">Shows how each pattern performed independently. Some patterns work better than others in certain market conditions.</span></span></h3>
```

```html
<h3>By Confidence Band <span class="tooltip-trigger" tabindex="0">i<span class="tooltip-text">Shows performance by signal quality. Higher confidence bands should have better win rates \u2014 if they don't, the scoring needs adjustment.</span></span></h3>
```

```html
<h3>By Market Regime <span class="tooltip-trigger" tabindex="0">i<span class="tooltip-text">Shows strategy performance in different market conditions. Most pattern strategies work best in confirmed uptrends and poorly in corrections.</span></span></h3>
```

```html
<h3>Win/Loss Summary <span class="tooltip-trigger" tabindex="0">i<span class="tooltip-text">Compares average winning vs. losing trade sizes. A healthy strategy has average wins at least 2-3x larger than average losses.</span></span></h3>
```

**Step 4: Verify app starts**

Run: `cd stock_pattern_scanner && python -c "from app import app; print('OK')"`
Expected: `OK`

**Step 5: Commit**

```bash
git add stock_pattern_scanner/templates/dashboard.html
git commit -m "feat(guide): add tooltips to backtest tab"
```

---

## Task 5: Add Help Panel HTML and CSS

**Files:**
- Modify: `stock_pattern_scanner/templates/dashboard.html`

**Step 1: Add help panel CSS**

Insert the following CSS just before the closing `</style>` tag, after the tooltip CSS added in Task 1:

```css
/* Help panel */
.help-btn {
    background: rgba(88, 166, 255, 0.15);
    border: 1px solid rgba(88, 166, 255, 0.3);
    color: var(--accent);
    width: 32px;
    height: 32px;
    border-radius: 50%;
    font-size: 16px;
    font-weight: 700;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    transition: background 0.15s;
}
.help-btn:hover { background: rgba(88, 166, 255, 0.3); }

.help-backdrop {
    display: none;
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.5);
    z-index: 999;
}
.help-backdrop.open { display: block; }

.help-panel {
    position: fixed;
    top: 0;
    right: -420px;
    width: 400px;
    height: 100vh;
    background: var(--bg-secondary);
    border-left: 1px solid var(--border);
    z-index: 1000;
    overflow-y: auto;
    transition: right 0.25s ease;
    padding: 24px;
}
.help-panel.open { right: 0; }

.help-panel-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 24px;
    padding-bottom: 16px;
    border-bottom: 1px solid var(--border);
}
.help-panel-header h2 {
    font-size: 18px;
    font-weight: 600;
    color: var(--text-primary);
}
.help-close-btn {
    background: transparent;
    border: none;
    color: var(--text-secondary);
    font-size: 24px;
    cursor: pointer;
    padding: 4px;
    line-height: 1;
}
.help-close-btn:hover { color: var(--text-primary); }

.help-section { margin-bottom: 28px; }
.help-section h3 {
    font-size: 14px;
    font-weight: 600;
    color: var(--accent);
    margin-bottom: 10px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}
.help-section p {
    font-size: 13px;
    line-height: 1.6;
    color: var(--text-secondary);
    margin-bottom: 10px;
}
.help-section ol, .help-section ul {
    font-size: 13px;
    line-height: 1.6;
    color: var(--text-secondary);
    padding-left: 20px;
    margin-bottom: 10px;
}
.help-section li { margin-bottom: 6px; }
.help-section strong { color: var(--text-primary); }

.help-pattern-card {
    background: var(--bg-tertiary);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 16px;
    margin-bottom: 12px;
}
.help-pattern-card h4 {
    font-size: 13px;
    font-weight: 600;
    color: var(--text-primary);
    margin-bottom: 8px;
}
.help-pattern-card p {
    font-size: 12px;
    line-height: 1.5;
    color: var(--text-secondary);
    margin-bottom: 8px;
}
.help-pattern-card .pattern-params {
    font-size: 11px;
    color: var(--text-muted);
}
.help-pattern-card svg {
    display: block;
    margin: 8px auto;
}

.glossary-term {
    padding: 8px 0;
    border-bottom: 1px solid var(--border);
}
.glossary-term:last-child { border-bottom: none; }
.glossary-term dt {
    font-size: 13px;
    font-weight: 600;
    color: var(--text-primary);
    margin-bottom: 2px;
}
.glossary-term dd {
    font-size: 12px;
    color: var(--text-secondary);
    line-height: 1.5;
}
```

Add to the `@media (max-width: 768px)` block:

```css
.help-panel { width: 100%; right: -100%; }
```

**Step 2: Add help button to the header**

Replace the header div (line 417-424). Change:
```html
<div class="header">
    <h1><span>&#9632;</span> Stock Pattern Scanner</h1>
    <div class="header-tabs">
        <button class="tab-btn active" onclick="switchTab('scanner')">Scanner</button>
        <button class="tab-btn" onclick="switchTab('backtest')">Backtest</button>
    </div>
    <div class="header-right">CAN SLIM Base Pattern Detection</div>
</div>
```
to:
```html
<div class="header">
    <h1><span>&#9632;</span> Stock Pattern Scanner</h1>
    <div class="header-tabs">
        <button class="tab-btn active" onclick="switchTab('scanner')">Scanner</button>
        <button class="tab-btn" onclick="switchTab('backtest')">Backtest</button>
    </div>
    <div style="display:flex;align-items:center;gap:12px;">
        <div class="header-right">CAN SLIM Base Pattern Detection</div>
        <button class="help-btn" onclick="toggleHelpPanel()" title="Investor Guide">?</button>
    </div>
</div>
```

**Step 3: Add help panel HTML before closing `</body>` tag**

Insert just before `<script>` (before line 663):

```html
<!-- Help Panel Backdrop -->
<div class="help-backdrop" id="helpBackdrop" onclick="toggleHelpPanel()"></div>

<!-- Help Panel -->
<div class="help-panel" id="helpPanel">
    <div class="help-panel-header">
        <h2>Investor Guide</h2>
        <button class="help-close-btn" onclick="toggleHelpPanel()">&times;</button>
    </div>

    <!-- Quick Start -->
    <div class="help-section">
        <h3>What Is This App?</h3>
        <p>This scanner finds stocks forming <strong>base patterns</strong> — specific price consolidation shapes that often come before major price moves. It's based on the <strong>CAN SLIM</strong> methodology developed by William O'Neil in <em>How to Make Money in Stocks</em>.</p>
        <p>The app scans stocks, scores how closely each pattern matches the ideal textbook formation, and shows you which ones are closest to a <strong>buy point</strong> — the price level where a breakout is expected.</p>
    </div>

    <!-- How to Use -->
    <div class="help-section">
        <h3>How to Use the Scanner</h3>
        <ol>
            <li><strong>Pick a watchlist</strong> — Growth for curated picks, S&P 500 or NASDAQ 100 for broader scans</li>
            <li><strong>Set a minimum score</strong> — start with 50+ to see quality patterns</li>
            <li><strong>Click Scan</strong> and wait for results</li>
            <li><strong>Focus on "At Pivot" and "Near Pivot"</strong> stocks with scores of 75+</li>
            <li><strong>Check quality filters</strong> — RS above 80, Vol Rating A or B, above both 50MA and 200MA</li>
            <li><strong>Use the buy point</strong> as your entry price, set a stop loss 7% below</li>
        </ol>
    </div>

    <!-- Pattern Guide -->
    <div class="help-section">
        <h3>Pattern Guide</h3>

        <div class="help-pattern-card">
            <h4 style="color:var(--badge-cup);">Cup & Handle</h4>
            <svg width="300" height="130" viewBox="0 0 300 130">
                <!-- Prior uptrend -->
                <path d="M10,100 L40,60 L70,35" fill="none" stroke="#58a6ff" stroke-width="2"/>
                <!-- Cup -->
                <path d="M70,35 Q80,38 95,70 Q120,110 150,110 Q180,110 205,70 Q220,38 230,35" fill="none" stroke="#58a6ff" stroke-width="2"/>
                <!-- Handle dip -->
                <path d="M230,35 Q240,38 248,50 Q255,42 265,35" fill="none" stroke="#58a6ff" stroke-width="2"/>
                <!-- Breakout -->
                <path d="M265,35 L290,20" fill="none" stroke="#58a6ff" stroke-width="2" stroke-dasharray="4,3"/>
                <!-- Buy point line -->
                <line x1="65" y1="35" x2="290" y2="35" stroke="#3fb950" stroke-width="1" stroke-dasharray="4,3"/>
                <!-- Labels -->
                <text x="15" y="118" fill="#8b949e" font-size="10">Prior Uptrend</text>
                <text x="120" y="100" fill="#8b949e" font-size="10" text-anchor="middle">Cup (12-33% deep)</text>
                <text x="248" y="60" fill="#8b949e" font-size="10">Handle</text>
                <text x="272" y="30" fill="#3fb950" font-size="10">Buy Point</text>
            </svg>
            <p>A U-shaped consolidation (the "cup") followed by a small pullback (the "handle"). The buy point is at the top of the cup. This is the most common and reliable pattern.</p>
            <div class="pattern-params">Ideal depth: 12-33% | Duration: 7-65 weeks | Look for volume dry-up in the handle</div>
        </div>

        <div class="help-pattern-card">
            <h4 style="color:var(--badge-deep-cup);">Deep Cup & Handle</h4>
            <svg width="300" height="140" viewBox="0 0 300 140">
                <!-- Prior uptrend -->
                <path d="M10,90 L40,50 L70,25" fill="none" stroke="#bc8cff" stroke-width="2"/>
                <!-- Deep cup -->
                <path d="M70,25 Q80,30 95,75 Q120,130 150,130 Q180,130 205,75 Q220,30 230,25" fill="none" stroke="#bc8cff" stroke-width="2"/>
                <!-- Handle -->
                <path d="M230,25 Q240,30 248,42 Q255,34 265,25" fill="none" stroke="#bc8cff" stroke-width="2"/>
                <!-- Breakout -->
                <path d="M265,25 L290,12" fill="none" stroke="#bc8cff" stroke-width="2" stroke-dasharray="4,3"/>
                <!-- Buy point line -->
                <line x1="65" y1="25" x2="290" y2="25" stroke="#3fb950" stroke-width="1" stroke-dasharray="4,3"/>
                <!-- Labels -->
                <text x="120" y="118" fill="#8b949e" font-size="10" text-anchor="middle">Cup (33-50% deep)</text>
                <text x="248" y="52" fill="#8b949e" font-size="10">Handle</text>
                <text x="272" y="20" fill="#3fb950" font-size="10">Buy Point</text>
                <text x="100" y="13" fill="#8b949e" font-size="9" font-style="italic">Forms in volatile markets</text>
            </svg>
            <p>Same shape as Cup & Handle but with a deeper pullback (33-50%). These form in volatile or bear markets and carry more risk, but can produce large gains when they work.</p>
            <div class="pattern-params">Depth: 33-50% | Duration: 7-65 weeks | Higher risk, higher reward</div>
        </div>

        <div class="help-pattern-card">
            <h4 style="color:var(--badge-double-bottom);">Double Bottom</h4>
            <svg width="300" height="130" viewBox="0 0 300 130">
                <!-- Prior uptrend -->
                <path d="M10,90 L30,55 L50,30" fill="none" stroke="#3fb950" stroke-width="2"/>
                <!-- First dip -->
                <path d="M50,30 Q70,40 85,95 Q95,100 105,95" fill="none" stroke="#3fb950" stroke-width="2"/>
                <!-- Middle peak -->
                <path d="M105,95 Q130,40 155,30" fill="none" stroke="#3fb950" stroke-width="2"/>
                <!-- Second dip -->
                <path d="M155,30 Q175,40 190,95 Q200,100 210,95" fill="none" stroke="#3fb950" stroke-width="2"/>
                <!-- Recovery and breakout -->
                <path d="M210,95 Q235,40 255,30" fill="none" stroke="#3fb950" stroke-width="2"/>
                <path d="M255,30 L280,15" fill="none" stroke="#3fb950" stroke-width="2" stroke-dasharray="4,3"/>
                <!-- Buy point line at middle peak -->
                <line x1="45" y1="30" x2="290" y2="30" stroke="#3fb950" stroke-width="1" stroke-dasharray="4,3"/>
                <!-- Labels -->
                <text x="85" y="118" fill="#8b949e" font-size="10" text-anchor="middle">First Low</text>
                <text x="195" y="118" fill="#8b949e" font-size="10" text-anchor="middle">Second Low</text>
                <text x="155" y="22" fill="#8b949e" font-size="10" text-anchor="middle">Middle Peak</text>
                <text x="262" y="25" fill="#3fb950" font-size="10">Buy Point</text>
            </svg>
            <p>A W-shaped pattern with two distinct lows near the same price level. The buy point is at the middle peak of the W. Shows the stock found strong price support twice — a bullish signal.</p>
            <div class="pattern-params">Depth: 15-40% | Two lows within 5% of each other | Buy at the middle peak</div>
        </div>

        <div class="help-pattern-card">
            <h4 style="color:var(--badge-flat-base);">Flat Base</h4>
            <svg width="300" height="120" viewBox="0 0 300 120">
                <!-- Prior uptrend -->
                <path d="M10,100 L30,75 L60,50 L90,35" fill="none" stroke="#f0883e" stroke-width="2"/>
                <!-- Flat consolidation -->
                <path d="M90,35 L110,38 L130,42 L150,40 L170,44 L190,38 L210,42 L230,36 L250,40" fill="none" stroke="#f0883e" stroke-width="2"/>
                <!-- Breakout -->
                <path d="M250,40 L270,35 L290,20" fill="none" stroke="#f0883e" stroke-width="2" stroke-dasharray="4,3"/>
                <!-- Buy point line -->
                <line x1="85" y1="35" x2="290" y2="35" stroke="#3fb950" stroke-width="1" stroke-dasharray="4,3"/>
                <!-- Range band -->
                <rect x="90" y="33" width="160" height="14" fill="none" stroke="#8b949e" stroke-width="0.5" stroke-dasharray="2,2" rx="2"/>
                <!-- Labels -->
                <text x="20" y="115" fill="#8b949e" font-size="10">Prior Uptrend</text>
                <text x="170" y="62" fill="#8b949e" font-size="10" text-anchor="middle">Tight Range (&lt;15%)</text>
                <text x="272" y="30" fill="#3fb950" font-size="10">Buy Point</text>
            </svg>
            <p>A tight sideways consolidation where the stock trades in a very narrow range (less than 15%). Usually forms after a prior advance. The tightness shows institutions are quietly accumulating shares without driving the price down.</p>
            <div class="pattern-params">Max depth: 15% | Duration: 5-15 weeks | Volume should contract during base</div>
        </div>
    </div>

    <!-- Reading Your Results -->
    <div class="help-section">
        <h3>Reading Your Results</h3>
        <p>After a scan completes, focus on these key areas:</p>
        <ul>
            <li><strong>Score 75+</strong> = high-quality pattern that closely matches the ideal formation</li>
            <li><strong>"At Pivot" status</strong> = the stock is at its buy point, potentially actionable now</li>
            <li><strong>RS 80+</strong> = stock is outperforming most of the market (institutional demand)</li>
            <li><strong>Vol Rating A or B</strong> = institutions are accumulating (buying) the stock</li>
            <li><strong>Above 50MA and 200MA</strong> = both short-term and long-term trends are healthy</li>
            <li><strong>Volume confirmed (&#10003;)</strong> = the breakout had strong volume support</li>
        </ul>
        <p>The <strong>buy point</strong> is your entry price. Set your <strong>stop loss</strong> 7% below it to protect against failed breakouts. Your <strong>profit target</strong> of 20% above gives a healthy 3:1 risk/reward ratio.</p>
    </div>

    <!-- Understanding the Backtest -->
    <div class="help-section">
        <h3>Understanding the Backtest</h3>
        <p>The backtest replays 2 years of historical data, detects patterns that formed in the past, and simulates what would have happened if you traded every signal using your stop loss and profit target settings.</p>
        <p><strong>Key metrics to watch:</strong></p>
        <ul>
            <li><strong>Win Rate above 50%</strong> is good, but even 40% can be profitable if avg wins >> avg losses</li>
            <li><strong>Profit Factor above 1.5</strong> suggests a solid strategy</li>
            <li><strong>Positive Expectancy</strong> means the strategy makes money over many trades</li>
        </ul>
        <p>Use the <strong>breakdown tables</strong> to see which patterns and market conditions produce the best results. Most patterns perform much better during confirmed uptrends.</p>
        <p style="color:var(--warning);font-size:12px;margin-top:8px;"><em>Past performance does not guarantee future results. Use backtests to understand strategy behavior, not to predict exact returns.</em></p>
    </div>

    <!-- Glossary -->
    <div class="help-section">
        <h3>Glossary</h3>
        <dl>
            <div class="glossary-term">
                <dt>Base Pattern</dt>
                <dd>A period of price consolidation (sideways movement) after an advance. The stock is "resting" before potentially moving higher. Think of it as coiling a spring.</dd>
            </div>
            <div class="glossary-term">
                <dt>Buy Point / Pivot</dt>
                <dd>The price level where a base pattern completes and a breakout is expected. This is the ideal entry price for buying the stock.</dd>
            </div>
            <div class="glossary-term">
                <dt>CAN SLIM</dt>
                <dd>An investment strategy by William O'Neil focusing on Current earnings, Annual earnings, New products/management, Supply and demand, Leader/laggard, Institutional sponsorship, and Market direction.</dd>
            </div>
            <div class="glossary-term">
                <dt>Confidence Score</dt>
                <dd>A 0-100 rating measuring how closely a detected pattern matches the ideal formation. Factors include depth, volume profile, trend strength, relative strength, and breakout quality.</dd>
            </div>
            <div class="glossary-term">
                <dt>Distribution Day</dt>
                <dd>A day where the S&P 500 closes down more than 0.2% on volume higher than the previous day. Clusters of distribution days signal institutional selling and potential market corrections.</dd>
            </div>
            <div class="glossary-term">
                <dt>Expectancy</dt>
                <dd>The average expected profit per trade, factoring in both win rate and the relative sizes of wins vs losses. Positive expectancy means the strategy is profitable over time.</dd>
            </div>
            <div class="glossary-term">
                <dt>Market Regime</dt>
                <dd>The overall market condition: "Confirmed Uptrend" (healthy, good for buying), "Under Pressure" (caution), or "In Correction" (avoid new buys). Based on S&P 500 trend and distribution day count.</dd>
            </div>
            <div class="glossary-term">
                <dt>Moving Average (50/200-day)</dt>
                <dd>The average closing price over the last 50 or 200 trading days. Acts as a trend indicator — price above = healthy trend, price below = weakening. The 200MA represents the long-term trend.</dd>
            </div>
            <div class="glossary-term">
                <dt>Profit Factor</dt>
                <dd>Total gross profits divided by total gross losses. Above 1.0 = profitable, above 2.0 = strong strategy. Below 1.0 = losing money overall.</dd>
            </div>
            <div class="glossary-term">
                <dt>Relative Strength (RS)</dt>
                <dd>A 1-99 rating comparing a stock's price performance to the S&P 500. An RS of 90 means the stock outperformed 90% of all stocks. Look for 80+ for leading stocks.</dd>
            </div>
            <div class="glossary-term">
                <dt>Stop Loss</dt>
                <dd>A pre-set price where you'll sell if the trade goes against you. The default 7% rule limits any single loss to a manageable amount. Never hold through a broken stop loss.</dd>
            </div>
            <div class="glossary-term">
                <dt>Volume Confirmation</dt>
                <dd>When a stock breaks out above its buy point with trading volume at least 40% above its average. This confirms institutional participation and increases breakout reliability.</dd>
            </div>
            <div class="glossary-term">
                <dt>Volume Rating (A-E)</dt>
                <dd>Grades institutional activity: A = heavy buying (accumulation), B = moderate buying, C = neutral, D = moderate selling, E = heavy selling (distribution). Look for A or B.</dd>
            </div>
            <div class="glossary-term">
                <dt>Win Rate</dt>
                <dd>The percentage of trades that ended profitably. A useful but incomplete metric — a 40% win rate can still be very profitable if winners are much larger than losers.</dd>
            </div>
        </dl>
    </div>
</div>
```

**Step 4: Add help panel toggle JavaScript**

Add the following to the `<script>` block, just before the closing `</script>` tag:

```javascript
// --- Help Panel ---
function toggleHelpPanel() {
    document.getElementById('helpPanel').classList.toggle('open');
    document.getElementById('helpBackdrop').classList.toggle('open');
}
document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape' && document.getElementById('helpPanel').classList.contains('open')) {
        toggleHelpPanel();
    }
});
```

**Step 5: Verify app starts**

Run: `cd stock_pattern_scanner && python -c "from app import app; print('OK')"`
Expected: `OK`

**Step 6: Commit**

```bash
git add stock_pattern_scanner/templates/dashboard.html
git commit -m "feat(guide): add slide-in help panel with SVG patterns and glossary"
```

---

## Task 6: Run Full Test Suite

**Step 1: Run all tests**

Run: `cd stock_pattern_scanner && python -m pytest tests/ -v`
Expected: All 82 tests PASS (no backend changes, so nothing should break)

**Step 2: Verify app starts and routes are intact**

Run: `cd stock_pattern_scanner && python -c "from app import app; print('Routes:', [r.path for r in app.routes])"`
Expected: All routes listed including backtest endpoints

**Step 3: Commit if any fixes were needed**

If any fixes were required, commit:
```bash
git add stock_pattern_scanner/templates/dashboard.html
git commit -m "fix(guide): resolve issues from integration testing"
```

---

## Verification Checklist

After all tasks:

- [ ] `python -m pytest tests/ -v` — all 82 tests pass
- [ ] App imports cleanly: `python -c "from app import app"`
- [ ] Dashboard loads at `http://localhost:8000/` with Scanner and Backtest tabs
- [ ] "?" button visible in header, opens slide-in panel
- [ ] Help panel has: Quick Start, How to Use, 4 Pattern cards with SVGs, Reading Results, Backtest section, Glossary
- [ ] Help panel closes on ×, backdrop click, and Escape key
- [ ] Tooltips appear on hover for: Min Score, all 4 stat cards, all 16 table headers, market banner, all backtest controls/metrics/breakdowns
- [ ] Tooltips are readable (no overlap, no clipping off-screen)
- [ ] Mobile: help panel goes full-width, tooltips shrink to 220px

Files modified:
- `stock_pattern_scanner/templates/dashboard.html` (tooltip CSS, help panel CSS, tooltip HTML on ~50 elements, help panel HTML with SVGs, toggle JS)

No files created. No backend changes.
