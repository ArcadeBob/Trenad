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

# ---------------------------------------------------------------------------
# Market regime
# ---------------------------------------------------------------------------
REGIME_DISTRIBUTION_DAY_DECLINE_PCT = 0.2
REGIME_DISTRIBUTION_DAY_LOOKBACK = 25
REGIME_PRESSURE_DISTRIBUTION_DAYS = 4
REGIME_CORRECTION_DISTRIBUTION_DAYS = 5
REGIME_MA_SLOPE_LOOKBACK = 10

# ---------------------------------------------------------------------------
# Volume analysis
# ---------------------------------------------------------------------------
VOLUME_DRYUP_TAIL_DAYS = 10
VOLUME_DRYUP_GOOD = 0.7
VOLUME_UPDOWN_STRONG = 1.5
VOLUME_UPDOWN_GOOD = 1.3

# ---------------------------------------------------------------------------
# Breakout rules
# ---------------------------------------------------------------------------
BREAKOUT_VOLUME_SURGE_PCT = 40.0
BREAKOUT_CLOSE_UPPER_HALF = 0.5
BREAKOUT_ENTRY_MAX_PCT = 2.0
BREAKOUT_EXTENDED_PCT = 5.0
STOP_LOSS_PCT = 7.0
PROFIT_TARGET_PCT = 20.0

# ---------------------------------------------------------------------------
# Trend strength
# ---------------------------------------------------------------------------
ADX_PERIOD = 14
ADX_STRONG = 30.0
ADX_MINIMUM = 20.0
ATR_PERIOD = 14
ATR_MAX_RATIO_PCT = 5.0
MA_SLOPE_LOOKBACK = 50

# ---------------------------------------------------------------------------
# Revised confidence scoring weights
# ---------------------------------------------------------------------------
SCORE_DEPTH_MAX_V2 = 15.0
SCORE_VOLUME_PROFILE_MAX = 20.0
SCORE_ABOVE_50MA_MAX_V2 = 10.0
SCORE_ABOVE_200MA_MAX_V2 = 5.0
SCORE_TIGHTNESS_MAX_V2 = 10.0
SCORE_BASE_LENGTH_MAX_V2 = 5.0
SCORE_PATTERN_BONUS_MAX_V2 = 10.0
SCORE_TREND_STRENGTH_MAX = 10.0
SCORE_RS_RATING_MAX = 10.0
SCORE_BREAKOUT_QUALITY_MAX = 5.0
SCORE_MINIMUM_VIABLE = 40.0

# RS scoring thresholds
RS_STRONG = 80.0
RS_MODERATE = 60.0

# ---------------------------------------------------------------------------
# Backtesting
# ---------------------------------------------------------------------------
BACKTEST_SCAN_INTERVAL_DAYS = 5
BACKTEST_DEFAULT_STOP_LOSS_PCT = 7.0
BACKTEST_DEFAULT_PROFIT_TARGET_PCT = 20.0
BACKTEST_DEFAULT_MIN_CONFIDENCE = 40.0
BACKTEST_MAX_OPEN_TRADES_PER_TICKER = 1

# ---------------------------------------------------------------------------
# Earnings Analysis (FMP)
# ---------------------------------------------------------------------------
FMP_API_BASE_URL = "https://financialmodelingprep.com/api/v3"
FMP_REQUEST_DELAY_MS = 300  # delay between FMP calls to respect rate limits
FMP_CACHE_TTL_HOURS = 24  # cache earnings data for 24 hours

# Earnings proximity thresholds (calendar days)
EARNINGS_IMMINENT_DAYS = 7
EARNINGS_SOON_DAYS = 14

# Post-earnings momentum scoring
EARNINGS_BEAT_MIN_PCT = 5.0  # minimum EPS surprise % for points
EARNINGS_BEAT_STRONG_PCT = 15.0  # strong beat threshold
EARNINGS_GAP_UP_PCT = 3.0  # stock gap-up on earnings day
SCORE_EARNINGS_MOMENTUM_MAX = 10.0  # max points for earnings factor

# ---------------------------------------------------------------------------
# Sector Relative Strength
# ---------------------------------------------------------------------------
SECTOR_ETF_MAP = {
    "Technology": "XLK",
    "Healthcare": "XLV",
    "Financial Services": "XLF",
    "Consumer Cyclical": "XLY",
    "Communication Services": "XLC",
    "Industrials": "XLI",
    "Consumer Defensive": "XLP",
    "Energy": "XLE",
    "Utilities": "XLU",
    "Real Estate": "XLRE",
    "Basic Materials": "XLB",
}
SECTOR_LEADING_THRESHOLD = 70  # RS above this = leading sector
SECTOR_LAGGING_THRESHOLD = 50  # RS below this = lagging sector
SECTOR_LEADING_BONUS = 5  # confidence points for leading sector
SECTOR_LAGGING_PENALTY = -10  # confidence penalty for lagging sector
SECTOR_CACHE_TTL_HOURS = 24

# ---------------------------------------------------------------------------
# Liquidity Floor
# ---------------------------------------------------------------------------
MIN_AVG_DOLLAR_VOLUME = 5_000_000  # $5M minimum avg daily dollar volume

# ---------------------------------------------------------------------------
# Scoring Rebalance
# ---------------------------------------------------------------------------
# Reduce depth from 15 to 10, volume from 20 to 15
SCORE_DEPTH_MAX = 10.0  # was 15.0
SCORE_VOLUME_PROFILE_MAX = 15.0  # was 20.0

# ---------------------------------------------------------------------------
# Volume Confirmation Grading
# ---------------------------------------------------------------------------
VOLUME_SURGE_WEAK_PCT = 20.0
VOLUME_SURGE_MODERATE_PCT = 40.0  # was the only threshold
VOLUME_SURGE_STRONG_PCT = 80.0
VOLUME_SURGE_CLIMACTIC_PCT = 150.0

SCORE_BREAKOUT_WEAK = 0.0
SCORE_BREAKOUT_MODERATE = 2.0
SCORE_BREAKOUT_CONFIRMED = 4.0
SCORE_BREAKOUT_STRONG = 5.0
SCORE_BREAKOUT_CLIMACTIC = 3.0  # penalty for exhaustion

# ---------------------------------------------------------------------------
# Market Regime Softening
# ---------------------------------------------------------------------------
REGIME_CORRECTION_CONFIDENCE_PENALTY = 15  # points deducted during corrections
