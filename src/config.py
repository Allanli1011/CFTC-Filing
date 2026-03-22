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
SOCRATA_LEGACY_FUTURES = "6dca-aqww"
SOCRATA_DISAGGREGATED   = "kh3c-gbw2"
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
# CFTC contract code → display name.
# Codes verified against CFTC Socrata API (publicreporting.cftc.gov).
# Run `python scripts/discover_markets.py` to search for additional codes.
WATCHED_MARKETS: dict[str, str] = {

    # ── Grains ────────────────────────────────────────────────────────────────
    "002602": "Corn",
    "001602": "Wheat (Chicago SRW)",
    "0006KW": "Wheat (Kansas City HRW)",
    "001612": "Wheat (Spring/Minneapolis)",
    "005602": "Soybeans",
    "007601": "Soybean Oil",
    "026603": "Soybean Meal",
    "004603": "Oats",
    "039601": "Rough Rice",

    # ── Softs ─────────────────────────────────────────────────────────────────
    "033661": "Cotton #2",
    "083731": "Coffee",
    "080732": "Sugar #11",
    "073732": "Cocoa",
    "040701": "Orange Juice",

    # ── Livestock & Dairy ─────────────────────────────────────────────────────
    "057642": "Live Cattle",
    "061642": "Feeder Cattle",
    "054642": "Lean Hogs",
    "052641": "Class III Milk",

    # ── Energy ────────────────────────────────────────────────────────────────
    "067651": "Crude Oil WTI",
    "06765T": "Crude Oil Brent",
    "023651": "Natural Gas",
    "022651": "Heating Oil (ULSD)",
    "111659": "RBOB Gasoline",

    # ── Metals ────────────────────────────────────────────────────────────────
    "088691": "Gold",
    "084691": "Silver",
    "085692": "Copper",
    "076651": "Platinum",
    "075651": "Palladium",

    # ── Equity Indices ────────────────────────────────────────────────────────
    "13874A": "S&P 500 E-mini",
    "209742": "Nasdaq 100 E-mini",
    "12460+": "DJIA E-mini",
    "239742": "Russell 2000 E-mini",
    "1170E1": "VIX",

    # ── Interest Rates ────────────────────────────────────────────────────────
    "020601": "30-Year T-Bond",
    "043602": "10-Year T-Note",
    "044601": "5-Year T-Note",
    "042601": "2-Year T-Note",
    "045601": "Fed Funds",
    "134741": "SOFR-3M",

    # ── Currencies ────────────────────────────────────────────────────────────
    "099741": "Euro FX",
    "097741": "Japanese Yen",
    "096742": "British Pound",
    "092741": "Swiss Franc",
    "090741": "Canadian Dollar",
    "232741": "Australian Dollar",
    "095741": "Mexican Peso",
    "112741": "New Zealand Dollar",
    "102741": "Brazilian Real",
    "089741": "Russian Ruble",

    # ── Crypto ────────────────────────────────────────────────────────────────
    "133741": "Bitcoin",
    "146021": "Ethereum",
    "133742": "Micro Bitcoin",
}

# Map CFTC contract code → yfinance ticker (for backtesting price data)
PRICE_TICKERS: dict[str, str] = {
    # Grains
    "002602": "ZC=F",    # Corn
    "001602": "ZW=F",    # Wheat Chicago
    "005602": "ZS=F",    # Soybeans
    "007601": "ZL=F",    # Soybean Oil
    "026603": "ZM=F",    # Soybean Meal
    "004603": "ZO=F",    # Oats
    "039601": "ZR=F",    # Rough Rice
    # Softs
    "033661": "CT=F",    # Cotton
    "083731": "KC=F",    # Coffee
    "080732": "SB=F",    # Sugar #11
    "073732": "CC=F",    # Cocoa
    "040701": "OJ=F",    # Orange Juice
    # Livestock
    "057642": "LE=F",    # Live Cattle
    "061642": "GF=F",    # Feeder Cattle
    "054642": "HE=F",    # Lean Hogs
    # Energy
    "067651": "CL=F",    # Crude Oil WTI
    "06765T": "BZ=F",    # Brent Crude
    "023651": "NG=F",    # Natural Gas
    "022651": "HO=F",    # Heating Oil
    "111659": "RB=F",    # RBOB Gasoline
    # Metals
    "088691": "GC=F",    # Gold
    "084691": "SI=F",    # Silver
    "085692": "HG=F",    # Copper
    "076651": "PL=F",    # Platinum
    "075651": "PA=F",    # Palladium
    # Equity Indices
    "13874A": "ES=F",    # S&P 500 E-mini
    "209742": "NQ=F",    # Nasdaq 100 E-mini
    "12460+": "YM=F",    # DJIA E-mini
    "239742": "RTY=F",   # Russell 2000
    # Interest Rates
    "020601": "ZB=F",    # 30-Year T-Bond
    "043602": "ZN=F",    # 10-Year T-Note
    "044601": "ZF=F",    # 5-Year T-Note
    "042601": "ZT=F",    # 2-Year T-Note
    "134741": "SR3=F",   # SOFR-3M
    # Currencies
    "099741": "6E=F",    # Euro
    "097741": "6J=F",    # Japanese Yen
    "096742": "6B=F",    # British Pound
    "092741": "6S=F",    # Swiss Franc
    "090741": "6C=F",    # Canadian Dollar
    "232741": "6A=F",    # Australian Dollar
    "095741": "6M=F",    # Mexican Peso
    "112741": "6N=F",    # New Zealand Dollar
    "102741": "6L=F",    # Brazilian Real
    # Crypto
    "133741": "BTC=F",   # Bitcoin
    "146021": "ETH=F",   # Ethereum
    "133742": "MBT=F",   # Micro Bitcoin
}

# ── Scheduler ─────────────────────────────────────────────────────────────────
SCHEDULER_ENABLED:  bool = os.getenv("SCHEDULER_ENABLED", "true").lower() == "true"
SCHEDULER_TIMEZONE: str  = os.getenv("SCHEDULER_TIMEZONE", "America/New_York")
