"""V9 Notifications — Multi-channel delivery with automatic degradation."""

from notifications.multi_channel import (
    MultiChannelNotifier,
    Notification,
    RecipientInfo,
    DeliveryResult,
    DeliveryAttempt,
    DeliveryStatus,
    ChannelHealth,
    SMSConfig,
    EmailConfig,
)

__all__ = [
    "MultiChannelNotifier",
    "Notification",
    "RecipientInfo",
    "DeliveryResult",
    "DeliveryAttempt",
    "DeliveryStatus",
    "ChannelHealth",
    "SMSConfig",
    "EmailConfig",
]
