"""
Backfill historical COT data from CFTC bulk ZIP files.

Usage:
    python scripts/backfill.py                    # all three report types, historical + current
    python scripts/backfill.py --type legacy      # only legacy
    python scripts/backfill.py --type disaggregated --period hist
    python scripts/backfill.py --type financial   --period current
"""
import sys
import argparse
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def backfill_legacy(period: str, watched_codes: list[str]) -> None:
    from src.fetcher.cot_fetcher import download_bulk, read_bulk_csv
    from src.parser.cot_parser import parse_legacy_df
    from src.storage.db import upsert_legacy

    path = download_bulk("legacy", period)
    df   = read_bulk_csv(path)
    rows = parse_legacy_df(df, watched_codes=watched_codes)
    n    = upsert_legacy(rows)
    logger.info("Legacy %s: inserted %d rows", period, n)


def backfill_disaggregated(period: str, watched_codes: list[str]) -> None:
    from src.fetcher.cot_fetcher import download_bulk, read_bulk_csv
    from src.parser.cot_parser import parse_legacy_df  # re-use, fields match enough
    from src.storage.db import upsert_disaggregated
    from src.parser.cot_parser import parse_legacy_rows
    import pandas as pd

    # Disaggregated needs its own parser via API, bulk uses different column names.
    # For bulk backfill we go via Socrata for simplicity (slower but correct).
    from src.fetcher.cot_fetcher import fetch_latest_disaggregated
    from src.parser.cot_parser import parse_disaggregated_rows

    logger.info("Disaggregated bulk via Socrata (full history may take a few minutes)...")
    rows_raw = fetch_latest_disaggregated(codes=watched_codes, weeks=600)
    rows     = parse_disaggregated_rows(rows_raw)
    n        = upsert_disaggregated(rows)
    logger.info("Disaggregated: inserted %d rows", n)


def backfill_financial(period: str, watched_codes: list[str]) -> None:
    from src.fetcher.cot_fetcher import fetch_latest_financial
    from src.parser.cot_parser import parse_financial_rows
    from src.storage.db import upsert_financial

    logger.info("Financial TFF via Socrata...")
    rows_raw = fetch_latest_financial(codes=watched_codes, weeks=600)
    rows     = parse_financial_rows(rows_raw)
    n        = upsert_financial(rows)
    logger.info("Financial: inserted %d rows", n)


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill CFTC COT historical data")
    parser.add_argument("--type", choices=["legacy", "disaggregated", "financial", "all"],
                        default="all", help="Which report type to backfill")
    parser.add_argument("--period", choices=["hist", "current", "both"],
                        default="both", help="Historical ZIP, current year ZIP, or both")
    args = parser.parse_args()

    from src.storage.db import init_db
    from src.config import WATCHED_MARKETS
    init_db()

    codes   = list(WATCHED_MARKETS.keys())
    periods = ["hist", "current"] if args.period == "both" else [args.period]

    if args.type in ("legacy", "all"):
        for period in periods:
            try:
                backfill_legacy(period, codes)
            except Exception as e:
                logger.error("Legacy %s failed: %s", period, e)

    if args.type in ("disaggregated", "all"):
        try:
            backfill_disaggregated("hist", codes)
        except Exception as e:
            logger.error("Disaggregated backfill failed: %s", e)

    if args.type in ("financial", "all"):
        try:
            backfill_financial("hist", codes)
        except Exception as e:
            logger.error("Financial backfill failed: %s", e)

    logger.info("Backfill complete.")


if __name__ == "__main__":
    main()
