"""Email delivery via Azure Communication Services.

In production: ACS_CONNECTION_STRING + ACS_SENDER_ADDRESS env vars must be set.
In local dev (variables absent): messages are printed to stdout so the rest of the
feature works without an ACS account.
"""

import asyncio
import logging
from functools import lru_cache

from app.config import settings

logger = logging.getLogger(__name__)


class EmailService:
    def __init__(self, connection_string: str, sender_address: str) -> None:
        from azure.communication.email import EmailClient

        self._client = EmailClient.from_connection_string(connection_string)
        self._sender = sender_address

    async def _send(self, to: str, subject: str, html: str, plain: str) -> None:
        message = {
            "senderAddress": self._sender,
            "recipients": {"to": [{"address": to}]},
            "content": {"subject": subject, "html": html, "plainText": plain},
        }
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._send_sync, message)

    def _send_sync(self, message: dict) -> None:
        poller = self._client.begin_send(message)
        result = poller.result()
        if result.get("status") not in ("Succeeded", None):
            logger.warning("ACS send status: %s", result.get("status"))

    async def send_password_reset(self, to_email: str, reset_url: str) -> None:
        subject = "AEGIS — Reset your password"
        plain = (
            f"You requested a password reset for your AEGIS account.\n\n"
            f"Click the link below to set a new password (expires in 1 hour):\n{reset_url}\n\n"
            "If you did not request this, you can ignore this email."
        )
        html = f"""
<html><body style="font-family:sans-serif;max-width:560px;margin:auto;padding:24px">
<h2 style="color:#f7a501">Reset your AEGIS password</h2>
<p>You requested a password reset for your AEGIS account.</p>
<p>
  <a href="{reset_url}"
     style="display:inline-block;background:#f7a501;color:#fff;padding:12px 24px;
            border-radius:6px;text-decoration:none;font-weight:bold">
    Reset Password
  </a>
</p>
<p style="color:#666;font-size:13px">
  This link expires in <strong>1 hour</strong>. If you did not request this,
  you can safely ignore this email.
</p>
</body></html>
"""
        await self._send(to_email, subject, html, plain)

    async def send_grade_notification(self, to_email: str, exam_title: str) -> None:
        subject = f'AEGIS — Your results for "{exam_title}" are ready'
        plain = (
            f'Your results for "{exam_title}" have been published.\n\n'
            "Log in to AEGIS to view your grades."
        )
        html = f"""
<html><body style="font-family:sans-serif;max-width:560px;margin:auto;padding:24px">
<h2 style="color:#f7a501">Your exam results are ready</h2>
<p>Your results for <strong>{exam_title}</strong> have been published by your professor.</p>
<p>Log in to <strong>AEGIS</strong> to view your grades.</p>
</body></html>
"""
        await self._send(to_email, subject, html, plain)


class _DevEmailService:
    """No-op email service for local development: logs to stdout."""

    async def send_password_reset(self, to_email: str, reset_url: str) -> None:
        logger.info("[DEV EMAIL] Password reset for %s → %s", to_email, reset_url)

    async def send_grade_notification(self, to_email: str, exam_title: str) -> None:
        logger.info("[DEV EMAIL] Grade notification for %s: %s", to_email, exam_title)


@lru_cache(maxsize=1)
def get_email_service() -> EmailService | _DevEmailService:
    if settings.acs_connection_string and settings.acs_sender_address:
        return EmailService(settings.acs_connection_string, settings.acs_sender_address)
    logger.warning(
        "ACS_CONNECTION_STRING / ACS_SENDER_ADDRESS not set — using dev email stub"
    )
    return _DevEmailService()
