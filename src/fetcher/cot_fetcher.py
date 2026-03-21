"""Download COT data from CFTC — both bulk historical ZIPs and incremental Socrata API."""
from __future__ import annotations

import io
import logging
import zipfile
from datetime import date, datetime
from pathlib import Path

import httpx
import pandas as pd

from src.config import (
    DATA_DIR,
    SOCRATA_APP_TOKEN,
    SOCRATA_BASE_URL,
    SOCRATA_LEGACY_FUTURES,
    SOCRATA_DISAGGREGATED,
    SOCRATA_TFF,
    CFTC_BULK_BASE,
    WATCHED_MARKETS,
)

logger = logging.getLogger(__name__)

# ── Socrata API ───────────────────────────────────────────────────────────────

_SOCRATA_HEADERS = {"X-App-Token": SOCRATA_APP_TOKEN} if SOCRATA_APP_TOKEN else {}
_PAGE = 5000  # max rows per Socrata request


def _socrata_url(dataset_id: str) -> str:
    return f"{SOCRATA_BASE_URL}/{dataset_id}.json"


def _fetch_socrata(dataset_id: str, where: str | None = None, limit: int = _PAGE) -> list[dict]:
    """Fetch rows from a Socrata dataset with optional $where filter, up to total limit."""
    params: dict[str, str | int] = {"$order": "report_date_as_yyyy_mm_dd DESC"}
    if where:
        params["$where"] = where

    rows: list[dict] = []
    offset = 0
    with httpx.Client(timeout=60, headers=_SOCRATA_HEADERS) as client:
        while len(rows) < limit:
            batch_size = min(_PAGE, limit - len(rows))
            params["$limit"] = batch_size
            params["$offset"] = offset
            
            resp = client.get(_socrata_url(dataset_id), params=params)
            resp.raise_for_status()
            batch = resp.json()
            if not batch:
                break
            rows.extend(batch)
            if len(batch) < batch_size:
                break
            offset += len(batch)
    return rows


def fetch_latest_legacy(codes: list[str] | None = None, weeks: int = 52) -> list[dict]:
    """Fetch last N weeks of Legacy COT from Socrata for watched markets."""
    codes = codes or list(WATCHED_MARKETS.keys())
    code_list = ", ".join(f"'{c}'" for c in codes)
    where = f"cftc_contract_market_code in({code_list})"
    rows = _fetch_socrata(SOCRATA_LEGACY_FUTURES, where=where, limit=len(codes) * weeks + 100)
    logger.info("Fetched %d Legacy COT rows from Socrata", len(rows))
    return rows


def fetch_latest_disaggregated(codes: list[str] | None = None, weeks: int = 52) -> list[dict]:
    codes = codes or list(WATCHED_MARKETS.keys())
    code_list = ", ".join(f"'{c}'" for c in codes)
    where = f"cftc_contract_market_code in({code_list})"
    rows = _fetch_socrata(SOCRATA_DISAGGREGATED, where=where, limit=len(codes) * weeks + 100)
    logger.info("Fetched %d Disaggregated COT rows from Socrata", len(rows))
    return rows


def fetch_latest_financial(codes: list[str] | None = None, weeks: int = 52) -> list[dict]:
    codes = codes or list(WATCHED_MARKETS.keys())
    code_list = ", ".join(f"'{c}'" for c in codes)
    where = f"cftc_contract_market_code in({code_list})"
    rows = _fetch_socrata(SOCRATA_TFF, where=where, limit=len(codes) * weeks + 100)
    logger.info("Fetched %d TFF COT rows from Socrata", len(rows))
    return rows


# ── Bulk Historical Download ──────────────────────────────────────────────────

_BULK_URLS: dict[str, dict[str, str]] = {
    "legacy": {
        "hist": f"{CFTC_BULK_BASE}/fut_fin_txt_hist_2010_2025.zip",
        "current": f"{CFTC_BULK_BASE}/fut_fin_txt_{date.today().year}.zip",
    },
    "disaggregated": {
        "hist": f"{CFTC_BULK_BASE}/fut_disagg_txt_hist_2006_2025.zip",
        "current": f"{CFTC_BULK_BASE}/fut_disagg_txt_{date.today().year}.zip",
    },
    "financial": {
        "hist": f"{CFTC_BULK_BASE}/fin_fut_txt_hist_2010_2025.zip",
        "current": f"{CFTC_BULK_BASE}/fin_fut_txt_{date.today().year}.zip",
    },
}


def _cache_path(report_type: str, period: str) -> Path:
    return DATA_DIR / f"bulk_{report_type}_{period}.zip"


def _download_zip(url: str, dest: Path) -> None:
    logger.info("Downloading %s → %s", url, dest)
    with httpx.Client(timeout=300, follow_redirects=True) as client:
        with client.stream("GET", url) as resp:
            resp.raise_for_status()
            with open(dest, "wb") as f:
                for chunk in resp.iter_bytes(chunk_size=65536):
                    f.write(chunk)


def download_bulk(report_type: str = "legacy", period: str = "hist", force: bool = False) -> Path:
    """Download bulk ZIP file. Returns local path. Skips if cached."""
    url = _BULK_URLS[report_type][period]
    dest = _cache_path(report_type, period)
    if dest.exists() and not force:
        logger.info("Using cached %s", dest)
        return dest
    _download_zip(url, dest)
    return dest


def read_bulk_csv(zip_path: Path) -> pd.DataFrame:
    """Extract and read the CSV file from a CFTC bulk ZIP."""
    with zipfile.ZipFile(zip_path) as zf:
        csv_names = [n for n in zf.namelist() if n.lower().endswith(".txt") or n.lower().endswith(".csv")]
        if not csv_names:
            raise ValueError(f"No CSV/TXT found in {zip_path}")
        with zf.open(csv_names[0]) as f:
            df = pd.read_csv(f, low_memory=False)
    logger.info("Read %d rows from %s", len(df), zip_path)
    return df
