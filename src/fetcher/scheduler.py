"""APScheduler-based scheduler that pulls fresh COT data every Friday after CFTC release."""
from __future__ import annotations

import logging

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from src.config import SCHEDULER_TIMEZONE

logger = logging.getLogger(__name__)


def _run_weekly_update() -> None:
    """Full pipeline: fetch → parse → store → analyze → alert."""
    from src.parser.cot_parser import parse_legacy_rows, parse_disaggregated_rows, parse_financial_rows
    from src.fetcher.cot_fetcher import fetch_latest_legacy, fetch_latest_disaggregated, fetch_latest_financial
    from src.storage.db import upsert_legacy, upsert_disaggregated, upsert_financial
    from src.analyzer.signals import generate_all_signals
    from src.alerts.notifier import dispatch_new_signals

    logger.info("=== Weekly COT update started ===")

    # Legacy
    try:
        raw = fetch_latest_legacy(weeks=4)
        rows = parse_legacy_rows(raw)
        n = upsert_legacy(rows)
        logger.info("Legacy: %d new rows", n)
    except Exception as e:
        logger.error("Legacy fetch failed: %s", e)

    # Disaggregated
    try:
        raw = fetch_latest_disaggregated(weeks=4)
        rows = parse_disaggregated_rows(raw)
        n = upsert_disaggregated(rows)
        logger.info("Disaggregated: %d new rows", n)
    except Exception as e:
        logger.error("Disaggregated fetch failed: %s", e)

    # Financial (TFF)
    try:
        raw = fetch_latest_financial(weeks=4)
        rows = parse_financial_rows(raw)
        n = upsert_financial(rows)
        logger.info("Financial (TFF): %d new rows", n)
    except Exception as e:
        logger.error("Financial fetch failed: %s", e)

    # Signals
    try:
        signals = generate_all_signals()
        logger.info("Generated %d signals", len(signals))
        dispatch_new_signals(signals)
    except Exception as e:
        logger.error("Signal generation failed: %s", e)

    logger.info("=== Weekly COT update complete ===")


def start_scheduler() -> None:
    """Start blocking scheduler. CFTC releases COT every Friday ~3:30 PM ET."""
    scheduler = BlockingScheduler(timezone=SCHEDULER_TIMEZONE)

    # Run every Friday at 16:00 ET (after 3:30 PM release + buffer)
    scheduler.add_job(
        _run_weekly_update,
        CronTrigger(day_of_week="fri", hour=16, minute=0, timezone=SCHEDULER_TIMEZONE),
        id="weekly_cot_update",
        name="Weekly COT data update",
        misfire_grace_time=3600,
        coalesce=True,
    )

    logger.info("Scheduler started — will run every Friday at 16:00 %s", SCHEDULER_TIMEZONE)
    scheduler.start()
