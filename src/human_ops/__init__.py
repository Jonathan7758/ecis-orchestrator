"""
human_ops — Human operations modules (H1-H4) for the ECIS platform.

Provides data models, storage abstraction, and service classes for
staff management, scheduling, exception dispatch, and work orders.
"""

from human_ops.models import (
    Assignment,
    AttendanceRecord,
    DispatchRecord,
    DispatchResult,
    DispatchStats,
    ExceptionEvent,
    OrderStats,
    RobotAssignment,
    SchedulePlan,
    StaffLocation,
    StaffProfile,
    StaffWorkload,
    WorkOrder,
)
from human_ops.storage import MemoryBackend, StorageBackend
from human_ops.staff_manager import StaffManager

__all__ = [
    # H1 — Staff Management models
    "StaffProfile",
    "AttendanceRecord",
    "StaffLocation",
    "StaffWorkload",
    # H2 — Scheduling models
    "Assignment",
    "RobotAssignment",
    "SchedulePlan",
    # H3 — Exception Dispatch models
    "ExceptionEvent",
    "DispatchResult",
    "DispatchRecord",
    "DispatchStats",
    # H4 — Work Order models
    "WorkOrder",
    "OrderStats",
    # Storage
    "StorageBackend",
    "MemoryBackend",
    # Services
    "StaffManager",
]
