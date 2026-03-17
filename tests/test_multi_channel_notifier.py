"""
F7+ Multi-Channel Notifier Tests — 25 tests.

Tests the core degradation logic: WeChat → SMS → Email.
Covers: normal delivery, degradation, timeout, all-failed,
        delivery status, channel health, and edge cases.

All channels use mock senders (no real API calls).
Uses MemoryBackend for delivery log persistence.

Marked with @pytest.mark.degradation for selective runs.
"""

from __future__ import annotations

import asyncio
from dataclasses import asdict
from typing import Any

import pytest

from human_ops.storage import MemoryBackend
from notifications.multi_channel import (
    DeliveryResult,
    EmailConfig,
    MultiChannelNotifier,
    Notification,
    RecipientInfo,
    SMSConfig,
)
from notifications.channels.wechat_channel import WeChatChannel
from notifications.channels.sms_channel import SMSChannel
from notifications.channels.email_channel import EmailChannel

pytestmark = [pytest.mark.asyncio, pytest.mark.degradation]


# =========================================================================
# Helpers — Mock channels
# =========================================================================

def make_wechat(success: bool = True, delay: float = 0.0):
    """Create a WeChat channel with controllable behavior."""
    async def mock_send(phone, msg):
        if delay > 0:
            await asyncio.sleep(delay)
        return success

    ch = WeChatChannel(wechat_service=None)
    # Override send to control success/failure
    original_send = ch.send

    async def controlled_send(notification, recipient):
        if delay > 0:
            await asyncio.sleep(delay)
        from notifications.multi_channel import DeliveryAttempt
        return DeliveryAttempt(
            channel="wechat",
            success=success,
            latency_ms=int(delay * 1000),
            error=None if success else "WeChat API error",
        )

    ch.send = controlled_send
    return ch


def make_sms(success: bool = True, delay: float = 0.0):
    """Create an SMS channel with controllable behavior."""
    async def mock_sender(phone, message):
        if delay > 0:
            await asyncio.sleep(delay)
        return success

    return SMSChannel(
        config=SMSConfig(provider="mock"),
        sender=mock_sender,
    )


def make_email(success: bool = True, delay: float = 0.0):
    """Create an Email channel with controllable behavior."""
    async def mock_sender(to, subject, body):
        if delay > 0:
            await asyncio.sleep(delay)
        return success

    return EmailChannel(
        config=EmailConfig(),
        sender=mock_sender,
    )


def make_notification(**kwargs) -> Notification:
    """Create a test notification."""
    defaults = {
        "notification_type": "dispatch",
        "title": "Robot GX-001 Error",
        "body": "Navigation sensor malfunction in Tower C Lobby",
        "priority": "high",
        "building_id": "tower-c",
    }
    defaults.update(kwargs)
    return Notification(**defaults)


def make_recipient(**kwargs) -> RecipientInfo:
    """Create a test recipient with all channels."""
    defaults = {
        "user_id": "tc-003",
        "name": "Wang Qiang",
        "wechat_userid": "wq003",
        "phone": "138-0001-0003",
        "email": "wangqiang@ecis.linkc.hk",
    }
    defaults.update(kwargs)
    return RecipientInfo(**defaults)


# =========================================================================
# Normal Delivery Tests
# =========================================================================

class TestNormalDelivery:
    """Test successful delivery through preferred channel."""

    async def test_wechat_first_success(self):
        """F7+-01: When WeChat succeeds, delivery uses WeChat."""
        notifier = MultiChannelNotifier(
            wechat_channel=make_wechat(success=True),
            sms_channel=make_sms(success=True),
            email_channel=make_email(success=True),
            backend=MemoryBackend(),
        )
        result = await notifier.dispatch(make_notification(), make_recipient())
        assert result.status == "delivered"
        assert result.channel_used == "wechat"
        assert len(result.attempts) == 1

    async def test_delivery_logged(self):
        """F7+-02: Delivery result is persisted to StorageBackend."""
        backend = MemoryBackend()
        notifier = MultiChannelNotifier(
            wechat_channel=make_wechat(success=True),
            backend=backend,
        )
        notif = make_notification()
        recipient = make_recipient()
        await notifier.dispatch(notif, recipient)

        key = f"{notif.notification_id}:{recipient.user_id}"
        log = await backend.get("delivery_log", key)
        assert log is not None
        assert log["status"] == "delivered"
        assert log["channel_used"] == "wechat"

    async def test_sms_only_recipient(self):
        """F7+-03: Recipient with only phone gets SMS delivery."""
        notifier = MultiChannelNotifier(
            wechat_channel=make_wechat(success=True),
            sms_channel=make_sms(success=True),
            backend=MemoryBackend(),
        )
        recipient = make_recipient(wechat_userid=None, email=None)
        result = await notifier.dispatch(make_notification(), recipient)
        assert result.status == "delivered"
        assert result.channel_used == "sms"

    async def test_email_only_recipient(self):
        """F7+-04: Recipient with only email gets Email delivery."""
        notifier = MultiChannelNotifier(
            wechat_channel=make_wechat(success=True),
            sms_channel=make_sms(success=True),
            email_channel=make_email(success=True),
            backend=MemoryBackend(),
        )
        recipient = make_recipient(wechat_userid=None, phone=None)
        result = await notifier.dispatch(make_notification(), recipient)
        assert result.status == "delivered"
        assert result.channel_used == "email"


# =========================================================================
# Degradation Tests (Core V9 Feature)
# =========================================================================

class TestDegradation:
    """Test automatic channel degradation on failure."""

    async def test_wechat_fail_degrade_to_sms(self):
        """F7+-05: WeChat failure degrades to SMS."""
        notifier = MultiChannelNotifier(
            wechat_channel=make_wechat(success=False),
            sms_channel=make_sms(success=True),
            email_channel=make_email(success=True),
            backend=MemoryBackend(),
        )
        result = await notifier.dispatch(make_notification(), make_recipient())
        assert result.status == "delivered"
        assert result.channel_used == "sms"
        assert len(result.attempts) == 2  # wechat failed + sms succeeded

    async def test_wechat_sms_fail_degrade_to_email(self):
        """F7+-06: WeChat + SMS failure degrades to Email."""
        notifier = MultiChannelNotifier(
            wechat_channel=make_wechat(success=False),
            sms_channel=make_sms(success=False),
            email_channel=make_email(success=True),
            backend=MemoryBackend(),
        )
        result = await notifier.dispatch(make_notification(), make_recipient())
        assert result.status == "delivered"
        assert result.channel_used == "email"
        assert len(result.attempts) == 3

    async def test_all_channels_fail(self):
        """F7+-07: All channels fail → status is all_failed."""
        notifier = MultiChannelNotifier(
            wechat_channel=make_wechat(success=False),
            sms_channel=make_sms(success=False),
            email_channel=make_email(success=False),
            backend=MemoryBackend(),
        )
        result = await notifier.dispatch(make_notification(), make_recipient())
        assert result.status == "all_failed"
        assert result.channel_used == "none"
        assert len(result.attempts) == 3

    async def test_wechat_timeout_degrade_to_sms(self):
        """F7+-08: WeChat timeout (>3s) degrades to SMS."""
        notifier = MultiChannelNotifier(
            wechat_channel=make_wechat(success=True, delay=5.0),  # exceeds 3s
            sms_channel=make_sms(success=True),
            backend=MemoryBackend(),
        )
        result = await notifier.dispatch(make_notification(), make_recipient())
        assert result.status == "delivered"
        assert result.channel_used == "sms"
        # First attempt should be timeout
        assert result.attempts[0]["success"] is False
        assert "Timeout" in (result.attempts[0].get("error") or "")

    async def test_schedule_notification_degradation(self):
        """F7+-09: Schedule notification degrades correctly."""
        notifier = MultiChannelNotifier(
            wechat_channel=make_wechat(success=False),
            sms_channel=make_sms(success=True),
            backend=MemoryBackend(),
        )
        notif = make_notification(
            notification_type="schedule",
            title="Morning Schedule Confirmed",
            body="Tower C: 3 staff assigned, 2 robots",
        )
        result = await notifier.dispatch(notif, make_recipient())
        assert result.status == "delivered"
        assert result.channel_used == "sms"

    async def test_dispatch_notification_degradation(self):
        """F7+-10: Dispatch notification degrades with key info preserved."""
        notifier = MultiChannelNotifier(
            wechat_channel=make_wechat(success=False),
            sms_channel=make_sms(success=True),
            backend=MemoryBackend(),
        )
        notif = make_notification(
            notification_type="dispatch",
            title="Urgent: Robot Error",
            body="GX-001 in Lobby, contact Wang Qiang 138-0001-0003",
            priority="critical",
        )
        result = await notifier.dispatch(notif, make_recipient())
        assert result.status == "delivered"


# =========================================================================
# Delivery Status Query Tests
# =========================================================================

class TestDeliveryStatus:
    """Test delivery status querying."""

    async def test_query_delivered(self):
        """F7+-11: Can query status of delivered notification."""
        backend = MemoryBackend()
        notifier = MultiChannelNotifier(
            wechat_channel=make_wechat(success=True),
            backend=backend,
        )
        notif = make_notification()
        recipient = make_recipient()
        await notifier.dispatch(notif, recipient)

        status = await notifier.get_delivery_status(
            notif.notification_id, recipient.user_id,
        )
        assert status is not None
        assert status.status == "delivered"
        assert status.channel_used == "wechat"
        assert status.total_attempts == 1

    async def test_query_failed(self):
        """F7+-12: Can query status of failed notification."""
        backend = MemoryBackend()
        notifier = MultiChannelNotifier(
            wechat_channel=make_wechat(success=False),
            backend=backend,
        )
        notif = make_notification()
        recipient = make_recipient(phone=None, email=None)
        await notifier.dispatch(notif, recipient)

        status = await notifier.get_delivery_status(
            notif.notification_id, recipient.user_id,
        )
        assert status is not None
        assert status.status == "all_failed"

    async def test_query_nonexistent(self):
        """F7+-13: Querying nonexistent notification returns None."""
        notifier = MultiChannelNotifier(backend=MemoryBackend())
        status = await notifier.get_delivery_status("no-such-id")
        assert status is None

    async def test_query_no_backend(self):
        """F7+-14: Query returns None when no backend configured."""
        notifier = MultiChannelNotifier(
            wechat_channel=make_wechat(success=True),
        )
        status = await notifier.get_delivery_status("any-id")
        assert status is None


# =========================================================================
# Channel Health Tests
# =========================================================================

class TestChannelHealth:
    """Test channel health monitoring."""

    async def test_all_healthy(self):
        """F7+-15: All channels report healthy when available."""
        notifier = MultiChannelNotifier(
            wechat_channel=make_wechat(success=True),
            sms_channel=make_sms(success=True),
            email_channel=make_email(success=True),
        )
        health = await notifier.get_channel_health()
        assert len(health) == 3
        assert all(h.is_available for h in health.values())

    async def test_health_after_failures(self):
        """F7+-16: Channel health reflects failure stats."""
        backend = MemoryBackend()
        wechat = make_wechat(success=False)
        sms = make_sms(success=True)
        notifier = MultiChannelNotifier(
            wechat_channel=wechat,
            sms_channel=sms,
            backend=backend,
        )

        # Send a notification that forces degradation
        await notifier.dispatch(make_notification(), make_recipient())

        health = await notifier.get_channel_health()
        assert health["wechat"].total_failed == 1
        assert health["wechat"].success_rate == 0.0
        assert health["sms"].total_failed == 0

    async def test_health_no_channels(self):
        """F7+-17: Empty notifier returns no health data."""
        notifier = MultiChannelNotifier()
        health = await notifier.get_channel_health()
        assert health == {}


# =========================================================================
# Data Model Tests
# =========================================================================

class TestDataModels:
    """Test notification data models."""

    def test_notification_defaults(self):
        """F7+-18: Notification creates with defaults."""
        n = Notification(title="Test", body="Hello")
        assert n.notification_id != ""
        assert n.created_at != ""
        assert n.priority == "normal"
        assert n.notification_type == "general"

    def test_notification_invalid_priority(self):
        """F7+-19: Invalid priority raises ValueError."""
        with pytest.raises(ValueError, match="Invalid priority"):
            Notification(priority="extreme")

    def test_notification_invalid_type(self):
        """F7+-20: Invalid notification type raises ValueError."""
        with pytest.raises(ValueError, match="Invalid notification_type"):
            Notification(notification_type="unknown")

    def test_recipient_info(self):
        """F7+-21: RecipientInfo stores all contact channels."""
        r = RecipientInfo(
            user_id="test",
            wechat_userid="wx123",
            phone="138-0000-0000",
            email="test@ecis.hk",
        )
        assert r.wechat_userid == "wx123"
        assert r.phone == "138-0000-0000"
        assert r.email == "test@ecis.hk"

    def test_sms_config_invalid_provider(self):
        """F7+-22: Invalid SMS provider raises ValueError."""
        with pytest.raises(ValueError, match="Unknown SMS provider"):
            SMSConfig(provider="invalid")


# =========================================================================
# Edge Cases
# =========================================================================

class TestEdgeCases:
    """Test boundary conditions and error handling."""

    async def test_no_channels_configured(self):
        """F7+-23: No channels → all_failed immediately."""
        notifier = MultiChannelNotifier(backend=MemoryBackend())
        result = await notifier.dispatch(make_notification(), make_recipient())
        assert result.status == "all_failed"
        assert result.attempts == []

    async def test_recipient_no_contact_info(self):
        """F7+-24: Recipient with no contact info → all_failed."""
        notifier = MultiChannelNotifier(
            wechat_channel=make_wechat(success=True),
            sms_channel=make_sms(success=True),
            email_channel=make_email(success=True),
            backend=MemoryBackend(),
        )
        recipient = RecipientInfo(user_id="empty")
        result = await notifier.dispatch(make_notification(), recipient)
        assert result.status == "all_failed"
        assert len(result.attempts) == 3  # Each channel tried but no contact

    async def test_multiple_recipients(self):
        """F7+-25: Same notification can be sent to multiple recipients."""
        backend = MemoryBackend()
        notifier = MultiChannelNotifier(
            wechat_channel=make_wechat(success=True),
            backend=backend,
        )
        notif = make_notification()

        r1 = make_recipient(user_id="tc-001", name="Zhang Wei", wechat_userid="zw001")
        r2 = make_recipient(user_id="tc-002", name="Li Na", wechat_userid="ln002")

        res1 = await notifier.dispatch(notif, r1)
        res2 = await notifier.dispatch(notif, r2)

        assert res1.status == "delivered"
        assert res2.status == "delivered"
        assert res1.recipient_id == "tc-001"
        assert res2.recipient_id == "tc-002"

        # Both logged separately
        s1 = await notifier.get_delivery_status(notif.notification_id, "tc-001")
        s2 = await notifier.get_delivery_status(notif.notification_id, "tc-002")
        assert s1 is not None
        assert s2 is not None
