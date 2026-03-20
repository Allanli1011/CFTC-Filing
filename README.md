# CFTC COT Monitor

Monitor CFTC Commitments of Traders (COT) reports and generate investment signals across 14 key futures markets.

## What It Does

| Phase | Feature |
|-------|---------|
| **1** | Auto-fetch COT data from CFTC (Socrata API + bulk ZIP) — weekly scheduled |
| **2** | COT Index (rolling percentile), extreme positioning alerts (Telegram/email) |
| **3** | Smart money vs speculator divergence signals, backtesting vs price returns |
| **4** | Multi-asset correlation, Risk-On/Off indicator, sector confluence signals |

## Covered Markets

Gold, Silver, Copper, Crude Oil, Natural Gas, S&P 500, Euro FX, JPY, GBP, 10-Year T-Note, 2-Year T-Note, Corn, Soybeans, Wheat

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Copy and configure environment
cp .env.example .env
# (optional: add Telegram token, email credentials)

# 3. Initialize database
python main.py init

# 4. Load historical data (~3 years)
python main.py backfill

# 5. Launch dashboard
python main.py dashboard
```

Dashboard runs at **http://localhost:8501**

## Commands

```bash
python main.py init          # Create database tables
python main.py fetch         # Pull latest 8 weeks from CFTC
python main.py backfill      # Full historical backfill (run once)
python main.py signals       # Generate and print signals to console
python main.py schedule      # Start auto-update every Friday 4 PM ET
python main.py dashboard     # Launch Streamlit dashboard
```

## Dashboard Pages

- **Market Overview** — COT Index heatmap for all 14 markets
- **Positioning Analysis** — Per-market deep dive (Legacy, Disaggregated, TFF tabs)
- **Signals & Alerts** — Filterable signal table with strength and direction
- **Backtesting** — Historical signal hit rate vs price returns (via yfinance)
- **Multi-Asset Analysis** — Correlation matrix, Risk-On/Off indicator, confluence signals

## Key Signals Explained

| Signal | Meaning |
|--------|---------|
| `extreme_long` | Speculator net longs at >80th percentile — **contrarian bearish** |
| `extreme_short` | Speculator net shorts at <20th percentile — **contrarian bullish** |
| `divergence` | Producers (smart money) opposite to Managed Money at extremes — **high conviction** |
| `momentum_acceleration` | Net position trending same direction 4+ consecutive weeks |
| `reversal_setup` | COT Index just crossed back from extreme zone |
| `multi_asset_confluence` | Correlated markets confirm the same signal |

## Alerts Setup

**Telegram:**
1. Create a bot via [@BotFather](https://t.me/BotFather)
2. Set `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` in `.env`

**Email:**
1. Set `SMTP_*` and `ALERT_EMAIL_TO` in `.env`

## Running Tests

```bash
pytest tests/ -v
```

## Project Structure

```
CFTC-Filing/
├── src/
│   ├── config.py              # All configuration
│   ├── fetcher/               # CFTC data download (API + bulk ZIP)
│   ├── parser/                # Raw data → DB-ready dicts
│   ├── storage/               # SQLAlchemy models + CRUD
│   ├── analyzer/
│   │   ├── positioning.py     # COT Index, percentile metrics
│   │   ├── sentiment.py       # Composite sentiment score
│   │   ├── signals.py         # Signal generation (all types)
│   │   ├── backtesting.py     # Phase 3: historical signal performance
│   │   └── multi_asset.py     # Phase 4: cross-market analysis
│   ├── alerts/
│   │   └── notifier.py        # Telegram + email dispatch
│   └── dashboard/
│       ├── app.py             # Streamlit dashboard (5 pages)
│       └── charts.py          # Plotly chart builders
├── scripts/
│   ├── init_db.py
│   └── backfill.py
├── tests/
├── data/                      # SQLite database + cached ZIPs
├── main.py                    # CLI entry point
├── requirements.txt
└── .env.example
```

## Disclaimer

COT data is a sentiment/positioning indicator, not investment advice. Past signal performance does not guarantee future results.
