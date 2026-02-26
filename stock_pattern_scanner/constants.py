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
