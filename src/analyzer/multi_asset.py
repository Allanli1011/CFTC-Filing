"""
Phase 4 — Multi-asset correlation analysis.

Identifies cross-market COT positioning relationships that can provide
additional conviction for investment decisions.

Key relationships analyzed:
  - USD positioning vs Gold / commodities (inverse)
  - Equity index positioning vs Bond positioning (risk-on/off)
  - Oil vs Equity correlation
  - Currencies vs underlying commodity markets
"""
from __future__ import annotations

import logging
from itertools import combinations

import numpy as np
import pandas as pd

from src.config import WATCHED_MARKETS, COT_INDEX_LOOKBACK
from src.storage.db import get_legacy_df, get_disaggregated_df
from src.analyzer.positioning import compute_legacy_metrics, compute_disagg_metrics

logger = logging.getLogger(__name__)

# Logical market groups for confluence analysis
MARKET_GROUPS: dict[str, list[str]] = {
    "commodities":  ["088691", "084691", "085692", "067651", "023651"],  # Gold, Silver, Copper, Oil, Gas
    "grains":       ["002602", "005602", "001602"],                       # Corn, Soybeans, Wheat
    "currencies":   ["099741", "097741", "096742"],                       # EUR, JPY, GBP
    "equity":       ["13874A"],                                            # S&P 500
    "rates":        ["043602", "020601"],                                  # 10Y, 2Y T-Note
}

# Known inverse relationships (when A is long, B tends to be short)
INVERSE_PAIRS: list[tuple[str, str]] = [
    ("099741", "088691"),  # EUR long ↔ Gold long (USD weakness)
    ("097741", "067651"),  # JPY long ↔ Oil short (risk-off)
    ("13874A", "043602"),  # Equity long ↔ Bonds short (risk-on)
]

# Known positive relationships
POSITIVE_PAIRS: list[tuple[str, str]] = [
    ("088691", "084691"),  # Gold ↔ Silver
    ("088691", "085692"),  # Gold ↔ Copper
    ("067651", "023651"),  # Oil ↔ Natural Gas
    ("002602", "005602"),  # Corn ↔ Soybeans
]


def _load_cot_index_series(contract_code: str, lookback: int = COT_INDEX_LOOKBACK) -> pd.Series | None:
    """Load the non-commercial COT Index time series for a market."""
    df = get_legacy_df(contract_code, limit=lookback + 20)
    if df.empty or len(df) < 26:
        return None
    df = compute_legacy_metrics(df, lookback=lookback)
    df["report_date"] = pd.to_datetime(df["report_date"])
    s = df.set_index("report_date")["noncomm_cot_index"].dropna()
    s.name = contract_code
    return s


def build_cot_index_panel() -> pd.DataFrame:
    """
    Build a wide DataFrame of COT Index values for all watched markets.
    Columns = contract_code, index = report_date.
    """
    series_list = []
    for code in WATCHED_MARKETS:
        s = _load_cot_index_series(code)
        if s is not None:
            series_list.append(s)

    if not series_list:
        return pd.DataFrame()

    panel = pd.concat(series_list, axis=1).sort_index()
    # Rename columns to market names
    panel.columns = [WATCHED_MARKETS.get(c, c) for c in panel.columns]
    return panel


def correlation_matrix(panel: pd.DataFrame) -> pd.DataFrame:
    """Pearson correlation of COT Index across markets (rolling 52w)."""
    if panel.empty:
        return pd.DataFrame()
    return panel.tail(52).corr(method="pearson").round(2)


def confluence_score(
    code_a: str,
    code_b: str,
    expected_relation: str = "inverse",
    lookback: int = 12,
) -> dict | None:
    """
    Measure how much two markets are currently "in sync" with their expected relationship.

    expected_relation: "inverse" or "positive"

    Returns a dict with current_score and recent_alignment.
    """
    s_a = _load_cot_index_series(code_a)
    s_b = _load_cot_index_series(code_b)
    if s_a is None or s_b is None:
        return None

    # Align on shared dates
    aligned = pd.concat([s_a, s_b], axis=1).dropna().tail(lookback)
    if aligned.empty:
        return None

    col_a, col_b = aligned.columns[0], aligned.columns[1]
    latest_a = aligned[col_a].iloc[-1]
    latest_b = aligned[col_b].iloc[-1]

    if expected_relation == "inverse":
        # Perfect: A=100, B=0 or A=0, B=100
        alignment = abs(latest_a - latest_b) / 100
    else:
        # Perfect: both at same extreme
        alignment = (1 - abs(latest_a - latest_b) / 100)

    return {
        "market_a":       WATCHED_MARKETS.get(code_a, code_a),
        "market_b":       WATCHED_MARKETS.get(code_b, code_b),
        "expected":       expected_relation,
        "cot_index_a":    round(latest_a, 1),
        "cot_index_b":    round(latest_b, 1),
        "alignment_score": round(alignment * 100, 1),
        "is_confirming":  alignment >= 0.6,
    }


def multi_asset_confluence_signals() -> list[dict]:
    """
    Generate confluence signals when multiple related markets show aligned extremes.
    These provide higher-conviction investment signals.
    """
    signals = []

    # Check all inverse pairs
    for code_a, code_b in INVERSE_PAIRS:
        result = confluence_score(code_a, code_b, "inverse")
        if result and result["is_confirming"]:
            a_idx = result["cot_index_a"]
            b_idx = result["cot_index_b"]

            # Determine direction based on which side is extreme
            if a_idx >= 80 and b_idx <= 20:
                direction = "bearish"
                name_a = result["market_a"]
                name_b = result["market_b"]
                desc = (
                    f"Multi-asset confluence (BEARISH): {name_a} COT at {a_idx:.0f}th pct (crowded long) "
                    f"confirmed by {name_b} COT at {b_idx:.0f}th pct (crowded short). "
                    "Inverse relationship aligned — high conviction bearish for {name_a}."
                )
            elif a_idx <= 20 and b_idx >= 80:
                direction = "bullish"
                name_a = result["market_a"]
                name_b = result["market_b"]
                desc = (
                    f"Multi-asset confluence (BULLISH): {name_a} COT at {a_idx:.0f}th pct (crowded short) "
                    f"confirmed by {name_b} COT at {b_idx:.0f}th pct (crowded long). "
                    f"Inverse relationship aligned — high conviction bullish for {name_a}."
                )
            else:
                continue

            signals.append({
                "contract_code":  code_a,
                "market_name":    result["market_a"],
                "paired_market":  result["market_b"],
                "signal_type":    "multi_asset_confluence",
                "direction":      direction,
                "alignment_score": result["alignment_score"],
                "cot_index_a":    a_idx,
                "cot_index_b":    b_idx,
                "description":    desc,
            })

    # Grain sector: all three crowded same direction = sector-wide signal
    grain_series = [(code, _load_cot_index_series(code)) for code in MARKET_GROUPS["grains"]]
    grain_series = [(c, s) for c, s in grain_series if s is not None]
    if len(grain_series) >= 2:
        latest = {c: s.iloc[-1] for c, s in grain_series}
        all_long  = all(v >= 75 for v in latest.values())
        all_short = all(v <= 25 for v in latest.values())
        if all_long or all_short:
            direction = "bearish" if all_long else "bullish"
            signals.append({
                "contract_code":  "GRAINS",
                "market_name":    "Grain Sector (Corn/Soybeans/Wheat)",
                "paired_market":  None,
                "signal_type":    "sector_consensus",
                "direction":      direction,
                "alignment_score": 100.0,
                "description":    (
                    f"ALL grain markets show {'extreme long' if all_long else 'extreme short'} COT positioning. "
                    f"Sector-wide {'bearish (contrarian)' if all_long else 'bullish (contrarian)'} signal."
                ),
            })

    return signals


def risk_on_off_indicator() -> dict:
    """
    Risk-on/off composite from equity vs bonds COT positioning.

    High equity + low bonds COT = risk-on (crowded)
    Low equity + high bonds COT = risk-off (crowded)
    """
    equity_s = _load_cot_index_series("13874A")  # S&P 500
    bond_s   = _load_cot_index_series("043602")  # 10-Year T-Note

    if equity_s is None or bond_s is None:
        return {"status": "insufficient_data"}

    eq_idx   = equity_s.iloc[-1]
    bond_idx = bond_s.iloc[-1]

    # Risk score: high equity + low bonds = risk-on
    risk_on_score = (eq_idx + (100 - bond_idx)) / 2

    if risk_on_score >= 75:
        regime = "risk_on_crowded"
        outlook = "Crowded risk-on positioning — potential for de-risking event."
    elif risk_on_score <= 25:
        regime = "risk_off_crowded"
        outlook = "Crowded risk-off positioning — potential for rally/rebound."
    elif risk_on_score >= 55:
        regime = "risk_on_lean"
        outlook = "Moderately risk-on positioning."
    elif risk_on_score <= 45:
        regime = "risk_off_lean"
        outlook = "Moderately risk-off positioning."
    else:
        regime = "neutral"
        outlook = "Balanced positioning across equities and bonds."

    return {
        "sp500_cot_index":  round(eq_idx, 1),
        "bond_cot_index":   round(bond_idx, 1),
        "risk_on_score":    round(risk_on_score, 1),
        "regime":           regime,
        "outlook":          outlook,
    }
