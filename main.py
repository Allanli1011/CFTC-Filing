"""
CFTC COT Monitor — Main Entry Point

Commands:
    python main.py init          Initialize database
    python main.py fetch         Fetch latest COT data (last 8 weeks)
    python main.py backfill      Backfill full history (run once)
    python main.py signals       Generate and print signals
    python main.py schedule      Start weekly auto-update scheduler
    python main.py dashboard     Launch Streamlit dashboard
"""
import os
import sys
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


def cmd_init() -> None:
    from src.storage.db import init_db
    init_db()
    print("Database initialized.")


def cmd_fetch() -> None:
    from datetime import timedelta
    from src.fetcher.cot_fetcher import fetch_latest_legacy, fetch_latest_disaggregated, fetch_latest_financial
    from src.parser.cot_parser import parse_legacy_rows, parse_disaggregated_rows, parse_financial_rows
    from src.storage.db import (
        upsert_legacy, upsert_disaggregated, upsert_financial, init_db,
        get_latest_report_date_legacy, get_latest_report_date_disaggregated,
        get_latest_report_date_financial,
    )

    # Fallback window used when the DB is empty (first run without backfill).
    fallback_weeks = 8
    if len(sys.argv) > 2 and sys.argv[2].isdigit():
        fallback_weeks = int(sys.argv[2])

    init_db()

    # For each table, fetch from the day after its latest stored report date
    # (with a 1-week overlap to catch any late CFTC revisions).
    # If the table is empty, fall back to fetching the last N weeks.
    def _since(latest_date, overlap_weeks: int = 1):
        if latest_date is None:
            return None
        return latest_date - timedelta(weeks=overlap_weeks)

    since_legacy = _since(get_latest_report_date_legacy())
    since_disagg = _since(get_latest_report_date_disaggregated())
    since_fin    = _since(get_latest_report_date_financial())

    label_legacy = f"since {since_legacy}" if since_legacy else f"last {fallback_weeks} weeks"
    label_disagg = f"since {since_disagg}" if since_disagg else f"last {fallback_weeks} weeks"
    label_fin    = f"since {since_fin}"    if since_fin    else f"last {fallback_weeks} weeks"

    print(f"Fetching Legacy COT ({label_legacy})...")
    n1 = upsert_legacy(parse_legacy_rows(
        fetch_latest_legacy(weeks=fallback_weeks, since=since_legacy)
    ))

    print(f"Fetching Disaggregated COT ({label_disagg})...")
    n2 = upsert_disaggregated(parse_disaggregated_rows(
        fetch_latest_disaggregated(weeks=fallback_weeks, since=since_disagg)
    ))

    print(f"Fetching Financial (TFF) COT ({label_fin})...")
    n3 = upsert_financial(parse_financial_rows(
        fetch_latest_financial(weeks=fallback_weeks, since=since_fin)
    ))

    print(f"Done — inserted: {n1} legacy, {n2} disaggregated, {n3} financial rows")


def cmd_backfill() -> None:
    import subprocess
    subprocess.run([sys.executable, "scripts/backfill.py"], check=True)


def cmd_signals() -> None:
    from src.storage.db import init_db
    from src.analyzer.signals import generate_all_signals

    init_db()
    signals = generate_all_signals(save=True)

    if not signals:
        print("No signals generated. Make sure data is loaded first (run: python main.py fetch).")
        return

    print(f"\n{'='*70}")
    print(f"  {len(signals)} COT Signals Generated")
    print(f"{'='*70}")

    for sig in sorted(signals, key=lambda s: s.get("strength", 0), reverse=True):
        icon = "🔴" if sig["direction"] == "bearish" else "🟢" if sig["direction"] == "bullish" else "⚪"
        print(f"\n{icon}  {sig['market_name']} | {sig['signal_type'].upper()} | {sig['direction'].upper()}")
        print(f"   Strength: {sig['strength']:.0f}/100  |  COT Index: {sig.get('cot_index', 'N/A')}")
        print(f"   {sig['description']}")


def cmd_schedule() -> None:
    from src.fetcher.scheduler import start_scheduler
    print("Starting scheduler (Ctrl+C to stop)...")
    start_scheduler()


def cmd_dashboard() -> None:
    import subprocess
    dashboard_path = "src/dashboard/app.py"
    print(f"Launching dashboard: streamlit run {dashboard_path}")
    subprocess.run(["streamlit", "run", dashboard_path], check=True)


COMMANDS = {
    "init":      cmd_init,
    "fetch":     cmd_fetch,
    "backfill":  cmd_backfill,
    "signals":   cmd_signals,
    "schedule":  cmd_schedule,
    "dashboard": cmd_dashboard,
}


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print(__doc__)
        print(f"Available commands: {', '.join(COMMANDS)}")
        sys.exit(1)
    COMMANDS[sys.argv[1]]()
