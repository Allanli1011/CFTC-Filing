"""Tests for signal generation logic."""
import pytest
from unittest.mock import patch, MagicMock
from datetime import date

import pandas as pd
import numpy as np

from src.analyzer.signals import _build_signal, signals_from_legacy
from src.config import WATCHED_MARKETS


# ── _build_signal ─────────────────────────────────────────────────────────────

def test_build_signal_basic():
    sig = _build_signal(
        contract_code="088691",
        report_date=date(2024, 1, 5),
        signal_type="extreme_long",
        signal_source="legacy",
        direction="bearish",
        strength=85.0,
        description="Test signal",
        cot_index=85.0,
        net_position=140000,
        net_chg_1w=3000,
    )
    assert sig["contract_code"] == "088691"
    assert sig["market_name"] == "Gold"
    assert sig["direction"] == "bearish"
    assert sig["strength"] == pytest.approx(85.0)
    assert sig["cot_index"] == pytest.approx(85.0)
    assert isinstance(sig["report_date"], date)


def test_build_signal_unknown_code():
    sig = _build_signal("UNKNOWN", date(2024, 1, 1), "test", "legacy", "neutral", 50.0, "")
    assert sig["market_name"] == "UNKNOWN"


def test_build_signal_strength_rounded():
    sig = _build_signal("088691", date(2024, 1, 1), "t", "l", "neutral", 83.456, "")
    assert sig["strength"] == pytest.approx(83.5)


# ── signals_from_legacy ───────────────────────────────────────────────────────

def _make_legacy_df_with_cot(n: int = 60, final_cot: float = 85.0) -> pd.DataFrame:
    """Build a synthetic legacy DF with a given final COT Index value."""
    base = date(2021, 1, 1)
    dates = [base + pd.Timedelta(weeks=i) for i in range(n)]

    # Build values such that final position lands at desired percentile
    # We'll set values 0..n-2 evenly spread, last = percentile target
    noncomm_net = list(range(0, n - 1))  # 0..n-2
    last_val = final_cot / 100 * (n - 2)  # interpolate
    noncomm_net.append(last_val)

    comm_long  = [100000] * n
    comm_short = [200000] * n

    return pd.DataFrame({
        "report_date":   dates,
        "open_interest": [500000] * n,
        "noncomm_long":  [v + 100000 for v in noncomm_net],
        "noncomm_short": [100000] * n,
        "noncomm_net":   noncomm_net,
        "noncomm_net_pct": [v / 5000 for v in noncomm_net],
        "comm_long":     comm_long,
        "comm_short":    comm_short,
        "comm_net":      [l - s for l, s in zip(comm_long, comm_short)],
        "nonrept_long":  [10000] * n,
        "nonrept_short": [15000] * n,
        "noncomm_cot_index": [None] * (n - 1) + [final_cot],
        "comm_cot_index":    [None] * n,
        "noncomm_net_chg1w": [None] + [noncomm_net[i] - noncomm_net[i-1] for i in range(1, n)],
        "noncomm_net_chg4w": [None] * 4 + [noncomm_net[i] - noncomm_net[i-4] for i in range(4, n)],
        "noncomm_momentum_streak": [1] * n,
    })


def test_signals_extreme_long_generated():
    df = _make_legacy_df_with_cot(final_cot=85.0)
    with patch("src.analyzer.signals.get_legacy_df", return_value=df):
        with patch("src.analyzer.signals.compute_legacy_metrics", return_value=df):
            sigs = signals_from_legacy("088691")
    extreme = [s for s in sigs if s["signal_type"] == "extreme_long"]
    assert len(extreme) >= 1
    assert extreme[0]["direction"] == "bearish"


def test_signals_extreme_short_generated():
    df = _make_legacy_df_with_cot(final_cot=15.0)
    with patch("src.analyzer.signals.get_legacy_df", return_value=df):
        with patch("src.analyzer.signals.compute_legacy_metrics", return_value=df):
            sigs = signals_from_legacy("088691")
    extreme = [s for s in sigs if s["signal_type"] == "extreme_short"]
    assert len(extreme) >= 1
    assert extreme[0]["direction"] == "bullish"


def test_signals_neutral_no_extreme():
    df = _make_legacy_df_with_cot(final_cot=50.0)
    with patch("src.analyzer.signals.get_legacy_df", return_value=df):
        with patch("src.analyzer.signals.compute_legacy_metrics", return_value=df):
            sigs = signals_from_legacy("088691")
    extreme = [s for s in sigs if s["signal_type"] in ("extreme_long", "extreme_short")]
    assert len(extreme) == 0


def test_signals_empty_df_returns_empty():
    with patch("src.analyzer.signals.get_legacy_df", return_value=pd.DataFrame()):
        sigs = signals_from_legacy("088691")
    assert sigs == []


def test_signals_strength_in_range():
    df = _make_legacy_df_with_cot(final_cot=90.0)
    with patch("src.analyzer.signals.get_legacy_df", return_value=df):
        with patch("src.analyzer.signals.compute_legacy_metrics", return_value=df):
            sigs = signals_from_legacy("088691")
    for sig in sigs:
        assert 0 <= sig["strength"] <= 100, f"Strength out of range: {sig['strength']}"


def test_signals_required_fields():
    df = _make_legacy_df_with_cot(final_cot=85.0)
    required = {"contract_code", "report_date", "signal_type", "direction", "strength", "description"}
    with patch("src.analyzer.signals.get_legacy_df", return_value=df):
        with patch("src.analyzer.signals.compute_legacy_metrics", return_value=df):
            sigs = signals_from_legacy("088691")
    for sig in sigs:
        missing = required - set(sig.keys())
        assert not missing, f"Signal missing fields: {missing}"
