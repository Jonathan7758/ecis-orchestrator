"""
SMS notification channel — Twilio / Alibaba Cloud / Mock.

Priority: 2 (degradation fallback from WeChat)
Timeout: 5 seconds

In production, connects to a real SMS API.
In tests, uses MockSMSSender.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Callable, Coroutine, Optional

from notifications.multi_channel import (
    DeliveryAttempt,
    Notification,
    RecipientInfo,
    SMSConfig,
)

from notifications.masking import mask_phone

logger = logging.getLogger("ecis.notifications.sms")


class SMSChannel:
    """SMS notification channel with configurable sender.

    Supports mock, Twilio, and Alibaba Cloud SMS backends.
    The sender function is injectable for testing.
    """

    @property
    def channel_name(self) -> str:
        return "sms"

    @property
    def timeout_seconds(self) -> float:
        return 5.0

    def __init__(
        self,
        config: Optional[SMSConfig] = None,
        sender: Optional[Callable[..., Coroutine]] = None,
    ) -> None:
        """Initialize SMS channel.

        Args:
            config: SMS provider configuration.
            sender: Async callable(phone, message) -> bool. Overrides
                    default sending logic. Use for testing.
        """
        self._config = config or SMSConfig(provider="mock")
        self._sender = sender
        self._available = True

    async def send(self, notification: Notification,
                   recipient: RecipientInfo) -> DeliveryAttempt:
        """Send via SMS.

        Args:
            notification: Notification to send.
            recipient: Must have phone number set.

        Returns:
            DeliveryAttempt with result.
        """
        start = time.monotonic()

        if not recipient.phone:
            return DeliveryAttempt(
                channel="sms",
                success=False,
                error="No phone number for recipient",
            )

        message = self._format_sms(notification)

        try:
            if self._sender is not None:
                # Custom/mock sender
                success = await self._sender(recipient.phone, message)
            elif self._config.provider == "mock":
                # Built-in mock — always succeed
                success = True
            else:
                # Real API integration point
                # In production: call Twilio/Alibaba SDK
                success = await self._send_via_provider(
                    recipient.phone, message,
                )

            latency = int((time.monotonic() - start) * 1000)
            return DeliveryAttempt(
                channel="sms",
                success=success,
                latency_ms=latency,
                error=None if success else "SMS delivery failed",
            )

        except Exception as exc:
            latency = int((time.monotonic() - start) * 1000)
            return DeliveryAttempt(
                channel="sms",
                success=False,
                latency_ms=latency,
                error=str(exc),
            )

    async def health_check(self) -> bool:
        """Check if SMS channel is available."""
        return self._available

    def set_available(self, available: bool) -> None:
        """Set availability (for testing/simulation)."""
        self._available = available

    def _format_sms(self, notification: Notification) -> str:
        """Format notification for SMS (160 char limit awareness)."""
        title = notification.title[:40] if notification.title else ""
        body = notification.body[:100] if notification.body else ""
        return f"[ECIS] {title}: {body}"

    async def _send_via_provider(self, phone: str, message: str) -> bool:
        """Send via configured SMS provider API.

        This is a placeholder for real API integration.
        In production, this would call Twilio/Alibaba Cloud SDK.
        """
        logger.warning(
            "SMS provider %s not implemented, returning False (phone: %s)",
            self._config.provider,
            mask_phone(phone),
        )
        return False
