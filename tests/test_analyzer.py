"""Tests for positioning analysis and sentiment calculation."""
import pytest
import numpy as np
import pandas as pd
from datetime import date, timedelta

from src.analyzer.positioning import cot_index, compute_legacy_metrics
from src.analyzer.sentiment import sentiment_score, interpret_score


# ── COT Index ─────────────────────────────────────────────────────────────────

def _make_series(values: list[float]) -> pd.Series:
    return pd.Series(values, dtype=float)


def test_cot_index_current_max():
    """When current value is the max of the window, COT Index = 100."""
    s = _make_series(list(range(1, 53)))  # 1..52, current = 52 (max)
    result = cot_index(s, lookback=52)
    assert result.iloc[-1] == pytest.approx(100.0)


def test_cot_index_current_min():
    """When current value is the min, COT Index = 0."""
    values = list(range(52, 0, -1))  # 52..1, current = 1 (min)
    s = _make_series(values)
    result = cot_index(s, lookback=52)
    assert result.iloc[-1] == pytest.approx(0.0)


def test_cot_index_midpoint():
    """When current value is the midpoint, COT Index ≈ 50."""
    values = list(range(101))  # 0..100, current = 100 after adding 50
    s = _make_series([50] * 52)  # all equal → midpoint = 50%
    result = cot_index(s, lookback=52)
    # all values equal → min == max == current → returns 50 by our formula
    assert result.iloc[-1] == pytest.approx(50.0)


def test_cot_index_short_series():
    """Series shorter than lookback should still compute with min_periods."""
    s = _make_series([10, 20, 30, 40, 50])
    result = cot_index(s, lookback=52)
    # With min_periods=26, NaN until enough data; with 5 points likely NaN
    # Just ensure it doesn't raise
    assert len(result) == 5


def test_cot_index_output_range():
    """All COT Index values must be in [0, 100]."""
    np.random.seed(42)
    s = pd.Series(np.random.randn(200))
    result = cot_index(s, lookback=52)
    valid = result.dropna()
    assert (valid >= 0).all()
    assert (valid <= 100).all()


# ── compute_legacy_metrics ────────────────────────────────────────────────────

def _make_legacy_df(n: int = 60) -> pd.DataFrame:
    """Build a synthetic legacy COT DataFrame."""
    base = date(2021, 1, 1)
    dates = [base + timedelta(weeks=i) for i in range(n)]
    np.random.seed(0)
    noncomm_long  = np.cumsum(np.random.randn(n)) * 1000 + 150000
    noncomm_short = np.cumsum(np.random.randn(n)) * 500  + 80000
    comm_long     = np.cumsum(np.random.randn(n)) * 800  + 100000
    comm_short    = np.cumsum(np.random.randn(n)) * 800  + 200000
    oi = noncomm_long + comm_long + 50000

    return pd.DataFrame({
        "report_date":   dates,
        "open_interest": oi.astype(int),
        "noncomm_long":  noncomm_long.astype(int),
        "noncomm_short": noncomm_short.astype(int),
        "noncomm_net":   (noncomm_long - noncomm_short).astype(int),
        "comm_long":     comm_long.astype(int),
        "comm_short":    comm_short.astype(int),
        "comm_net":      (comm_long - comm_short).astype(int),
        "nonrept_long":  np.full(n, 10000, dtype=int),
        "nonrept_short": np.full(n, 15000, dtype=int),
    })


def test_compute_legacy_metrics_columns():
    df = _make_legacy_df()
    result = compute_legacy_metrics(df, lookback=52)
    for col in ["noncomm_cot_index", "comm_cot_index", "noncomm_net_pct",
                "noncomm_net_chg1w", "noncomm_net_chg4w", "noncomm_momentum_streak"]:
        assert col in result.columns, f"Missing column: {col}"


def test_compute_legacy_metrics_sorted():
    df = _make_legacy_df().sample(frac=1, random_state=42)  # shuffle
    result = compute_legacy_metrics(df)
    dates = pd.to_datetime(result["report_date"])
    assert (dates.diff().dropna() > pd.Timedelta(0)).all(), "Output should be sorted by date"


def test_compute_legacy_metrics_streak_type():
    df = _make_legacy_df()
    result = compute_legacy_metrics(df)
    streaks = result["noncomm_momentum_streak"]
    assert streaks.dtype in (int, object) or str(streaks.dtype).startswith("int")
    assert not streaks.isna().any()


# ── Sentiment ─────────────────────────────────────────────────────────────────

def test_sentiment_score_extreme_long():
    score = sentiment_score(cot_index=90, net_pct=30, momentum_streak=5)
    assert score > 75, "High COT index + positive streak should produce high score"


def test_sentiment_score_extreme_short():
    score = sentiment_score(cot_index=10, net_pct=-30, momentum_streak=-5)
    assert score < 25, "Low COT index + negative streak should produce low score"


def test_sentiment_score_neutral():
    score = sentiment_score(cot_index=50, net_pct=0)
    assert 40 < score < 60, "Neutral inputs should produce score near 50"


def test_sentiment_score_no_data():
    score = sentiment_score(None, None)
    assert score == 50.0


def test_interpret_score_extreme_long():
    direction, label = interpret_score(85)
    assert direction == "bearish"
    assert "Extreme" in label


def test_interpret_score_extreme_short():
    direction, label = interpret_score(10)
    assert direction == "bullish"
    assert "Extreme" in label


def test_interpret_score_neutral():
    direction, label = interpret_score(50)
    assert direction == "neutral"


def test_interpret_score_range():
    """Ensure all percentile values return a valid tuple."""
    for v in range(0, 101, 5):
        direction, label = interpret_score(float(v))
        assert isinstance(direction, str)
        assert isinstance(label, str)
        assert len(direction) > 0
