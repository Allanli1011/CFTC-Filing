"""
Phase 3 — Backtesting framework.

Tests how well COT signals predicted subsequent price returns.
Uses yfinance to fetch futures price data aligned with CFTC report dates.
"""
from __future__ import annotations

import logging
from datetime import timedelta

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def fetch_price_data(ticker: str, start: str, end: str) -> pd.DataFrame:
    """Download weekly closing price for a futures ticker via yfinance."""
    try:
        import yfinance as yf
        df = yf.download(ticker, start=start, end=end, interval="1wk", progress=False, auto_adjust=True)
        if df.empty:
            return pd.DataFrame()
        df = df[["Close"]].rename(columns={"Close": "price"})
        df.index = pd.to_datetime(df.index).tz_localize(None)
        return df
    except Exception as e:
        logger.warning("yfinance failed for %s: %s", ticker, e)
        return pd.DataFrame()


def align_cot_with_prices(cot_df: pd.DataFrame, price_df: pd.DataFrame) -> pd.DataFrame:
    """
    Merge COT data with price data.
    COT dates are usually Tuesday close-of-business; prices are Friday close.
    We use the next Friday's close after each COT report date.
    """
    if cot_df.empty or price_df.empty:
        return pd.DataFrame()

    cot_df = cot_df.copy()
    cot_df["report_date"] = pd.to_datetime(cot_df["report_date"])

    merged_rows = []
    for _, row in cot_df.iterrows():
        cot_date = row["report_date"]
        # Find the closest price date on or after COT date
        future_prices = price_df[price_df.index >= cot_date]
        if future_prices.empty:
            continue
        entry_price = future_prices.iloc[0]["price"]

        # Forward returns at 1, 4, 12, 26 weeks
        for weeks in [1, 4, 12, 26]:
            target_date = cot_date + timedelta(weeks=weeks)
            future = price_df[price_df.index >= target_date]
            if future.empty:
                continue
            exit_price = future.iloc[0]["price"]
            row_dict = row.to_dict()
            row_dict[f"fwd_return_{weeks}w"] = (exit_price / entry_price - 1) * 100
        merged_rows.append(row_dict)

    return pd.DataFrame(merged_rows)


def backtest_cot_index_signal(
    merged_df: pd.DataFrame,
    cot_index_col: str = "noncomm_cot_index",
    long_threshold: float = 80.0,
    short_threshold: float = 20.0,
    forward_weeks: int = 12,
) -> pd.DataFrame:
    """
    Simple backtest: go short when COT index > long_threshold,
    go long when < short_threshold.

    Returns a DataFrame with columns:
      signal_date, signal, cot_index, entry_price, fwd_return, hit
    """
    fwd_col = f"fwd_return_{forward_weeks}w"
    if fwd_col not in merged_df.columns:
        logger.warning("Column %s not found in merged_df", fwd_col)
        return pd.DataFrame()

    df = merged_df.dropna(subset=[cot_index_col, fwd_col]).copy()

    def assign_signal(idx: float) -> str:
        if idx >= long_threshold:
            return "short"
        elif idx <= short_threshold:
            return "long"
        return "flat"

    df["signal"] = df[cot_index_col].apply(assign_signal)
    df = df[df["signal"] != "flat"].copy()

    # Hit rate: short → negative forward return is a win; long → positive is a win
    df["hit"] = df.apply(
        lambda r: (r["signal"] == "short" and r[fwd_col] < 0)
                  or (r["signal"] == "long" and r[fwd_col] > 0),
        axis=1,
    )

    # Adjusted return: flip sign for shorts
    df["adj_return"] = df.apply(
        lambda r: -r[fwd_col] if r["signal"] == "short" else r[fwd_col],
        axis=1,
    )

    result_cols = ["report_date", "signal", cot_index_col, fwd_col, "hit", "adj_return"]
    result_cols = [c for c in result_cols if c in df.columns]
    return df[result_cols].reset_index(drop=True)


def backtest_summary(backtest_df: pd.DataFrame) -> dict:
    """Compute aggregate statistics from a backtest result DataFrame."""
    if backtest_df.empty:
        return {}

    total = len(backtest_df)
    hits  = backtest_df["hit"].sum()
    hit_rate = hits / total * 100

    longs  = backtest_df[backtest_df["signal"] == "long"]
    shorts = backtest_df[backtest_df["signal"] == "short"]

    adj_returns = backtest_df["adj_return"]

    return {
        "total_signals":      total,
        "hit_rate_pct":       round(hit_rate, 1),
        "avg_return_pct":     round(adj_returns.mean(), 2),
        "median_return_pct":  round(adj_returns.median(), 2),
        "max_win_pct":        round(adj_returns.max(), 2),
        "max_loss_pct":       round(adj_returns.min(), 2),
        "sharpe_approx":      round(adj_returns.mean() / adj_returns.std(), 2) if adj_returns.std() > 0 else None,
        "long_signals":       len(longs),
        "long_hit_rate":      round(longs["hit"].mean() * 100, 1) if not longs.empty else None,
        "short_signals":      len(shorts),
        "short_hit_rate":     round(shorts["hit"].mean() * 100, 1) if not shorts.empty else None,
    }


def run_full_backtest(
    contract_code: str,
    price_ticker: str,
    cot_index_col: str = "noncomm_cot_index",
    forward_weeks: int = 12,
    long_threshold: float = 80.0,
    short_threshold: float = 20.0,
) -> tuple[pd.DataFrame, dict]:
    """
    Full backtest pipeline for one market.
    Returns (backtest_df, summary_dict).
    """
    from src.storage.db import get_legacy_df
    from src.analyzer.positioning import compute_legacy_metrics

    cot_df = get_legacy_df(contract_code, limit=600)
    if cot_df.empty:
        return pd.DataFrame(), {}

    cot_df = compute_legacy_metrics(cot_df)

    if cot_df.empty:
        return pd.DataFrame(), {}

    start = str(cot_df["report_date"].min())[:10]
    end   = str(cot_df["report_date"].max())[:10]

    price_df = fetch_price_data(price_ticker, start, end)
    if price_df.empty:
        return pd.DataFrame(), {}

    merged = align_cot_with_prices(cot_df, price_df)
    if merged.empty:
        return pd.DataFrame(), {}

    backtest_df = backtest_cot_index_signal(
        merged, cot_index_col, long_threshold, short_threshold, forward_weeks
    )
    summary = backtest_summary(backtest_df)
    return backtest_df, summary
