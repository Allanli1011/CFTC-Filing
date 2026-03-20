"""Central configuration loaded from environment / .env file."""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

# ── Database ──────────────────────────────────────────────────────────────────
DATABASE_URL: str = os.getenv("DATABASE_URL", f"sqlite:///{DATA_DIR}/cftc.db")

# ── Socrata API ───────────────────────────────────────────────────────────────
SOCRATA_APP_TOKEN: str = os.getenv("SOCRATA_APP_TOKEN", "")

# Socrata dataset IDs
SOCRATA_LEGACY_FUTURES = "jun7-i38e"
SOCRATA_DISAGGREGATED   = "72hh-3qpy"
SOCRATA_TFF             = "gpe5-46if"
SOCRATA_BASE_URL        = "https://publicreporting.cftc.gov/resource"

# CFTC bulk download base
CFTC_BULK_BASE = "https://www.cftc.gov/files/dea/history"

# ── Alerts ────────────────────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID:   str = os.getenv("TELEGRAM_CHAT_ID", "")

SMTP_HOST:     str = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT:     int = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER:     str = os.getenv("SMTP_USER", "")
SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
ALERT_EMAIL_TO: str = os.getenv("ALERT_EMAIL_TO", "")

# ── Analysis ──────────────────────────────────────────────────────────────────
COT_INDEX_LOOKBACK:       int   = int(os.getenv("COT_INDEX_LOOKBACK", "156"))
EXTREME_LONG_THRESHOLD:   float = float(os.getenv("EXTREME_LONG_THRESHOLD", "80"))
EXTREME_SHORT_THRESHOLD:  float = float(os.getenv("EXTREME_SHORT_THRESHOLD", "20"))

# ── Watched Markets ───────────────────────────────────────────────────────────
# CFTC contract codes → display name
WATCHED_MARKETS: dict[str, str] = {
    "088691": "Gold",
    "084691": "Silver",
    "085692": "Copper",
    "067651": "Crude Oil WTI",
    "023651": "Natural Gas",
    "13874A": "S&P 500 E-mini",
    "099741": "Euro FX",
    "097741": "Japanese Yen",
    "096742": "British Pound",
    "043602": "10-Year T-Note",
    "020601": "2-Year T-Note",
    "002602": "Corn",
    "005602": "Soybeans",
    "001602": "Wheat",
}

# Map CFTC contract code → yfinance ticker (for backtesting price data)
PRICE_TICKERS: dict[str, str] = {
    "088691": "GC=F",    # Gold Futures
    "084691": "SI=F",    # Silver Futures
    "085692": "HG=F",    # Copper Futures
    "067651": "CL=F",    # Crude Oil
    "023651": "NG=F",    # Natural Gas
    "13874A": "ES=F",    # S&P 500 E-mini
    "099741": "6E=F",    # Euro FX
    "097741": "6J=F",    # Japanese Yen
    "096742": "6B=F",    # British Pound
    "043602": "ZN=F",    # 10-Year T-Note
    "002602": "ZC=F",    # Corn
    "005602": "ZS=F",    # Soybeans
    "001602": "ZW=F",    # Wheat
}

# ── Scheduler ─────────────────────────────────────────────────────────────────
SCHEDULER_ENABLED:  bool = os.getenv("SCHEDULER_ENABLED", "true").lower() == "true"
SCHEDULER_TIMEZONE: str  = os.getenv("SCHEDULER_TIMEZONE", "America/New_York")
