"""SQLAlchemy ORM models for all CFTC report types and derived tables."""
from datetime import date, datetime

from sqlalchemy import (
    Column, Date, DateTime, Float, Integer, String, Text,
    UniqueConstraint, func,
)
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class COTLegacy(Base):
    """CFTC Legacy COT report (futures + options combined)."""
    __tablename__ = "cot_legacy"
    __table_args__ = (UniqueConstraint("contract_code", "report_date"),)

    id              = Column(Integer, primary_key=True)
    contract_code   = Column(String(16), nullable=False, index=True)
    market_name     = Column(String(256), nullable=False)
    report_date     = Column(Date, nullable=False, index=True)

    open_interest   = Column(Integer)

    # Non-commercial (speculators / large traders)
    noncomm_long    = Column(Integer)
    noncomm_short   = Column(Integer)
    noncomm_spread  = Column(Integer)
    noncomm_net     = Column(Integer)  # derived: long - short

    # Commercial (hedgers)
    comm_long       = Column(Integer)
    comm_short      = Column(Integer)
    comm_net        = Column(Integer)  # derived

    # Non-reportable (small traders)
    nonrept_long    = Column(Integer)
    nonrept_short   = Column(Integer)

    # Week-over-week changes
    chg_open_interest  = Column(Integer)
    chg_noncomm_long   = Column(Integer)
    chg_noncomm_short  = Column(Integer)
    chg_comm_long      = Column(Integer)
    chg_comm_short     = Column(Integer)

    # % of OI
    pct_noncomm_long   = Column(Float)
    pct_noncomm_short  = Column(Float)
    pct_comm_long      = Column(Float)
    pct_comm_short     = Column(Float)

    # Trader counts
    traders_total      = Column(Integer)
    traders_noncomm_long  = Column(Integer)
    traders_noncomm_short = Column(Integer)
    traders_comm_long     = Column(Integer)
    traders_comm_short    = Column(Integer)

    created_at = Column(DateTime, server_default=func.now())


class COTDisaggregated(Base):
    """CFTC Disaggregated COT report (physical commodity markets)."""
    __tablename__ = "cot_disaggregated"
    __table_args__ = (UniqueConstraint("contract_code", "report_date"),)

    id            = Column(Integer, primary_key=True)
    contract_code = Column(String(16), nullable=False, index=True)
    market_name   = Column(String(256), nullable=False)
    report_date   = Column(Date, nullable=False, index=True)

    open_interest = Column(Integer)

    # Producer / Merchant / Processor / User
    prod_long    = Column(Integer)
    prod_short   = Column(Integer)
    prod_net     = Column(Integer)

    # Swap Dealers
    swap_long    = Column(Integer)
    swap_short   = Column(Integer)
    swap_spread  = Column(Integer)
    swap_net     = Column(Integer)

    # Managed Money (hedge funds / CTAs)
    mmoney_long  = Column(Integer)
    mmoney_short = Column(Integer)
    mmoney_spread = Column(Integer)
    mmoney_net   = Column(Integer)

    # Other Reportables
    other_long   = Column(Integer)
    other_short  = Column(Integer)
    other_net    = Column(Integer)

    # Non-Reportable
    nonrept_long  = Column(Integer)
    nonrept_short = Column(Integer)

    # Week-over-week changes
    chg_open_interest = Column(Integer)
    chg_prod_long     = Column(Integer)
    chg_prod_short    = Column(Integer)
    chg_swap_long     = Column(Integer)
    chg_swap_short    = Column(Integer)
    chg_mmoney_long   = Column(Integer)
    chg_mmoney_short  = Column(Integer)

    created_at = Column(DateTime, server_default=func.now())


class COTFinancial(Base):
    """CFTC Traders in Financial Futures (TFF) report."""
    __tablename__ = "cot_financial"
    __table_args__ = (UniqueConstraint("contract_code", "report_date"),)

    id            = Column(Integer, primary_key=True)
    contract_code = Column(String(16), nullable=False, index=True)
    market_name   = Column(String(256), nullable=False)
    report_date   = Column(Date, nullable=False, index=True)

    open_interest = Column(Integer)

    # Dealer / Intermediary
    dealer_long   = Column(Integer)
    dealer_short  = Column(Integer)
    dealer_spread = Column(Integer)
    dealer_net    = Column(Integer)

    # Asset Manager / Institutional
    assetmgr_long   = Column(Integer)
    assetmgr_short  = Column(Integer)
    assetmgr_spread = Column(Integer)
    assetmgr_net    = Column(Integer)

    # Leveraged Money (hedge funds)
    levmoney_long   = Column(Integer)
    levmoney_short  = Column(Integer)
    levmoney_spread = Column(Integer)
    levmoney_net    = Column(Integer)

    # Other Reportables
    other_long   = Column(Integer)
    other_short  = Column(Integer)
    other_net    = Column(Integer)

    # Non-Reportable
    nonrept_long  = Column(Integer)
    nonrept_short = Column(Integer)

    # Changes
    chg_open_interest   = Column(Integer)
    chg_dealer_long     = Column(Integer)
    chg_dealer_short    = Column(Integer)
    chg_assetmgr_long   = Column(Integer)
    chg_assetmgr_short  = Column(Integer)
    chg_levmoney_long   = Column(Integer)
    chg_levmoney_short  = Column(Integer)

    created_at = Column(DateTime, server_default=func.now())


class Signal(Base):
    """Generated trading signals based on COT analysis."""
    __tablename__ = "signals"
    __table_args__ = (UniqueConstraint("contract_code", "report_date", "signal_type"),)

    id             = Column(Integer, primary_key=True)
    contract_code  = Column(String(16), nullable=False, index=True)
    market_name    = Column(String(256))
    report_date    = Column(Date, nullable=False, index=True)
    signal_type    = Column(String(64), nullable=False)   # e.g. "extreme_long", "divergence"
    signal_source  = Column(String(64))                   # "legacy", "disaggregated", "financial"
    direction      = Column(String(8))                    # "bullish", "bearish", "neutral"
    strength       = Column(Float)                        # 0–100
    description    = Column(Text)

    # Percentile context
    cot_index      = Column(Float)   # current percentile
    net_position   = Column(Integer)
    net_chg_1w     = Column(Integer)

    created_at = Column(DateTime, server_default=func.now())


class AlertLog(Base):
    """Record of sent alerts to avoid duplicates."""
    __tablename__ = "alert_log"

    id             = Column(Integer, primary_key=True)
    signal_id      = Column(Integer, nullable=False, index=True)
    channel        = Column(String(32))   # "telegram", "email", "console"
    sent_at        = Column(DateTime, server_default=func.now())
    status         = Column(String(16))   # "sent", "failed"
    error_msg      = Column(Text)
