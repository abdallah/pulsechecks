"""SMTP email integration for alert channels.

Cloud-agnostic: works with SES SMTP on AWS and any SMTP provider
(SendGrid, Mailgun, Google Workspace relay) on GCP. Uses the stdlib
smtplib in a worker thread so no extra dependency is required.
"""
import asyncio
import smtplib
from email.message import EmailMessage
from typing import List

from ..config import get_settings
import logging

logger = logging.getLogger(__name__)

SMTP_TIMEOUT = 15  # seconds


class EmailNotConfiguredError(Exception):
    """Raised when SMTP settings are missing on this deployment."""


def _build_message(recipients: List[str], subject: str, body: str) -> EmailMessage:
    settings = get_settings()
    msg = EmailMessage()
    msg["From"] = settings.smtp_from or settings.smtp_username
    msg["To"] = ", ".join(recipients)
    msg["Subject"] = subject
    msg.set_content(body)
    return msg


def _send_sync(recipients: List[str], subject: str, body: str) -> None:
    settings = get_settings()
    if not settings.smtp_host:
        raise EmailNotConfiguredError(
            "SMTP is not configured on this deployment. "
            "Set SMTP_HOST, SMTP_USERNAME, SMTP_PASSWORD, and SMTP_FROM."
        )

    msg = _build_message(recipients, subject, body)
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=SMTP_TIMEOUT) as server:
        if settings.smtp_use_tls:
            server.starttls()
        if settings.smtp_username:
            server.login(settings.smtp_username, settings.smtp_password)
        server.send_message(msg)


async def send_email(recipients: List[str], subject: str, body: str) -> bool:
    """Send an email to the given recipients. Returns success boolean."""
    try:
        await asyncio.to_thread(_send_sync, recipients, subject, body)
        return True
    except EmailNotConfiguredError:
        raise
    except Exception as e:
        logger.error(f"Failed to send email to {len(recipients)} recipient(s): {e}")
        return False


def _check_url(check) -> str:
    settings = get_settings()
    return f"{settings.frontend_url}/teams/{check.team_id}/checks/{check.check_id}"


async def send_late_alert_email(recipients: List[str], check, team_name: str) -> bool:
    subject = f"⚠️ [{team_name}] Check late: {check.name}"
    body = (
        f"The check \"{check.name}\" in team \"{team_name}\" has not reported in on time.\n\n"
        f"Status: LATE\n"
        f"Last ping: {check.last_ping_at or 'never'}\n\n"
        f"View check: {_check_url(check)}\n"
    )
    return await send_email(recipients, subject, body)


async def send_recovery_alert_email(recipients: List[str], check, team_name: str) -> bool:
    subject = f"✅ [{team_name}] Check recovered: {check.name}"
    body = (
        f"The check \"{check.name}\" in team \"{team_name}\" is reporting in again.\n\n"
        f"Status: UP\n\n"
        f"View check: {_check_url(check)}\n"
    )
    return await send_email(recipients, subject, body)
