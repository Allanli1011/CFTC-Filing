"""Normalize and enrich COT DataFrames for analysis."""
from __future__ import annotations

import pandas as pd


def normalize_legacy(df: pd.DataFrame) -> pd.DataFrame:
    """Sort by date, compute net position ratio and crowding score."""
    if df.empty:
        return df
    df = df.copy()
    df["report_date"] = pd.to_datetime(df["report_date"])
    df = df.sort_values("report_date").reset_index(drop=True)

    # Net position as fraction of open interest
    df["noncomm_net_pct"] = df.apply(
        lambda r: (r.noncomm_net / r.open_interest * 100) if r.open_interest else None, axis=1
    )
    df["comm_net_pct"] = df.apply(
        lambda r: (r.comm_net / r.open_interest * 100) if r.open_interest else None, axis=1
    )

    # Momentum: 4-week change in net position
    df["noncomm_net_chg4w"] = df["noncomm_net"].diff(4)
    df["comm_net_chg4w"] = df["comm_net"].diff(4)

    return df


def normalize_disaggregated(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    df = df.copy()
    df["report_date"] = pd.to_datetime(df["report_date"])
    df = df.sort_values("report_date").reset_index(drop=True)

    df["mmoney_net_pct"] = df.apply(
        lambda r: (r.mmoney_net / r.open_interest * 100) if r.open_interest else None, axis=1
    )
    df["prod_net_pct"] = df.apply(
        lambda r: (r.prod_net / r.open_interest * 100) if r.open_interest else None, axis=1
    )
    df["mmoney_net_chg4w"] = df["mmoney_net"].diff(4)

    return df


def normalize_financial(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    df = df.copy()
    df["report_date"] = pd.to_datetime(df["report_date"])
    df = df.sort_values("report_date").reset_index(drop=True)

    df["levmoney_net_pct"] = df.apply(
        lambda r: (r.levmoney_net / r.open_interest * 100) if r.open_interest else None, axis=1
    )
    df["assetmgr_net_pct"] = df.apply(
        lambda r: (r.assetmgr_net / r.open_interest * 100) if r.open_interest else None, axis=1
    )
    df["levmoney_net_chg4w"] = df["levmoney_net"].diff(4)

    return df
