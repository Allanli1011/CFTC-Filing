"""
Phase 2 — Positioning analysis.

Key metrics:
  - COT Index: rolling percentile of net positions (the core sentiment indicator)
  - Net position as % of open interest
  - Week-over-week and 4-week momentum
  - Crowd positioning score (0–100)
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.config import COT_INDEX_LOOKBACK


def cot_index(series: pd.Series, lookback: int = COT_INDEX_LOOKBACK) -> pd.Series:
    """
    Classic COT Index = rolling percentile rank of net position.

    Value of 100 means net position is the highest in the lookback window.
    Value of 0 means the lowest.
    Readings > 80 → crowd extremely long (potential fade).
    Readings < 20 → crowd extremely short (potential fade).
    """
    def _pct_rank(window: pd.Series) -> float:
        if len(window) < 2:
            return float("nan")
        current = window.iloc[-1]
        mn, mx = window.min(), window.max()
        if mx == mn:
            return 50.0
        return (current - mn) / (mx - mn) * 100

    return series.rolling(window=lookback, min_periods=min(26, lookback)).apply(_pct_rank, raw=False)


def compute_legacy_metrics(df: pd.DataFrame, lookback: int = COT_INDEX_LOOKBACK) -> pd.DataFrame:
    """
    Enrich a single-market Legacy COT DataFrame with analysis columns.
    Input df must be sorted by report_date ascending.
    """
    if df.empty:
        return df
    df = df.copy()
    df = df.sort_values("report_date").reset_index(drop=True)

    df["noncomm_cot_index"] = cot_index(df["noncomm_net"].astype(float), lookback)
    df["comm_cot_index"]    = cot_index(df["comm_net"].astype(float), lookback)

    # Net % of OI
    df["noncomm_net_pct"] = df["noncomm_net"] / df["open_interest"].replace(0, np.nan) * 100
    df["comm_net_pct"]    = df["comm_net"]    / df["open_interest"].replace(0, np.nan) * 100

    # 1-week and 4-week net changes
    df["noncomm_net_chg1w"] = df["noncomm_net"].diff(1)
    df["noncomm_net_chg4w"] = df["noncomm_net"].diff(4)
    df["comm_net_chg1w"]    = df["comm_net"].diff(1)

    # Momentum streak: consecutive weeks of increasing net longs (speculators)
    direction = np.sign(df["noncomm_net_chg1w"].fillna(0))
    streak = []
    count = 0
    for d in direction:
        if d > 0:
            count = max(count + 1, 1)
        elif d < 0:
            count = min(count - 1, -1)
        else:
            count = 0
        streak.append(count)
    df["noncomm_momentum_streak"] = streak

    return df


def compute_disagg_metrics(df: pd.DataFrame, lookback: int = COT_INDEX_LOOKBACK) -> pd.DataFrame:
    if df.empty:
        return df
    df = df.copy()
    df = df.sort_values("report_date").reset_index(drop=True)

    df["mmoney_cot_index"] = cot_index(df["mmoney_net"].astype(float), lookback)
    df["prod_cot_index"]   = cot_index(df["prod_net"].astype(float), lookback)

    df["mmoney_net_pct"] = df["mmoney_net"] / df["open_interest"].replace(0, np.nan) * 100
    df["prod_net_pct"]   = df["prod_net"]   / df["open_interest"].replace(0, np.nan) * 100

    df["mmoney_net_chg1w"] = df["mmoney_net"].diff(1)
    df["mmoney_net_chg4w"] = df["mmoney_net"].diff(4)

    return df


def compute_financial_metrics(df: pd.DataFrame, lookback: int = COT_INDEX_LOOKBACK) -> pd.DataFrame:
    if df.empty:
        return df
    df = df.copy()
    df = df.sort_values("report_date").reset_index(drop=True)

    df["levmoney_cot_index"]  = cot_index(df["levmoney_net"].astype(float), lookback)
    df["assetmgr_cot_index"]  = cot_index(df["assetmgr_net"].astype(float), lookback)

    df["levmoney_net_pct"]  = df["levmoney_net"]  / df["open_interest"].replace(0, np.nan) * 100
    df["assetmgr_net_pct"]  = df["assetmgr_net"]  / df["open_interest"].replace(0, np.nan) * 100

    df["levmoney_net_chg1w"] = df["levmoney_net"].diff(1)
    df["levmoney_net_chg4w"] = df["levmoney_net"].diff(4)

    return df


def latest_summary(df: pd.DataFrame, metric_cols: list[str]) -> dict:
    """Return the most recent row as a dict with only the requested columns."""
    if df.empty:
        return {}
    row = df.iloc[-1]
    return {c: row.get(c) for c in metric_cols if c in row.index}
