"""
Email notification channel — SMTP-based delivery.

Priority: 3 (last resort in degradation chain)
Timeout: 10 seconds

In production, connects to a real SMTP server.
In tests, uses injectable sender function.
"""

from __future__ import annotations

import logging
import time
from typing import Callable, Coroutine, Optional

from notifications.multi_channel import (
    DeliveryAttempt,
    EmailConfig,
    Notification,
    RecipientInfo,
)

from notifications.masking import mask_email

logger = logging.getLogger("ecis.notifications.email")


class EmailChannel:
    """Email notification channel via SMTP.

    Last-resort fallback in the degradation chain.
    """

    @property
    def channel_name(self) -> str:
        return "email"

    @property
    def timeout_seconds(self) -> float:
        return 10.0

    def __init__(
        self,
        config: Optional[EmailConfig] = None,
        sender: Optional[Callable[..., Coroutine]] = None,
    ) -> None:
        """Initialize email channel.

        Args:
            config: SMTP configuration.
            sender: Async callable(to_address, subject, body) -> bool.
                    Overrides default SMTP logic. Use for testing.
        """
        self._config = config or EmailConfig()
        self._sender = sender
        self._available = True

    async def send(self, notification: Notification,
                   recipient: RecipientInfo) -> DeliveryAttempt:
        """Send via Email.

        Args:
            notification: Notification to send.
            recipient: Must have email address set.

        Returns:
            DeliveryAttempt with result.
        """
        start = time.monotonic()

        if not recipient.email:
            return DeliveryAttempt(
                channel="email",
                success=False,
                error="No email address for recipient",
            )

        subject = f"[ECIS] {notification.title}"
        body = self._format_email(notification)

        try:
            if self._sender is not None:
                # Custom/mock sender
                success = await self._sender(recipient.email, subject, body)
            else:
                # Real SMTP integration point
                success = await self._send_via_smtp(
                    recipient.email, subject, body,
                )

            latency = int((time.monotonic() - start) * 1000)
            return DeliveryAttempt(
                channel="email",
                success=success,
                latency_ms=latency,
                error=None if success else "Email delivery failed",
            )

        except Exception as exc:
            latency = int((time.monotonic() - start) * 1000)
            return DeliveryAttempt(
                channel="email",
                success=False,
                latency_ms=latency,
                error=str(exc),
            )

    async def health_check(self) -> bool:
        """Check if email channel is available."""
        return self._available

    def set_available(self, available: bool) -> None:
        """Set availability (for testing/simulation)."""
        self._available = available

    def _format_email(self, notification: Notification) -> str:
        """Format notification as email body (HTML-like)."""
        return (
            f"ECIS Notification\n"
            f"{'='*40}\n\n"
            f"Type: {notification.notification_type}\n"
            f"Priority: {notification.priority}\n"
            f"Building: {notification.building_id}\n\n"
            f"{notification.title}\n"
            f"{'-'*40}\n"
            f"{notification.body}\n\n"
            f"Sent at: {notification.created_at}\n"
            f"Notification ID: {notification.notification_id}\n"
        )

    async def _send_via_smtp(self, to_address: str,
                              subject: str, body: str) -> bool:
        """Send via SMTP.

        Placeholder for real aiosmtplib integration.
        """
        logger.warning("SMTP not configured, returning False")
        return False
