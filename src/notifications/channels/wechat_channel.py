"""
Enterprise WeChat notification channel.

Wraps V8's WeChatWorkService as a NotificationChannel for use with
the MultiChannelNotifier degradation chain.

Priority: 1 (tried first)
Timeout: 3 seconds
"""

from __future__ import annotations

import logging
import time
from typing import Any, Optional

from notifications.multi_channel import (
    DeliveryAttempt,
    Notification,
    RecipientInfo,
)

logger = logging.getLogger("ecis.notifications.wechat")


class WeChatChannel:
    """Enterprise WeChat notification channel.

    Adapts V8's WeChatWorkService to the NotificationChannel protocol.
    """

    @property
    def channel_name(self) -> str:
        return "wechat"

    @property
    def timeout_seconds(self) -> float:
        return 3.0

    def __init__(self, wechat_service: Any = None) -> None:
        """Initialize with optional V8 WeChatWorkService instance.

        Args:
            wechat_service: V8 F7 WeChatWorkService. If None, uses mock.
        """
        self._service = wechat_service
        self._available = True

    async def send(self, notification: Notification,
                   recipient: RecipientInfo) -> DeliveryAttempt:
        """Send via Enterprise WeChat.

        Args:
            notification: Notification to send.
            recipient: Must have wechat_userid set.

        Returns:
            DeliveryAttempt with result.
        """
        start = time.monotonic()

        if not recipient.wechat_userid:
            return DeliveryAttempt(
                channel="wechat",
                success=False,
                error="No wechat_userid for recipient",
            )

        try:
            if self._service is not None:
                # Use real V8 WeChatWorkService
                await self._service.send_text(
                    recipient.wechat_userid,
                    f"[{notification.title}]\n{notification.body}",
                )
            else:
                # Mock mode — simulate success
                pass

            latency = int((time.monotonic() - start) * 1000)
            return DeliveryAttempt(
                channel="wechat",
                success=True,
                latency_ms=latency,
            )

        except Exception as exc:
            latency = int((time.monotonic() - start) * 1000)
            return DeliveryAttempt(
                channel="wechat",
                success=False,
                latency_ms=latency,
                error=str(exc),
            )

    async def health_check(self) -> bool:
        """Check if WeChat service is available."""
        return self._available

    def set_available(self, available: bool) -> None:
        """Set availability (for testing/simulation)."""
        self._available = available
