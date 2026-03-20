"""Tests for COT data parsers."""
import pytest
from datetime import date

from src.parser.cot_parser import (
    _safe_int, _safe_float, _parse_date,
    parse_legacy_rows, parse_disaggregated_rows, parse_financial_rows,
)


# ── Utility helpers ───────────────────────────────────────────────────────────

def test_safe_int_valid():
    assert _safe_int("12345") == 12345
    assert _safe_int(99.9) == 99
    assert _safe_int("-500") == -500


def test_safe_int_invalid():
    assert _safe_int(None) is None
    assert _safe_int("") is None
    assert _safe_int("nan") is None
    assert _safe_int("abc") is None


def test_safe_float_valid():
    assert _safe_float("3.14") == pytest.approx(3.14)
    assert _safe_float(0) == pytest.approx(0.0)


def test_safe_float_invalid():
    assert _safe_float(None) is None
    assert _safe_float("N/A") is None


def test_parse_date_iso():
    assert _parse_date("2024-01-05") == date(2024, 1, 5)


def test_parse_date_slash():
    assert _parse_date("01/05/2024") == date(2024, 1, 5)


def test_parse_date_yymmdd():
    assert _parse_date("240105") == date(2024, 1, 5)


def test_parse_date_datetime_obj():
    from datetime import datetime
    assert _parse_date(datetime(2024, 3, 15)) == date(2024, 3, 15)


def test_parse_date_invalid():
    assert _parse_date("not-a-date") is None
    assert _parse_date(None) is None


# ── Legacy parser ─────────────────────────────────────────────────────────────

def _make_legacy_api_row(**overrides) -> dict:
    base = {
        "cftc_contract_market_code": "088691",
        "market_and_exchange_names": "GOLD - COMMODITY EXCHANGE INC.",
        "report_date_as_yyyy_mm_dd": "2024-01-05",
        "open_interest_all": "450000",
        "noncomm_positions_long_all": "220000",
        "noncomm_positions_short_all": "80000",
        "noncomm_postions_spread_all": "30000",
        "comm_positions_long_all": "150000",
        "comm_positions_short_all": "280000",
        "nonrept_positions_long_all": "10000",
        "nonrept_positions_short_all": "20000",
        "change_in_open_interest_all": "5000",
        "change_in_noncomm_long_all": "3000",
        "change_in_noncomm_short_all": "-1000",
        "change_in_comm_long_all": "2000",
        "change_in_comm_short_all": "-500",
        "pct_of_oi_noncomm_long_all": "48.9",
        "pct_of_oi_noncomm_short_all": "17.8",
        "pct_of_oi_comm_long_all": "33.3",
        "pct_of_oi_comm_short_all": "62.2",
        "traders_tot_all": "320",
        "traders_noncomm_long_all": "120",
        "traders_noncomm_short_all": "95",
        "traders_comm_long_all": "60",
        "traders_comm_short_all": "75",
    }
    base.update(overrides)
    return base


def test_parse_legacy_basic():
    rows = parse_legacy_rows([_make_legacy_api_row()])
    assert len(rows) == 1
    row = rows[0]
    assert row["contract_code"] == "088691"
    assert row["report_date"] == date(2024, 1, 5)
    assert row["noncomm_long"] == 220000
    assert row["noncomm_short"] == 80000
    assert row["noncomm_net"] == 140000    # 220000 - 80000
    assert row["comm_net"] == -130000      # 150000 - 280000
    assert row["open_interest"] == 450000


def test_parse_legacy_missing_code():
    row = _make_legacy_api_row(cftc_contract_market_code="")
    result = parse_legacy_rows([row])
    assert result == []


def test_parse_legacy_missing_date():
    row = _make_legacy_api_row(report_date_as_yyyy_mm_dd="")
    result = parse_legacy_rows([row])
    assert result == []


def test_parse_legacy_multiple():
    rows = [_make_legacy_api_row(report_date_as_yyyy_mm_dd=f"2024-0{i}-05") for i in range(1, 4)]
    result = parse_legacy_rows(rows)
    assert len(result) == 3


# ── Disaggregated parser ──────────────────────────────────────────────────────

def _make_disagg_row(**overrides) -> dict:
    base = {
        "cftc_contract_market_code": "088691",
        "market_and_exchange_names": "GOLD",
        "report_date_as_yyyy_mm_dd": "2024-01-05",
        "open_interest_all": "450000",
        "prod_merc_positions_long_all": "100000",
        "prod_merc_positions_short_all": "200000",
        "swap_positions_long_all": "50000",
        "swap__positions_short_all": "40000",
        "swap__positions_spread_all": "5000",
        "m_money_positions_long_all": "180000",
        "m_money_positions_short_all": "60000",
        "m_money_positions_spread_all": "10000",
        "other_rept_positions_long_all": "20000",
        "other_rept_positions_short_all": "30000",
        "nonrept_positions_long_all": "5000",
        "nonrept_positions_short_all": "8000",
        "change_in_open_interest_all": "1000",
        "change_in_prod_merc_long_all": "-2000",
        "change_in_prod_merc_short_all": "3000",
        "change_in_swap_long_all": "500",
        "change_in_swap_short_all": "-200",
        "change_in_m_money_long_all": "4000",
        "change_in_m_money_short_all": "-1500",
    }
    base.update(overrides)
    return base


def test_parse_disaggregated_basic():
    rows = parse_disaggregated_rows([_make_disagg_row()])
    assert len(rows) == 1
    row = rows[0]
    assert row["mmoney_net"] == 120000   # 180000 - 60000
    assert row["prod_net"] == -100000    # 100000 - 200000


# ── TFF parser ────────────────────────────────────────────────────────────────

def _make_tff_row(**overrides) -> dict:
    base = {
        "cftc_contract_market_code": "13874A",
        "market_and_exchange_names": "E-MINI S&P 500",
        "report_date_as_yyyy_mm_dd": "2024-01-05",
        "open_interest_all": "2500000",
        "dealer_positions_long_all": "300000",
        "dealer_positions_short_all": "450000",
        "dealer_positions_spread_all": "50000",
        "asset_mgr_positions_long_all": "900000",
        "asset_mgr_positions_short_all": "400000",
        "asset_mgr_positions_spread_all": "100000",
        "lev_money_positions_long_all": "600000",
        "lev_money_positions_short_all": "800000",
        "lev_money_positions_spread_all": "50000",
        "other_rept_positions_long_all": "100000",
        "other_rept_positions_short_all": "80000",
        "nonrept_positions_long_all": "50000",
        "nonrept_positions_short_all": "70000",
        "change_in_open_interest_all": "10000",
        "change_in_dealer_long_all": "-5000",
        "change_in_dealer_short_all": "8000",
        "change_in_asset_mgr_long_all": "15000",
        "change_in_asset_mgr_short_all": "-3000",
        "change_in_lev_money_long_all": "-20000",
        "change_in_lev_money_short_all": "10000",
    }
    base.update(overrides)
    return base


def test_parse_financial_basic():
    rows = parse_financial_rows([_make_tff_row()])
    assert len(rows) == 1
    row = rows[0]
    assert row["dealer_net"] == -150000    # 300000 - 450000
    assert row["assetmgr_net"] == 500000   # 900000 - 400000
    assert row["levmoney_net"] == -200000  # 600000 - 800000
