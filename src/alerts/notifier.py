"""
Alert dispatch system.

Channels supported:
  - Telegram Bot
  - Email (SMTP)
  - Console (always enabled, for logging)

Alerts are deduplicated via the alert_log table.
"""
from __future__ import annotations

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import httpx

from src.config import (
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHAT_ID,
    SMTP_HOST,
    SMTP_PORT,
    SMTP_USER,
    SMTP_PASSWORD,
    ALERT_EMAIL_TO,
    EXTREME_LONG_THRESHOLD,
    EXTREME_SHORT_THRESHOLD,
)
from src.storage.db import was_alert_sent, log_alert

logger = logging.getLogger(__name__)

_SIGNAL_EMOJI = {
    "bullish":       "🟢",
    "bullish_lean":  "🟡",
    "neutral":       "⚪",
    "bearish_lean":  "🟡",
    "bearish":       "🔴",
}


def _format_message(signal: dict) -> str:
    emoji = _SIGNAL_EMOJI.get(signal.get("direction", "neutral"), "⚪")
    market = signal.get("market_name", signal.get("contract_code", "Unknown"))
    sig_type = signal.get("signal_type", "").replace("_", " ").title()
    strength = signal.get("strength", 0)
    cot_idx  = signal.get("cot_index")
    desc     = signal.get("description", "")

    lines = [
        f"{emoji} CFTC COT SIGNAL — {market}",
        f"Type:       {sig_type}",
        f"Direction:  {signal.get('direction', '').upper()}",
        f"Strength:   {strength:.0f}/100",
    ]
    if cot_idx is not None:
        lines.append(f"COT Index:  {cot_idx:.1f}th percentile")
    if signal.get("net_position") is not None:
        lines.append(f"Net Pos:    {signal['net_position']:,}")
    if signal.get("net_chg_1w") is not None:
        lines.append(f"Chg (1W):   {signal['net_chg_1w']:+,}")
    lines.append("")
    lines.append(desc)
    return "\n".join(lines)


# ── Telegram ──────────────────────────────────────────────────────────────────

def send_telegram(message: str) -> bool:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        resp = httpx.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": message}, timeout=10)
        resp.raise_for_status()
        return True
    except Exception as e:
        logger.error("Telegram send failed: %s", e)
        return False


# ── Email ─────────────────────────────────────────────────────────────────────

def send_email(subject: str, body: str) -> bool:
    if not all([SMTP_USER, SMTP_PASSWORD, ALERT_EMAIL_TO]):
        return False
    try:
        msg = MIMEMultipart()
        msg["From"]    = SMTP_USER
        msg["To"]      = ALERT_EMAIL_TO
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_USER, ALERT_EMAIL_TO, msg.as_string())
        return True
    except Exception as e:
        logger.error("Email send failed: %s", e)
        return False


# ── Dispatch ──────────────────────────────────────────────────────────────────

def _should_alert(signal: dict) -> bool:
    """Only alert on signals with sufficient strength."""
    strength = signal.get("strength", 0)
    sig_type = signal.get("signal_type", "")
    # Divergence signals always alert; others need strength ≥ threshold
    if sig_type in ("divergence", "multi_asset_confluence", "sector_consensus"):
        return True
    return strength >= max(EXTREME_LONG_THRESHOLD, 100 - EXTREME_SHORT_THRESHOLD)


def dispatch_signal(signal: dict, signal_id: int | None = None) -> None:
    """Send a signal to all configured channels."""
    if not _should_alert(signal):
        return

    message = _format_message(signal)
    market  = signal.get("market_name", "Unknown")
    sig_type = signal.get("signal_type", "signal")

    # Console always
    logger.info("ALERT: %s | %s | dir=%s strength=%.0f",
                market, sig_type, signal.get("direction"), signal.get("strength", 0))

    # Telegram
    if TELEGRAM_BOT_TOKEN:
        if signal_id and was_alert_sent(signal_id, "telegram"):
            pass
        else:
            ok = send_telegram(message)
            if signal_id:
                log_alert(signal_id, "telegram", "sent" if ok else "failed")

    # Email
    if SMTP_USER and ALERT_EMAIL_TO:
        if signal_id and was_alert_sent(signal_id, "email"):
            pass
        else:
            subject = f"COT Signal: {market} — {sig_type.replace('_', ' ').title()}"
            ok = send_email(subject, message)
            if signal_id:
                log_alert(signal_id, "email", "sent" if ok else "failed")


def dispatch_new_signals(signals: list[dict]) -> int:
    """Dispatch all signals that pass the threshold. Returns number dispatched."""
    dispatched = 0
    for sig in signals:
        if _should_alert(sig):
            dispatch_signal(sig)
            dispatched += 1
    return dispatched
