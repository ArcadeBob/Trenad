"""Tests for volume accumulation/distribution analysis."""

from __future__ import annotations

import pandas as pd

from volume_analysis import VolumeAnalyzer


def _make_base_df(
    closes: list[float],
    volumes: list[float],
    base_start: int,
    base_end: int,
) -> tuple[pd.DataFrame, int, int]:
    """Build a DataFrame with explicit base boundaries."""
    n = len(closes)
    dates = pd.bdate_range(end="2026-02-20", periods=n)
    df = pd.DataFrame(
        {
            "Open": closes,
            "High": [c * 1.01 for c in closes],
            "Low": [c * 0.99 for c in closes],
            "Close": closes,
            "Volume": volumes,
        },
        index=dates,
    )
    avg_vol = pd.Series(volumes).rolling(50).mean()
    df["AvgVolume50"] = avg_vol.values
    return df, base_start, base_end


def test_ad_rating_strong_accumulation():
    """Mostly up days on high volume -> A or B rating."""
    n = 250
    # Create data with alternating up/down pattern but net upward bias
    # Up days have very high volume, down days have very low volume
    closes = []
    volumes = []
    price = 100.0
    for i in range(n):
        if i % 5 == 3:  # every 5th day is a small down day
            price -= 0.2
            volumes.append(300_000)  # low volume on down days
        else:
            price += 0.3
            volumes.append(3_000_000)  # high volume on up days
        closes.append(price)
    df, bs, be = _make_base_df(closes, volumes, 200, 249)
    analyzer = VolumeAnalyzer(df, bs, be)
    rating = analyzer.ad_rating()
    assert rating in ("A", "B")


def test_ad_rating_heavy_distribution():
    """Mostly down days on high volume -> D or E rating."""
    n = 250
    # Create data with alternating up/down pattern but net downward bias
    # Down days have very high volume, up days have very low volume
    closes = []
    volumes = []
    price = 150.0
    for i in range(n):
        if i % 5 == 3:  # every 5th day is a small up day
            price += 0.2
            volumes.append(300_000)  # low volume on up days
        else:
            price -= 0.3
            volumes.append(3_000_000)  # high volume on down days
        closes.append(price)
    df, bs, be = _make_base_df(closes, volumes, 200, 249)
    analyzer = VolumeAnalyzer(df, bs, be)
    rating = analyzer.ad_rating()
    assert rating in ("D", "E")


def test_volume_dryup_score():
    """Volume dropping off at end of base -> low dry-up score (good)."""
    n = 250
    closes = [100 + (30 * i / (n - 1)) for i in range(n)]
    volumes = [1_000_000] * n
    # Last 10 days of base have very low volume
    for i in range(240, 250):
        volumes[i] = 300_000
    df, bs, be = _make_base_df(closes, volumes, 200, 249)
    analyzer = VolumeAnalyzer(df, bs, be)
    score = analyzer.dryup_score()
    assert score < 0.7


def test_updown_volume_ratio_bullish():
    """More volume on up days than down days -> ratio > 1.0."""
    n = 250
    closes = [100 + (50 * i / (n - 1)) for i in range(n)]
    volumes = []
    for i in range(n):
        if i > 0 and closes[i] > closes[i - 1]:
            volumes.append(2_000_000)
        else:
            volumes.append(500_000)
    df, bs, be = _make_base_df(closes, volumes, 200, 249)
    analyzer = VolumeAnalyzer(df, bs, be)
    ratio = analyzer.updown_ratio()
    assert ratio > 1.0


def test_score_returns_0_to_20():
    """Volume score must be in [0, 20]."""
    n = 250
    closes = [100 + (50 * i / (n - 1)) for i in range(n)]
    volumes = [1_000_000] * n
    df, bs, be = _make_base_df(closes, volumes, 200, 249)
    analyzer = VolumeAnalyzer(df, bs, be)
    score = analyzer.score()
    assert 0 <= score <= 20


def test_is_distributing_flag():
    """D or E rating should flag as distributing."""
    n = 250
    # Same heavy distribution pattern as test_ad_rating_heavy_distribution
    closes = []
    volumes = []
    price = 150.0
    for i in range(n):
        if i % 5 == 3:  # every 5th day is a small up day
            price += 0.2
            volumes.append(300_000)
        else:
            price -= 0.3
            volumes.append(3_000_000)
        closes.append(price)
    df, bs, be = _make_base_df(closes, volumes, 200, 249)
    analyzer = VolumeAnalyzer(df, bs, be)
    assert analyzer.is_distributing()
