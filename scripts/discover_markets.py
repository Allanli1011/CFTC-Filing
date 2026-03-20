"""
Discover all markets available in the CFTC COT Socrata API.

Usage:
    python scripts/discover_markets.py                         # show all markets
    python scripts/discover_markets.py --search "gold"         # keyword search
    python scripts/discover_markets.py --type disaggregated    # specific report type
    python scripts/discover_markets.py --export markets.csv    # export to CSV

This script is useful for:
- Finding exact CFTC contract codes for new markets
- Verifying codes before adding to WATCHED_MARKETS in config.py
- Exploring what's available in each report type
"""
import sys
import argparse
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx
import pandas as pd

from src.config import SOCRATA_APP_TOKEN, SOCRATA_BASE_URL

DATASETS = {
    "legacy":        "jun7-i38e",
    "disaggregated": "72hh-3qpy",
    "financial":     "gpe5-46if",
}

HEADERS = {"X-App-Token": SOCRATA_APP_TOKEN} if SOCRATA_APP_TOKEN else {}


def fetch_all_markets(dataset_id: str) -> pd.DataFrame:
    """Query Socrata for all unique market names and contract codes."""
    url = f"{SOCRATA_BASE_URL}/{dataset_id}.json"
    params = {
        "$select": "cftc_contract_market_code, market_and_exchange_names, cftc_commodity_code, cftc_market_code",
        "$group":  "cftc_contract_market_code, market_and_exchange_names, cftc_commodity_code, cftc_market_code",
        "$limit":  "5000",
        "$order":  "market_and_exchange_names ASC",
    }
    with httpx.Client(timeout=60, headers=HEADERS) as client:
        resp = client.get(url, params=params)
        resp.raise_for_status()
        rows = resp.json()

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows).rename(columns={
        "cftc_contract_market_code": "contract_code",
        "market_and_exchange_names": "market_name",
        "cftc_commodity_code":       "commodity_code",
        "cftc_market_code":          "market_code",
    })
    return df.sort_values("market_name").reset_index(drop=True)


def discover(report_type: str = "all", search: str = "", export: str = "") -> None:
    types = list(DATASETS.keys()) if report_type == "all" else [report_type]

    all_rows = []
    for rtype in types:
        print(f"\nQuerying {rtype} report...", flush=True)
        try:
            df = fetch_all_markets(DATASETS[rtype])
            df["report_type"] = rtype
            all_rows.append(df)
            print(f"  Found {len(df)} markets")
        except Exception as e:
            print(f"  ERROR: {e}")

    if not all_rows:
        print("No data found.")
        return

    combined = pd.concat(all_rows, ignore_index=True)

    # Keyword filter
    if search:
        mask = combined["market_name"].str.contains(search, case=False, na=False)
        combined = combined[mask]
        print(f"\nFiltered to {len(combined)} markets matching '{search}'")

    # Print results
    pd.set_option("display.max_colwidth", 60)
    pd.set_option("display.max_rows", 500)
    print("\n" + "=" * 90)
    print(f"{'Contract Code':<16} {'Report Type':<16} {'Market Name'}")
    print("=" * 90)
    for _, row in combined.iterrows():
        code  = row.get("contract_code", "")
        rtype = row.get("report_type", "")
        name  = row.get("market_name", "")
        print(f"{code:<16} {rtype:<16} {name}")

    print(f"\nTotal: {len(combined)} markets across {combined['report_type'].nunique()} report type(s)")

    # Export
    if export:
        path = Path(export)
        combined.to_csv(path, index=False)
        print(f"\nExported to {path.resolve()}")

    # Show which of these are NOT already in WATCHED_MARKETS
    from src.config import WATCHED_MARKETS
    known = set(WATCHED_MARKETS.keys())
    new_codes = combined[~combined["contract_code"].isin(known)]
    if not new_codes.empty and not search:
        print(f"\n── {len(new_codes)} markets NOT yet in WATCHED_MARKETS ──")
        for _, row in new_codes.head(30).iterrows():
            print(f'    "{row["contract_code"]}": "{row["market_name"]}",')
        if len(new_codes) > 30:
            print(f"    ... and {len(new_codes) - 30} more. Use --export to see all.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Discover CFTC COT market codes")
    parser.add_argument("--type",   choices=["legacy", "disaggregated", "financial", "all"],
                        default="all", help="Which report type to query")
    parser.add_argument("--search", default="", help="Keyword to filter market names")
    parser.add_argument("--export", default="", metavar="FILE.csv",
                        help="Export results to CSV file")
    args = parser.parse_args()
    discover(args.type, args.search, args.export)


if __name__ == "__main__":
    main()
