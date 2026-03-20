# CLAUDE.md — AI Assistant Guide for CFTC COT Monitor

## Project Overview

**CFTC COT Monitor** is a Python application that fetches CFTC Commitments of Traders (COT) reports, stores them in a local database, analyzes positioning for investment signals, and displays results in a Streamlit dashboard.

**Purpose:** Monitor speculator and commercial hedger positioning across **49 futures markets in 8 sectors** (Grains, Softs, Livestock, Energy, Metals, Equities, Rates, FX) to identify crowded trades and high-conviction reversal setups.

---

## Architecture

```
CFTC-Filing/
├── src/
│   ├── config.py              # Central config (env vars, watched markets, thresholds)
│   ├── fetcher/               # CFTC data download (Socrata API + bulk ZIP)
│   │   ├── cot_fetcher.py     # fetch_latest_* and download_bulk functions
│   │   └── scheduler.py      # APScheduler weekly job (Friday 4 PM ET)
│   ├── parser/
│   │   ├── cot_parser.py      # Socrata API dict → DB-ready dict (3 report types)
│   │   └── normalizer.py      # Enrich DataFrames with derived columns
│   ├── storage/
│   │   ├── models.py          # SQLAlchemy ORM: COTLegacy, COTDisaggregated, COTFinancial, Signal, AlertLog
│   │   └── db.py              # Engine, sessions, upsert helpers, query helpers
│   ├── analyzer/
│   │   ├── positioning.py     # COT Index (rolling percentile), metrics per report type
│   │   ├── sentiment.py       # Composite sentiment score (0–100) + interpretation
│   │   ├── signals.py         # Signal generation for all markets (extreme, divergence, momentum)
│   │   ├── backtesting.py     # Phase 3: historical signal vs price return analysis
│   │   └── multi_asset.py     # Phase 4: correlation panel, Risk-On/Off, confluence signals
│   ├── alerts/
│   │   └── notifier.py        # Telegram + email + console dispatch with deduplication
│   └── dashboard/
│       ├── app.py             # Streamlit app (5 pages, cached data loading)
│       └── charts.py          # Plotly chart builders (COT Index, net position, heatmap, etc.)
├── scripts/
│   ├── init_db.py             # One-time DB init
│   └── backfill.py            # Historical data load (run once)
├── tests/                     # pytest test suite
├── data/                      # SQLite DB + cached bulk ZIPs (git-ignored)
├── main.py                    # CLI entry point
├── requirements.txt
└── .env.example
```

---

## Data Flow

```
CFTC Socrata API / Bulk ZIPs
        ↓
  cot_fetcher.py          (download)
        ↓
  cot_parser.py           (parse raw → typed dicts)
        ↓
  storage/db.py           (upsert into SQLite)
        ↓
  analyzer/positioning.py (compute COT Index, metrics)
        ↓
  analyzer/signals.py     (generate signals)
        ↓
  alerts/notifier.py      (dispatch Telegram/email)
        ↓
  dashboard/app.py        (display in Streamlit)
```

---

## Key Concepts

### COT Index
The core indicator — rolling percentile of net speculative position over a configurable lookback window (default 156 weeks / 3 years).
- **>80** = extreme long (contrarian **bearish** signal)
- **<20** = extreme short (contrarian **bullish** signal)
- Implemented in `src/analyzer/positioning.py:cot_index()`

### Report Types
| Type | Class | Markets |
|------|-------|---------|
| Legacy COT | `COTLegacy` | All futures |
| Disaggregated | `COTDisaggregated` | Physical commodities |
| TFF (Financial) | `COTFinancial` | Financial futures (FX, rates, equity index) |

### Signal Types
- `extreme_long` / `extreme_short` — single-market positioning extremes
- `divergence` — Producers vs Managed Money at opposite extremes (high conviction)
- `momentum_acceleration` — consecutive weeks trending same direction (≥4 weeks)
- `reversal_setup` — COT Index just crossed back from extreme zone
- `multi_asset_confluence` — correlated markets confirm signal

---

## Development Workflow

### Git Conventions
```
feat:     new feature
fix:      bug fix
refactor: code restructure without behavior change
test:     add/update tests
docs:     documentation changes
chore:    dependencies, config
```

Branch pattern: `claude/<description>-<session-id>` for AI branches, `feature/<description>` for human branches.

### Running the Project

```bash
# Setup
pip install -r requirements.txt
cp .env.example .env

# Initialize DB
python main.py init

# Load data (first time)
python main.py backfill

# Regular update
python main.py fetch

# Generate signals
python main.py signals

# Start dashboard
python main.py dashboard       # → http://localhost:8501

# Run tests
pytest tests/ -v
```

### Environment Variables
All config is in `.env` (see `.env.example`). Key variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `sqlite:///./data/cftc.db` | DB connection string |
| `COT_INDEX_LOOKBACK` | `156` | Weeks for percentile window |
| `EXTREME_LONG_THRESHOLD` | `80` | Alert above this percentile |
| `EXTREME_SHORT_THRESHOLD` | `20` | Alert below this percentile |
| `TELEGRAM_BOT_TOKEN` | — | Optional Telegram alerts |
| `SOCRATA_APP_TOKEN` | — | Optional, increases API rate limits |

---

## Code Conventions

### Adding a New Market
1. Add `"CONTRACT_CODE": "Market Name"` to `WATCHED_MARKETS` in `src/config.py`
2. Add its yfinance ticker to `PRICE_TICKERS` in `src/config.py`
3. Add the contract code to the appropriate sector list in `SECTOR_GROUPS` in `src/dashboard/app.py` (keeps sidebar and tab filters consistent)
4. Re-run `python main.py backfill` to load historical data

### Adding a New Signal Type
1. Implement the detection logic in `src/analyzer/signals.py`
2. Call it from `generate_all_signals()`
3. Add the signal type to the dashboard filter in `src/dashboard/app.py`
4. Write a unit test in `tests/test_signals.py`

### Database Changes
- Add new columns to the relevant model in `src/storage/models.py`
- `init_db()` uses `create_all()` — for existing DBs, manually `ALTER TABLE` or delete and reinitialize

### Parser Field Mapping
Socrata API uses inconsistent column naming (e.g., `noncomm_postions_spread_all` with typo). The parser handles both variants. When CFTC changes field names, update `src/parser/cot_parser.py`.

---

## Testing Guidelines

- All signal detection logic must have unit tests with mocked DB calls
- Parser tests cover: valid rows, missing required fields, edge cases (None, empty string, "nan")
- Use `unittest.mock.patch` to mock `get_legacy_df` / `get_disaggregated_df` in signal tests
- Do not make real network calls in tests

---

## Notes for AI Assistants

1. **Percentile interpretation**: High COT Index = crowded longs = **bearish** contrarian signal. This counter-intuitive relationship is intentional and correct.
2. **Socrata column names**: CFTC's own column names have typos (e.g., `noncomm_postions_spread_all`). The parser deliberately handles both the typo and the correct spelling.
3. **No live trading**: This tool generates positioning analysis signals only. Do not add order execution, brokerage API calls, or automated trading logic.
4. **Data quality**: COT data is released weekly with a 3-day lag (Tuesday data → Friday release). The scheduler accounts for this.
5. **SQLite vs PostgreSQL**: The default `DATABASE_URL` uses SQLite. Switch to PostgreSQL + TimescaleDB for production use by changing `DATABASE_URL` in `.env`.
6. **Watched markets list**: `WATCHED_MARKETS` in `config.py` is the single source of truth for which markets are monitored. `SECTOR_GROUPS` in `src/dashboard/app.py` mirrors it for UI grouping — keep them in sync when adding/removing markets.
7. **Dashboard sector grouping**: The `SECTOR_GROUPS` dict in `app.py` drives the sidebar sector filter, Market Overview tabs, Signals sector filter, and Correlation Matrix sector selector. It is intentionally separate from `config.py` (UI concern only).
