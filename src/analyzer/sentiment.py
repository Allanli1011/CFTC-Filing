"""
Phase 2 — Sentiment indicators derived from COT positioning.

Composite sentiment score combining:
  1. COT Index (rolling percentile)
  2. Net position vs open interest ratio
  3. Momentum streak
  4. Trader concentration
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def sentiment_score(
    cot_index: float | None,
    net_pct: float | None,
    momentum_streak: int = 0,
) -> float:
    """
    Composite sentiment score in range [0, 100].
    0  = max bearish crowd sentiment
    50 = neutral
    100 = max bullish crowd sentiment

    NOTE: Extreme readings (>80 or <20) are CONTRARIAN signals.
    """
    components = []
    weights = []

    if cot_index is not None and not np.isnan(cot_index):
        components.append(cot_index)
        weights.append(0.55)

    if net_pct is not None and not np.isnan(net_pct):
        # Normalise net_pct to 0-100 assuming range [-50, +50]
        norm = np.clip((net_pct + 50) / 100 * 100, 0, 100)
        components.append(norm)
        weights.append(0.30)

    if momentum_streak != 0:
        # streak of ±5 weeks maps to 75/25
        streak_score = np.clip(50 + momentum_streak * 5, 0, 100)
        components.append(streak_score)
        weights.append(0.15)

    if not components:
        return 50.0

    total_w = sum(weights)
    score = sum(c * w for c, w in zip(components, weights)) / total_w
    return round(float(score), 1)


def interpret_score(score: float) -> tuple[str, str]:
    """Return (direction, label) for a sentiment score."""
    if score >= 80:
        return "bearish", "Extreme Long (Contrarian Bearish)"
    elif score >= 65:
        return "bearish_lean", "Crowded Long (Lean Bearish)"
    elif score >= 55:
        return "neutral", "Slight Bullish Bias"
    elif score >= 45:
        return "neutral", "Neutral"
    elif score >= 35:
        return "neutral", "Slight Bearish Bias"
    elif score >= 20:
        return "bullish_lean", "Crowded Short (Lean Bullish)"
    else:
        return "bullish", "Extreme Short (Contrarian Bullish)"


def add_sentiment(df: pd.DataFrame, cot_col: str, net_pct_col: str, streak_col: str | None = None) -> pd.DataFrame:
    """Add sentiment_score and sentiment_label columns to DataFrame."""
    df = df.copy()

    def _row_score(row):
        streak = int(row[streak_col]) if streak_col and streak_col in row.index else 0
        return sentiment_score(row.get(cot_col), row.get(net_pct_col), streak)

    df["sentiment_score"] = df.apply(_row_score, axis=1)
    df["sentiment_label"] = df["sentiment_score"].apply(lambda s: interpret_score(s)[1])
    df["sentiment_direction"] = df["sentiment_score"].apply(lambda s: interpret_score(s)[0])
    return df
