"""
Phase 2 & 3 — Signal generation.

Signal types:
  - extreme_long / extreme_short  : COT Index above/below threshold
  - divergence                    : Commercials vs Managed Money extreme divergence
  - momentum_acceleration         : Net position momentum streak >= 4 weeks
  - reversal_setup                : COT Index flip from extreme back toward neutral
  - multi_asset_confluence        : Phase 4 — correlated market confirmation
"""
from __future__ import annotations

import logging
from datetime import date

import pandas as pd

from src.config import (
    COT_INDEX_LOOKBACK,
    EXTREME_LONG_THRESHOLD,
    EXTREME_SHORT_THRESHOLD,
    WATCHED_MARKETS,
)
from src.storage.db import (
    get_legacy_df,
    get_disaggregated_df,
    get_financial_df,
    save_signals,
)
from src.analyzer.positioning import compute_legacy_metrics, compute_disagg_metrics, compute_financial_metrics
from src.analyzer.sentiment import sentiment_score, interpret_score

logger = logging.getLogger(__name__)


def _build_signal(
    contract_code: str,
    report_date,
    signal_type: str,
    signal_source: str,
    direction: str,
    strength: float,
    description: str,
    cot_index: float | None = None,
    net_position: int | None = None,
    net_chg_1w: int | None = None,
) -> dict:
    return {
        "contract_code": contract_code,
        "market_name":   WATCHED_MARKETS.get(contract_code, contract_code),
        "report_date":   report_date if isinstance(report_date, date) else report_date.date(),
        "signal_type":   signal_type,
        "signal_source": signal_source,
        "direction":     direction,
        "strength":      round(strength, 1),
        "description":   description,
        "cot_index":     round(cot_index, 1) if cot_index is not None else None,
        "net_position":  int(net_position) if net_position is not None else None,
        "net_chg_1w":    int(net_chg_1w) if net_chg_1w is not None else None,
    }


# ── Legacy signals ────────────────────────────────────────────────────────────

def signals_from_legacy(contract_code: str) -> list[dict]:
    df = get_legacy_df(contract_code, limit=COT_INDEX_LOOKBACK + 10)
    if df.empty or len(df) < 26:
        return []

    df = compute_legacy_metrics(df)
    row = df.iloc[-1]
    signals = []

    idx = row.get("noncomm_cot_index")
    if idx is None or pd.isna(idx):
        return []

    net    = row.get("noncomm_net")
    chg1w  = row.get("noncomm_net_chg1w")
    streak = int(row.get("noncomm_momentum_streak", 0))
    score  = sentiment_score(idx, row.get("noncomm_net_pct"), streak)
    direction, label = interpret_score(score)

    # Extreme positioning
    if idx >= EXTREME_LONG_THRESHOLD:
        signals.append(_build_signal(
            contract_code, row["report_date"], "extreme_long", "legacy",
            "bearish",
            strength=idx,
            description=f"Non-commercial net long at {idx:.0f}th percentile. {label}.",
            cot_index=idx, net_position=net, net_chg_1w=chg1w,
        ))
    elif idx <= EXTREME_SHORT_THRESHOLD:
        signals.append(_build_signal(
            contract_code, row["report_date"], "extreme_short", "legacy",
            "bullish",
            strength=100 - idx,
            description=f"Non-commercial net short at {idx:.0f}th percentile. {label}.",
            cot_index=idx, net_position=net, net_chg_1w=chg1w,
        ))

    # Momentum acceleration (streak >= 4 or <= -4)
    if abs(streak) >= 4:
        sig_dir = "bullish" if streak > 0 else "bearish"
        signals.append(_build_signal(
            contract_code, row["report_date"], "momentum_acceleration", "legacy",
            sig_dir,
            strength=min(abs(streak) * 15, 95),
            description=f"Non-commercial net position trending {'up' if streak > 0 else 'down'} "
                        f"for {abs(streak)} consecutive weeks.",
            cot_index=idx, net_position=net, net_chg_1w=chg1w,
        ))

    # Reversal setup: was extreme last week, now pulling back
    if len(df) >= 2:
        prev_idx = df.iloc[-2].get("noncomm_cot_index")
        if prev_idx is not None and not pd.isna(prev_idx):
            was_extreme_long  = prev_idx >= EXTREME_LONG_THRESHOLD  and idx < EXTREME_LONG_THRESHOLD
            was_extreme_short = prev_idx <= EXTREME_SHORT_THRESHOLD and idx > EXTREME_SHORT_THRESHOLD
            if was_extreme_long:
                signals.append(_build_signal(
                    contract_code, row["report_date"], "reversal_setup", "legacy",
                    "bearish", strength=70,
                    description=f"COT Index dropped from extreme long ({prev_idx:.0f}) to {idx:.0f}. "
                                "Potential bearish reversal confirmation.",
                    cot_index=idx, net_position=net, net_chg_1w=chg1w,
                ))
            elif was_extreme_short:
                signals.append(_build_signal(
                    contract_code, row["report_date"], "reversal_setup", "legacy",
                    "bullish", strength=70,
                    description=f"COT Index recovered from extreme short ({prev_idx:.0f}) to {idx:.0f}. "
                                "Potential bullish reversal confirmation.",
                    cot_index=idx, net_position=net, net_chg_1w=chg1w,
                ))

    return signals


# ── Disaggregated divergence signals (Phase 3) ────────────────────────────────

def signals_from_disaggregated(contract_code: str) -> list[dict]:
    """
    Divergence signal: Producer/Merchant (smart money) vs Managed Money.
    When these two groups are at opposite extremes, it's a high-conviction signal.
    """
    df = get_disaggregated_df(contract_code, limit=COT_INDEX_LOOKBACK + 10)
    if df.empty or len(df) < 26:
        return []

    df = compute_disagg_metrics(df)
    row = df.iloc[-1]
    signals = []

    mm_idx   = row.get("mmoney_cot_index")
    prod_idx = row.get("prod_cot_index")

    if mm_idx is None or prod_idx is None or pd.isna(mm_idx) or pd.isna(prod_idx):
        return []

    mm_net   = row.get("mmoney_net")
    chg1w    = row.get("mmoney_net_chg1w")

    # Divergence: MM extreme long + Producer extreme short (bearish setup)
    if mm_idx >= EXTREME_LONG_THRESHOLD and prod_idx <= EXTREME_SHORT_THRESHOLD:
        divergence_strength = (mm_idx - prod_idx) / 100 * 80 + 20
        signals.append(_build_signal(
            contract_code, row["report_date"], "divergence", "disaggregated",
            "bearish",
            strength=min(divergence_strength, 98),
            description=(
                f"STRONG BEARISH SETUP: Managed Money at extreme long ({mm_idx:.0f}th pct) "
                f"while Producers at extreme short ({prod_idx:.0f}th pct). "
                "Smart money (producers) opposing speculative crowd."
            ),
            cot_index=mm_idx, net_position=mm_net, net_chg_1w=chg1w,
        ))

    # Divergence: MM extreme short + Producer extreme long (bullish setup)
    elif mm_idx <= EXTREME_SHORT_THRESHOLD and prod_idx >= EXTREME_LONG_THRESHOLD:
        divergence_strength = (prod_idx - mm_idx) / 100 * 80 + 20
        signals.append(_build_signal(
            contract_code, row["report_date"], "divergence", "disaggregated",
            "bullish",
            strength=min(divergence_strength, 98),
            description=(
                f"STRONG BULLISH SETUP: Managed Money at extreme short ({mm_idx:.0f}th pct) "
                f"while Producers at extreme long ({prod_idx:.0f}th pct). "
                "Smart money (producers) supporting market against speculative shorts."
            ),
            cot_index=mm_idx, net_position=mm_net, net_chg_1w=chg1w,
        ))

    # Extreme MM-only signals
    elif mm_idx >= EXTREME_LONG_THRESHOLD:
        signals.append(_build_signal(
            contract_code, row["report_date"], "extreme_long", "disaggregated",
            "bearish", strength=mm_idx,
            description=f"Managed Money at {mm_idx:.0f}th percentile — crowded long.",
            cot_index=mm_idx, net_position=mm_net, net_chg_1w=chg1w,
        ))
    elif mm_idx <= EXTREME_SHORT_THRESHOLD:
        signals.append(_build_signal(
            contract_code, row["report_date"], "extreme_short", "disaggregated",
            "bullish", strength=100 - mm_idx,
            description=f"Managed Money at {mm_idx:.0f}th percentile — crowded short.",
            cot_index=mm_idx, net_position=mm_net, net_chg_1w=chg1w,
        ))

    return signals


# ── Financial (TFF) signals ───────────────────────────────────────────────────

def signals_from_financial(contract_code: str) -> list[dict]:
    df = get_financial_df(contract_code, limit=COT_INDEX_LOOKBACK + 10)
    if df.empty or len(df) < 26:
        return []

    df = compute_financial_metrics(df)
    row = df.iloc[-1]
    signals = []

    lm_idx = row.get("levmoney_cot_index")
    am_idx = row.get("assetmgr_cot_index")

    if lm_idx is None or pd.isna(lm_idx):
        return []

    lm_net = row.get("levmoney_net")
    chg1w  = row.get("levmoney_net_chg1w")

    if lm_idx >= EXTREME_LONG_THRESHOLD:
        signals.append(_build_signal(
            contract_code, row["report_date"], "extreme_long", "financial",
            "bearish", strength=lm_idx,
            description=f"Leveraged money at extreme long ({lm_idx:.0f}th pct). Hedge fund crowding.",
            cot_index=lm_idx, net_position=lm_net, net_chg_1w=chg1w,
        ))
    elif lm_idx <= EXTREME_SHORT_THRESHOLD:
        signals.append(_build_signal(
            contract_code, row["report_date"], "extreme_short", "financial",
            "bullish", strength=100 - lm_idx,
            description=f"Leveraged money at extreme short ({lm_idx:.0f}th pct). Hedge fund crowding.",
            cot_index=lm_idx, net_position=lm_net, net_chg_1w=chg1w,
        ))

    # Asset Manager diverges from Leveraged Money
    if am_idx is not None and not pd.isna(am_idx):
        if lm_idx >= EXTREME_LONG_THRESHOLD and am_idx <= EXTREME_SHORT_THRESHOLD:
            signals.append(_build_signal(
                contract_code, row["report_date"], "divergence", "financial",
                "bearish", strength=85,
                description=(
                    f"Divergence: Leveraged money crowded long ({lm_idx:.0f}th pct) "
                    f"while Asset Managers short ({am_idx:.0f}th pct)."
                ),
                cot_index=lm_idx, net_position=lm_net, net_chg_1w=chg1w,
            ))

    return signals


# ── Master signal runner ──────────────────────────────────────────────────────

def generate_all_signals(save: bool = True) -> list[dict]:
    """Generate signals for all watched markets across all report types."""
    all_signals: list[dict] = []

    for code in WATCHED_MARKETS:
        try:
            all_signals.extend(signals_from_legacy(code))
        except Exception as e:
            logger.warning("Legacy signals failed for %s: %s", code, e)

        try:
            all_signals.extend(signals_from_disaggregated(code))
        except Exception as e:
            logger.warning("Disagg signals failed for %s: %s", code, e)

        try:
            all_signals.extend(signals_from_financial(code))
        except Exception as e:
            logger.warning("Financial signals failed for %s: %s", code, e)

    logger.info("Total signals generated: %d", len(all_signals))

    if save and all_signals:
        save_signals(all_signals)

    return all_signals
