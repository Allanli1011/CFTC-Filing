"""Parse raw CFTC COT data (Socrata API dicts or bulk CSV DataFrames) into DB-ready dicts."""
from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)


def _safe_int(val: Any) -> int | None:
    try:
        return int(float(str(val))) if val not in (None, "", "nan") else None
    except (ValueError, TypeError):
        return None


def _safe_float(val: Any) -> float | None:
    try:
        return float(str(val)) if val not in (None, "", "nan") else None
    except (ValueError, TypeError):
        return None


def _parse_date(val: Any) -> date | None:
    if val is None:
        return None
    if isinstance(val, (date, datetime)):
        return val if isinstance(val, date) else val.date()
    s = str(val).split("T")[0]
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%y%m%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    logger.warning("Could not parse date: %r", val)
    return None


# ── Legacy COT ────────────────────────────────────────────────────────────────

def _legacy_row_from_api(r: dict) -> dict | None:
    """Map a Socrata API row to COTLegacy model fields."""
    rd = _parse_date(r.get("report_date_as_yyyy_mm_dd") or r.get("as_of_date_in_form_yymmdd"))
    code = r.get("cftc_contract_market_code", "").strip()
    if not rd or not code:
        return None

    nc_long  = _safe_int(r.get("noncomm_positions_long_all"))
    nc_short = _safe_int(r.get("noncomm_positions_short_all"))
    c_long   = _safe_int(r.get("comm_positions_long_all"))
    c_short  = _safe_int(r.get("comm_positions_short_all"))

    return {
        "contract_code":      code,
        "market_name":        r.get("market_and_exchange_names", "").strip(),
        "report_date":        rd,
        "open_interest":      _safe_int(r.get("open_interest_all")),
        "noncomm_long":       nc_long,
        "noncomm_short":      nc_short,
        "noncomm_spread":     _safe_int(r.get("noncomm_postions_spread_all") or r.get("noncomm_positions_spread_all")),
        "noncomm_net":        (nc_long - nc_short) if nc_long is not None and nc_short is not None else None,
        "comm_long":          c_long,
        "comm_short":         c_short,
        "comm_net":           (c_long - c_short) if c_long is not None and c_short is not None else None,
        "nonrept_long":       _safe_int(r.get("nonrept_positions_long_all")),
        "nonrept_short":      _safe_int(r.get("nonrept_positions_short_all")),
        "chg_open_interest":  _safe_int(r.get("change_in_open_interest_all")),
        "chg_noncomm_long":   _safe_int(r.get("change_in_noncomm_long_all")),
        "chg_noncomm_short":  _safe_int(r.get("change_in_noncomm_short_all")),
        "chg_comm_long":      _safe_int(r.get("change_in_comm_long_all")),
        "chg_comm_short":     _safe_int(r.get("change_in_comm_short_all")),
        "pct_noncomm_long":   _safe_float(r.get("pct_of_oi_noncomm_long_all")),
        "pct_noncomm_short":  _safe_float(r.get("pct_of_oi_noncomm_short_all")),
        "pct_comm_long":      _safe_float(r.get("pct_of_oi_comm_long_all")),
        "pct_comm_short":     _safe_float(r.get("pct_of_oi_comm_short_all")),
        "traders_total":          _safe_int(r.get("traders_tot_all")),
        "traders_noncomm_long":   _safe_int(r.get("traders_noncomm_long_all")),
        "traders_noncomm_short":  _safe_int(r.get("traders_noncomm_short_all")),
        "traders_comm_long":      _safe_int(r.get("traders_comm_long_all")),
        "traders_comm_short":     _safe_int(r.get("traders_comm_short_all")),
    }


def _legacy_row_from_df_row(r: pd.Series) -> dict | None:
    """Map a bulk CSV row (column names lowercased) to COTLegacy model fields."""
    rd = _parse_date(r.get("report_date_as_yyyy-mm-dd") or r.get("as_of_date_in_form_yymmdd"))
    code = str(r.get("cftc_contract_market_code", "")).strip()
    if not rd or not code:
        return None

    def gi(col: str) -> int | None:
        return _safe_int(r.get(col))

    def gf(col: str) -> float | None:
        return _safe_float(r.get(col))

    nc_long  = gi("noncomm_positions_long_all")
    nc_short = gi("noncomm_positions_short_all")
    c_long   = gi("comm_positions_long_all")
    c_short  = gi("comm_positions_short_all")

    return {
        "contract_code":     code,
        "market_name":       str(r.get("market_and_exchange_names", "")).strip(),
        "report_date":       rd,
        "open_interest":     gi("open_interest_all"),
        "noncomm_long":      nc_long,
        "noncomm_short":     nc_short,
        "noncomm_spread":    gi("noncomm_postions_spread_all") or gi("noncomm_positions_spread_all"),
        "noncomm_net":       (nc_long - nc_short) if nc_long is not None and nc_short is not None else None,
        "comm_long":         c_long,
        "comm_short":        c_short,
        "comm_net":          (c_long - c_short) if c_long is not None and c_short is not None else None,
        "nonrept_long":      gi("nonrept_positions_long_all"),
        "nonrept_short":     gi("nonrept_positions_short_all"),
        "chg_open_interest": gi("change_in_open_interest_all"),
        "chg_noncomm_long":  gi("change_in_noncomm_long_all"),
        "chg_noncomm_short": gi("change_in_noncomm_short_all"),
        "chg_comm_long":     gi("change_in_comm_long_all"),
        "chg_comm_short":    gi("change_in_comm_short_all"),
        "pct_noncomm_long":  gf("pct_of_oi_noncomm_long_all"),
        "pct_noncomm_short": gf("pct_of_oi_noncomm_short_all"),
        "pct_comm_long":     gf("pct_of_oi_comm_long_all"),
        "pct_comm_short":    gf("pct_of_oi_comm_short_all"),
        "traders_total":         gi("traders_tot_all"),
        "traders_noncomm_long":  gi("traders_noncomm_long_all"),
        "traders_noncomm_short": gi("traders_noncomm_short_all"),
        "traders_comm_long":     gi("traders_comm_long_all"),
        "traders_comm_short":    gi("traders_comm_short_all"),
    }


def parse_legacy_rows(api_rows: list[dict]) -> list[dict]:
    out = []
    for r in api_rows:
        parsed = _legacy_row_from_api(r)
        if parsed:
            out.append(parsed)
    logger.info("Parsed %d/%d Legacy rows", len(out), len(api_rows))
    return out


def parse_legacy_df(df: pd.DataFrame, watched_codes: list[str] | None = None) -> list[dict]:
    df.columns = [c.lower().strip() for c in df.columns]
    if watched_codes:
        col = next((c for c in df.columns if "contract_market_code" in c), None)
        if col:
            df = df[df[col].astype(str).str.strip().isin(watched_codes)]
    out = []
    for _, row in df.iterrows():
        parsed = _legacy_row_from_df_row(row)
        if parsed:
            out.append(parsed)
    return out


# ── Disaggregated COT ─────────────────────────────────────────────────────────

def _disagg_row_from_api(r: dict) -> dict | None:
    rd = _parse_date(r.get("report_date_as_yyyy_mm_dd") or r.get("as_of_date_in_form_yymmdd"))
    code = r.get("cftc_contract_market_code", "").strip()
    if not rd or not code:
        return None

    p_long  = _safe_int(r.get("prod_merc_positions_long_all"))
    p_short = _safe_int(r.get("prod_merc_positions_short_all"))
    s_long  = _safe_int(r.get("swap_positions_long_all"))
    s_short = _safe_int(r.get("swap__positions_short_all") or r.get("swap_positions_short_all"))
    m_long  = _safe_int(r.get("m_money_positions_long_all"))
    m_short = _safe_int(r.get("m_money_positions_short_all"))
    o_long  = _safe_int(r.get("other_rept_positions_long_all"))
    o_short = _safe_int(r.get("other_rept_positions_short_all"))

    def net(l, s):
        return (l - s) if l is not None and s is not None else None

    return {
        "contract_code":  code,
        "market_name":    r.get("market_and_exchange_names", "").strip(),
        "report_date":    rd,
        "open_interest":  _safe_int(r.get("open_interest_all")),
        "prod_long":      p_long,
        "prod_short":     p_short,
        "prod_net":       net(p_long, p_short),
        "swap_long":      s_long,
        "swap_short":     s_short,
        "swap_spread":    _safe_int(r.get("swap__positions_spread_all") or r.get("swap_positions_spread_all")),
        "swap_net":       net(s_long, s_short),
        "mmoney_long":    m_long,
        "mmoney_short":   m_short,
        "mmoney_spread":  _safe_int(r.get("m_money_positions_spread_all")),
        "mmoney_net":     net(m_long, m_short),
        "other_long":     o_long,
        "other_short":    o_short,
        "other_net":      net(o_long, o_short),
        "nonrept_long":   _safe_int(r.get("nonrept_positions_long_all")),
        "nonrept_short":  _safe_int(r.get("nonrept_positions_short_all")),
        "chg_open_interest": _safe_int(r.get("change_in_open_interest_all")),
        "chg_prod_long":     _safe_int(r.get("change_in_prod_merc_long_all")),
        "chg_prod_short":    _safe_int(r.get("change_in_prod_merc_short_all")),
        "chg_swap_long":     _safe_int(r.get("change_in_swap_long_all")),
        "chg_swap_short":    _safe_int(r.get("change_in_swap_short_all")),
        "chg_mmoney_long":   _safe_int(r.get("change_in_m_money_long_all")),
        "chg_mmoney_short":  _safe_int(r.get("change_in_m_money_short_all")),
    }


def parse_disaggregated_rows(api_rows: list[dict]) -> list[dict]:
    out = [_disagg_row_from_api(r) for r in api_rows]
    out = [x for x in out if x]
    logger.info("Parsed %d/%d Disaggregated rows", len(out), len(api_rows))
    return out


# ── TFF (Traders in Financial Futures) ───────────────────────────────────────

def _tff_row_from_api(r: dict) -> dict | None:
    rd = _parse_date(r.get("report_date_as_yyyy_mm_dd") or r.get("as_of_date_in_form_yymmdd"))
    code = r.get("cftc_contract_market_code", "").strip()
    if not rd or not code:
        return None

    d_long  = _safe_int(r.get("dealer_positions_long_all"))
    d_short = _safe_int(r.get("dealer_positions_short_all"))
    a_long  = _safe_int(r.get("asset_mgr_positions_long_all"))
    a_short = _safe_int(r.get("asset_mgr_positions_short_all"))
    l_long  = _safe_int(r.get("lev_money_positions_long_all"))
    l_short = _safe_int(r.get("lev_money_positions_short_all"))
    o_long  = _safe_int(r.get("other_rept_positions_long_all"))
    o_short = _safe_int(r.get("other_rept_positions_short_all"))

    def net(l, s):
        return (l - s) if l is not None and s is not None else None

    return {
        "contract_code":  code,
        "market_name":    r.get("market_and_exchange_names", "").strip(),
        "report_date":    rd,
        "open_interest":  _safe_int(r.get("open_interest_all")),
        "dealer_long":    d_long,
        "dealer_short":   d_short,
        "dealer_spread":  _safe_int(r.get("dealer_positions_spread_all")),
        "dealer_net":     net(d_long, d_short),
        "assetmgr_long":   a_long,
        "assetmgr_short":  a_short,
        "assetmgr_spread": _safe_int(r.get("asset_mgr_positions_spread_all")),
        "assetmgr_net":    net(a_long, a_short),
        "levmoney_long":   l_long,
        "levmoney_short":  l_short,
        "levmoney_spread": _safe_int(r.get("lev_money_positions_spread_all")),
        "levmoney_net":    net(l_long, l_short),
        "other_long":     o_long,
        "other_short":    o_short,
        "other_net":      net(o_long, o_short),
        "nonrept_long":   _safe_int(r.get("nonrept_positions_long_all")),
        "nonrept_short":  _safe_int(r.get("nonrept_positions_short_all")),
        "chg_open_interest":  _safe_int(r.get("change_in_open_interest_all")),
        "chg_dealer_long":    _safe_int(r.get("change_in_dealer_long_all")),
        "chg_dealer_short":   _safe_int(r.get("change_in_dealer_short_all")),
        "chg_assetmgr_long":  _safe_int(r.get("change_in_asset_mgr_long_all")),
        "chg_assetmgr_short": _safe_int(r.get("change_in_asset_mgr_short_all")),
        "chg_levmoney_long":  _safe_int(r.get("change_in_lev_money_long_all")),
        "chg_levmoney_short": _safe_int(r.get("change_in_lev_money_short_all")),
    }


def parse_financial_rows(api_rows: list[dict]) -> list[dict]:
    out = [_tff_row_from_api(r) for r in api_rows]
    out = [x for x in out if x]
    logger.info("Parsed %d/%d TFF rows", len(out), len(api_rows))
    return out
