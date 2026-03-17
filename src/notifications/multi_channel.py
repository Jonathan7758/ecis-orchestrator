"""
F7+ Multi-Channel Notifier — Enterprise WeChat + SMS + Email with degradation.

Core V9 module that solves the single-point-of-failure issue identified in
ecis-user-story-check Q4: "When WeChat is down, notifications cannot be delivered."

Degradation chain:
    Priority 1: Enterprise WeChat (timeout=3s)
    Priority 2: SMS (timeout=5s)
    Priority 3: Email (timeout=10s)

All delivery attempts are logged via StorageBackend for auditability.

Usage:
    notifier = MultiChannelNotifier(
        wechat_channel=wechat, sms_channel=sms,
        email_channel=email, backend=backend,
    )
    result = await notifier.dispatch(notification, recipient)
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Protocol
from uuid import uuid4

from human_ops.storage import StorageBackend

logger = logging.getLogger("ecis.notifications")


# =========================================================================
# Data Models (Step 1: dataclass)
# =========================================================================

@dataclass
class SMSConfig:
    """SMS channel configuration."""
    provider: str = "mock"           # mock / twilio / alibaba_cloud
    api_key: str = ""
    sender_id: str = "ECIS"

    def __post_init__(self):
        if self.provider not in ("mock", "twilio", "alibaba_cloud", "tencent_cloud"):
            raise ValueError(f"Unknown SMS provider: {self.provider}")


@dataclass
class EmailConfig:
    """Email channel configuration."""
    smtp_host: str = "localhost"
    smtp_port: int = 587
    username: str = ""
    password: str = ""
    from_address: str = "ecis@linkc.hk"


@dataclass
class Notification:
    """A notification to be delivered."""
    notification_id: str = ""
    notification_type: str = "general"  # schedule / dispatch / order / health / general
    title: str = ""
    body: str = ""
    priority: str = "normal"            # low / normal / high / critical
    building_id: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = ""

    def __post_init__(self):
        if not self.notification_id:
            self.notification_id = str(uuid4())
        if not self.created_at:
            self.created_at = datetime.utcnow().isoformat()
        if self.priority not in ("low", "normal", "high", "critical"):
            raise ValueError(f"Invalid priority: {self.priority}")
        if self.notification_type not in (
            "schedule", "dispatch", "order", "health", "general",
        ):
            raise ValueError(f"Invalid notification_type: {self.notification_type}")


@dataclass
class RecipientInfo:
    """Recipient contact information for multi-channel delivery."""
    user_id: str = ""
    name: str = ""
    wechat_userid: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None


@dataclass
class DeliveryAttempt:
    """Record of a single delivery attempt on one channel."""
    channel: str = ""                # wechat / sms / email
    success: bool = False
    latency_ms: int = 0
    error: Optional[str] = None
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.utcnow().isoformat()


@dataclass
class DeliveryResult:
    """Final delivery result with all attempts."""
    notification_id: str = ""
    recipient_id: str = ""
    channel_used: str = ""           # wechat / sms / email / none
    status: str = "pending"          # delivered / pending / all_failed
    attempts: List[Dict[str, Any]] = field(default_factory=list)
    created_at: str = ""
    delivered_at: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.utcnow().isoformat()


@dataclass
class DeliveryStatus:
    """Delivery status query result."""
    notification_id: str = ""
    recipient_id: str = ""
    channel_used: str = ""
    status: str = "unknown"
    total_attempts: int = 0
    last_attempt_at: str = ""


@dataclass
class ChannelHealth:
    """Health status of a notification channel."""
    channel: str = ""
    is_available: bool = True
    success_rate: float = 1.0        # 0.0 - 1.0
    avg_latency_ms: int = 0
    last_failure: Optional[str] = None
    total_sent: int = 0
    total_failed: int = 0


# =========================================================================
# Channel Protocol (Step 2: Interface)
# =========================================================================

class NotificationChannel(Protocol):
    """Protocol for notification delivery channels."""

    @property
    def channel_name(self) -> str:
        """Return channel identifier (wechat/sms/email)."""
        ...

    @property
    def timeout_seconds(self) -> float:
        """Return delivery timeout in seconds."""
        ...

    async def send(self, notification: Notification,
                   recipient: RecipientInfo) -> DeliveryAttempt:
        """Send a notification through this channel.

        Args:
            notification: The notification to send.
            recipient: Recipient contact info.

        Returns:
            DeliveryAttempt with success status.
        """
        ...

    async def health_check(self) -> bool:
        """Check if the channel is currently available."""
        ...


# =========================================================================
# F7+ MultiChannelNotifier (Step 4: Implementation)
# =========================================================================

class MultiChannelNotifier:
    """V9 F7+: Multi-channel notification with automatic degradation.

    Tries to deliver via Enterprise WeChat first. If that fails or
    times out, degrades to SMS. If SMS fails, degrades to Email.
    All attempts are logged to StorageBackend.

    Integrates with P3 NotificationService — P3's public send() interface
    remains unchanged; only its internal delivery mechanism is replaced.
    """

    DELIVERY_LOG = "delivery_log"

    def __init__(
        self,
        wechat_channel: Optional[NotificationChannel] = None,
        sms_channel: Optional[NotificationChannel] = None,
        email_channel: Optional[NotificationChannel] = None,
        backend: Optional[StorageBackend] = None,
    ) -> None:
        """Initialize multi-channel notifier.

        Args:
            wechat_channel: Enterprise WeChat delivery channel.
            sms_channel: SMS delivery channel (Twilio/Alibaba).
            email_channel: Email delivery channel (SMTP).
            backend: StorageBackend for delivery log persistence.
        """
        self._channels: List[NotificationChannel] = []
        if wechat_channel is not None:
            self._channels.append(wechat_channel)
        if sms_channel is not None:
            self._channels.append(sms_channel)
        if email_channel is not None:
            self._channels.append(email_channel)
        self._backend = backend

        # Track channel health stats
        self._channel_stats: Dict[str, Dict[str, Any]] = {}
        for ch in self._channels:
            self._channel_stats[ch.channel_name] = {
                "total_sent": 0,
                "total_failed": 0,
                "latency_sum_ms": 0,
                "last_failure": None,
            }

    async def dispatch(self, notification: Notification,
                       recipient: RecipientInfo) -> DeliveryResult:
        """Dispatch notification through channels with automatic degradation.

        Tries each channel in priority order (wechat → sms → email).
        Stops at the first successful delivery.

        Args:
            notification: The notification to deliver.
            recipient: Recipient with contact info for each channel.

        Returns:
            DeliveryResult with the channel used and all attempts.
        """
        result = DeliveryResult(
            notification_id=notification.notification_id,
            recipient_id=recipient.user_id,
        )

        for channel in self._channels:
            # Check if recipient has contact info for this channel
            if not self._recipient_has_channel(recipient, channel.channel_name):
                attempt = DeliveryAttempt(
                    channel=channel.channel_name,
                    success=False,
                    error=f"Recipient has no {channel.channel_name} contact info",
                )
                result.attempts.append(asdict(attempt))
                continue

            # Try delivery with timeout
            try:
                attempt = await asyncio.wait_for(
                    channel.send(notification, recipient),
                    timeout=channel.timeout_seconds,
                )
            except asyncio.TimeoutError:
                attempt = DeliveryAttempt(
                    channel=channel.channel_name,
                    success=False,
                    latency_ms=int(channel.timeout_seconds * 1000),
                    error=f"Timeout after {channel.timeout_seconds}s",
                )
            except Exception as exc:
                attempt = DeliveryAttempt(
                    channel=channel.channel_name,
                    success=False,
                    error=str(exc),
                )

            result.attempts.append(asdict(attempt))
            self._update_stats(channel.channel_name, attempt)

            if attempt.success:
                result.channel_used = channel.channel_name
                result.status = "delivered"
                result.delivered_at = datetime.utcnow().isoformat()
                logger.info(
                    "Notification %s delivered via %s to %s",
                    notification.notification_id,
                    channel.channel_name,
                    recipient.user_id,
                )
                break
            else:
                logger.warning(
                    "Channel %s failed for %s: %s — trying next",
                    channel.channel_name,
                    notification.notification_id,
                    attempt.error,
                )

        # If all channels failed
        if result.status != "delivered":
            result.status = "all_failed"
            result.channel_used = "none"
            logger.error(
                "All channels failed for notification %s to %s",
                notification.notification_id,
                recipient.user_id,
            )

        # Persist delivery log
        if self._backend is not None:
            log_key = f"{notification.notification_id}:{recipient.user_id}"
            await self._backend.put(
                self.DELIVERY_LOG, log_key, asdict(result),
            )

        return result

    async def get_delivery_status(self,
                                  notification_id: str,
                                  recipient_id: str = "") -> Optional[DeliveryStatus]:
        """Query delivery status for a notification.

        Args:
            notification_id: The notification ID.
            recipient_id: Optional recipient filter.

        Returns:
            DeliveryStatus if found, None otherwise.
        """
        if self._backend is None:
            return None

        if recipient_id:
            key = f"{notification_id}:{recipient_id}"
            data = await self._backend.get(self.DELIVERY_LOG, key)
            if data is None:
                return None
            return DeliveryStatus(
                notification_id=data.get("notification_id", ""),
                recipient_id=data.get("recipient_id", ""),
                channel_used=data.get("channel_used", ""),
                status=data.get("status", "unknown"),
                total_attempts=len(data.get("attempts", [])),
                last_attempt_at=data.get("delivered_at", ""),
            )

        # Query all deliveries for this notification
        records = await self._backend.query(
            self.DELIVERY_LOG,
            {"notification_id": notification_id},
        )
        if not records:
            return None

        record = records[0]
        return DeliveryStatus(
            notification_id=record.get("notification_id", ""),
            recipient_id=record.get("recipient_id", ""),
            channel_used=record.get("channel_used", ""),
            status=record.get("status", "unknown"),
            total_attempts=len(record.get("attempts", [])),
            last_attempt_at=record.get("delivered_at", ""),
        )

    async def get_channel_health(self) -> Dict[str, ChannelHealth]:
        """Get health status for all configured channels.

        Returns:
            Dict mapping channel name to ChannelHealth.
        """
        result = {}
        for channel in self._channels:
            stats = self._channel_stats.get(channel.channel_name, {})
            total = stats.get("total_sent", 0)
            failed = stats.get("total_failed", 0)
            latency_sum = stats.get("latency_sum_ms", 0)

            success_rate = (total - failed) / total if total > 0 else 1.0
            avg_latency = latency_sum // total if total > 0 else 0

            # Check channel availability
            try:
                is_available = await channel.health_check()
            except Exception:
                is_available = False

            result[channel.channel_name] = ChannelHealth(
                channel=channel.channel_name,
                is_available=is_available,
                success_rate=success_rate,
                avg_latency_ms=avg_latency,
                last_failure=stats.get("last_failure"),
                total_sent=total,
                total_failed=failed,
            )
        return result

    def _recipient_has_channel(self, recipient: RecipientInfo,
                               channel_name: str) -> bool:
        """Check if recipient has contact info for a given channel."""
        if channel_name == "wechat":
            return recipient.wechat_userid is not None
        elif channel_name == "sms":
            return recipient.phone is not None
        elif channel_name == "email":
            return recipient.email is not None
        return False

    def _update_stats(self, channel_name: str, attempt: DeliveryAttempt) -> None:
        """Update internal channel statistics."""
        if channel_name not in self._channel_stats:
            return
        stats = self._channel_stats[channel_name]
        stats["total_sent"] += 1
        stats["latency_sum_ms"] += attempt.latency_ms
        if not attempt.success:
            stats["total_failed"] += 1
            stats["last_failure"] = attempt.timestamp
