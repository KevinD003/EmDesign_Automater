"""Outbound email (v2 Part 35) — SMTP when configured, file outbox otherwise.

Configuration is by environment variables so no code change is needed between
a laptop, a LAN box, and a real deployment:

- ``SMTP_HOST`` (presence turns real sending ON), ``SMTP_PORT`` (default 587),
  ``SMTP_USER`` / ``SMTP_PASS`` (optional auth), ``SMTP_FROM`` (default
  ``no-reply@stitchiq.local``), ``SMTP_STARTTLS=0`` to disable STARTTLS for a
  plaintext relay on a trusted LAN.
- Without ``SMTP_HOST`` every message is written to ``data/outbox/*.eml``
  instead — the flow is fully testable end-to-end (the reset test reads the
  token out of the .eml), and a supervised LAN launch can hand the file to the
  user directly. The send is never silently dropped: the function returns
  where the message went.

``data/`` is gitignored, so the outbox can never leak addresses into the repo.
"""

from __future__ import annotations

import os
import re
import smtplib
import threading
from datetime import UTC, datetime
from email.message import EmailMessage
from pathlib import Path

_OUTBOX = Path(__file__).resolve().parents[2] / "data" / "outbox"
_counter_lock = threading.Lock()
_counter = 0


class MailError(Exception):
    """Raised when SMTP is configured but the send fails."""


def _build(to: str, subject: str, body: str) -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = os.environ.get("SMTP_FROM", "no-reply@stitchiq.local")
    msg["To"] = to
    msg["Subject"] = subject
    msg["Date"] = datetime.now(UTC).strftime("%a, %d %b %Y %H:%M:%S +0000")
    # cte="7bit": our bodies are ASCII, and the default quoted-printable would
    # soft-wrap the reset link mid-token — a user copying from the raw .eml
    # (the outbox fallback IS the delivery on a LAN install) would get a
    # broken link. 7bit keeps every line literal.
    msg.set_content(body, cte="7bit")
    return msg


def send_email(to: str, subject: str, body: str) -> str:
    """Send (or spool) one plain-text message; returns "smtp" or the .eml path."""
    msg = _build(to, subject, body)
    host = os.environ.get("SMTP_HOST")
    if host:
        port = int(os.environ.get("SMTP_PORT", "587"))
        try:
            with smtplib.SMTP(host, port, timeout=15) as smtp:
                if os.environ.get("SMTP_STARTTLS", "1") != "0":
                    smtp.starttls()
                user = os.environ.get("SMTP_USER")
                if user:
                    smtp.login(user, os.environ.get("SMTP_PASS", ""))
                smtp.send_message(msg)
        except (OSError, smtplib.SMTPException) as exc:
            raise MailError(f"SMTP send failed: {exc}") from exc
        return "smtp"

    global _counter
    outdir = Path(os.environ.get("STITCHIQ_OUTBOX", str(_OUTBOX)))
    outdir.mkdir(parents=True, exist_ok=True)
    with _counter_lock:
        _counter += 1
        n = _counter
    safe_to = re.sub(r"[^A-Za-z0-9_.@-]", "_", to)[:64]
    path = outdir / (
        f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%S')}-{n:04d}-{safe_to}.eml"
    )
    path.write_bytes(bytes(msg))
    return str(path)


def send_reset_email(to: str, username: str, token: str) -> str:
    """The password-reset message. The link targets the SPA's reset route."""
    base = os.environ.get("STITCHIQ_APP_URL", "http://localhost:5173").rstrip("/")
    link = f"{base}/#/reset?token={token}"
    body = (
        f"Hi {username},\n\n"
        "Someone (hopefully you) asked to reset the PIN for your STITCHIQ "
        "account.\n\n"
        f"Reset link (valid for 30 minutes, works once):\n\n    {link}\n\n"
        "If you did not ask for this, you can ignore this email - your PIN "
        "is unchanged and the link expires on its own.\n\n"
        "- STITCHIQ\n"
    )
    return send_email(to, "Reset your STITCHIQ PIN", body)
