"""Database engine, session factory, and CRUD helpers."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import date
from typing import Generator

import pandas as pd
from sqlalchemy import create_engine, select, and_, desc, func
from sqlalchemy.orm import Session, sessionmaker

from src.config import DATABASE_URL
from src.storage.models import Base, COTLegacy, COTDisaggregated, COTFinancial, Signal, AlertLog

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {},
    echo=False,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def init_db() -> None:
    """Create all tables (idempotent)."""
    Base.metadata.create_all(engine)


@contextmanager
def get_session() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# ── Latest-date helpers (for incremental fetch) ───────────────────────────────

def get_latest_report_date_legacy() -> date | None:
    with get_session() as s:
        return s.scalar(select(func.max(COTLegacy.report_date)))


def get_latest_report_date_disaggregated() -> date | None:
    with get_session() as s:
        return s.scalar(select(func.max(COTDisaggregated.report_date)))


def get_latest_report_date_financial() -> date | None:
    with get_session() as s:
        return s.scalar(select(func.max(COTFinancial.report_date)))


# ── Upsert helpers ────────────────────────────────────────────────────────────

def upsert_legacy(rows: list[dict]) -> int:
    """Insert or update Legacy COT rows. Returns number of new rows inserted."""
    inserted = 0
    with get_session() as s:
        for row in rows:
            existing = s.scalar(
                select(COTLegacy).where(
                    and_(
                        COTLegacy.contract_code == row["contract_code"],
                        COTLegacy.report_date   == row["report_date"],
                    )
                )
            )
            if existing is None:
                s.add(COTLegacy(**row))
                inserted += 1
            else:
                for k, v in row.items():
                    setattr(existing, k, v)
    return inserted


def upsert_disaggregated(rows: list[dict]) -> int:
    inserted = 0
    with get_session() as s:
        for row in rows:
            existing = s.scalar(
                select(COTDisaggregated).where(
                    and_(
                        COTDisaggregated.contract_code == row["contract_code"],
                        COTDisaggregated.report_date   == row["report_date"],
                    )
                )
            )
            if existing is None:
                s.add(COTDisaggregated(**row))
                inserted += 1
            else:
                for k, v in row.items():
                    setattr(existing, k, v)
    return inserted


def upsert_financial(rows: list[dict]) -> int:
    inserted = 0
    with get_session() as s:
        for row in rows:
            existing = s.scalar(
                select(COTFinancial).where(
                    and_(
                        COTFinancial.contract_code == row["contract_code"],
                        COTFinancial.report_date   == row["report_date"],
                    )
                )
            )
            if existing is None:
                s.add(COTFinancial(**row))
                inserted += 1
            else:
                for k, v in row.items():
                    setattr(existing, k, v)
    return inserted


# ── Query helpers ─────────────────────────────────────────────────────────────

def get_legacy_df(contract_code: str | None = None, limit: int = 500) -> pd.DataFrame:
    q = select(COTLegacy).order_by(desc(COTLegacy.report_date)).limit(limit)
    if contract_code:
        q = q.where(COTLegacy.contract_code == contract_code)
    
    with engine.connect() as conn:
        df = pd.read_sql(q, conn)
    return df


def get_disaggregated_df(contract_code: str | None = None, limit: int = 500) -> pd.DataFrame:
    q = select(COTDisaggregated).order_by(desc(COTDisaggregated.report_date)).limit(limit)
    if contract_code:
        q = q.where(COTDisaggregated.contract_code == contract_code)
    
    with engine.connect() as conn:
        df = pd.read_sql(q, conn)
    return df


def get_financial_df(contract_code: str | None = None, limit: int = 500) -> pd.DataFrame:
    q = select(COTFinancial).order_by(desc(COTFinancial.report_date)).limit(limit)
    if contract_code:
        q = q.where(COTFinancial.contract_code == contract_code)
    
    with engine.connect() as conn:
        df = pd.read_sql(q, conn)
    return df


def save_signals(signals: list[dict]) -> int:
    """Upsert signals keyed on (contract_code, report_date, signal_type). Returns inserted count."""
    inserted = 0
    with get_session() as s:
        for sig in signals:
            existing = s.scalar(
                select(Signal).where(
                    and_(
                        Signal.contract_code == sig["contract_code"],
                        Signal.report_date   == sig["report_date"],
                        Signal.signal_type   == sig["signal_type"],
                    )
                )
            )
            if existing is None:
                s.add(Signal(**sig))
                inserted += 1
            else:
                for k, v in sig.items():
                    setattr(existing, k, v)
    return inserted


def get_latest_signals(limit: int = 100) -> pd.DataFrame:
    with get_session() as s:
        rows = s.scalars(
            select(Signal).order_by(desc(Signal.report_date), desc(Signal.strength)).limit(limit)
        ).all()
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame([r.__dict__ for r in rows]).drop(columns=["_sa_instance_state"], errors="ignore")


def was_alert_sent(signal_id: int, channel: str) -> bool:
    with get_session() as s:
        row = s.scalar(
            select(AlertLog).where(
                and_(AlertLog.signal_id == signal_id, AlertLog.channel == channel, AlertLog.status == "sent")
            )
        )
    return row is not None


def log_alert(signal_id: int, channel: str, status: str, error_msg: str = "") -> None:
    with get_session() as s:
        s.add(AlertLog(signal_id=signal_id, channel=channel, status=status, error_msg=error_msg))
