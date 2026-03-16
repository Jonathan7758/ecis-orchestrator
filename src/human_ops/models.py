"""
human_ops.models — Data models for H1-H4 human operations modules.

Covers staff profiles, attendance, scheduling, exception dispatch,
and work order management for the ECIS property management platform.
All models use Python dataclasses following existing v1.0 patterns.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, date, time
from typing import Dict, List, Optional
from uuid import uuid4


# ---------------------------------------------------------------------------
# H1 — Staff Management
# ---------------------------------------------------------------------------

@dataclass
class StaffProfile:
    """A property-management staff member's profile."""

    staff_id: str
    name: str
    role: str  # cleaner | security | supervisor | manager
    building_id: str
    phone: str
    skills: List[str] = field(default_factory=list)
    status: str = "active"  # active | inactive | on_leave
    hire_date: Optional[str] = None  # ISO date string
    experience_years: float = 0.0

    def __post_init__(self) -> None:
        if self.role not in ("cleaner", "security", "supervisor", "manager"):
            raise ValueError(f"Invalid role: {self.role}")
        if self.status not in ("active", "inactive", "on_leave"):
            raise ValueError(f"Invalid status: {self.status}")


@dataclass
class AttendanceRecord:
    """A single attendance record for one staff member on one date."""

    staff_id: str
    date: str  # ISO date string (YYYY-MM-DD)
    status: str = "present"  # present | absent | late | leave
    check_in: Optional[str] = None  # ISO datetime string
    check_out: Optional[str] = None  # ISO datetime string
    location_building: Optional[str] = None

    def __post_init__(self) -> None:
        if self.status not in ("present", "absent", "late", "leave"):
            raise ValueError(f"Invalid attendance status: {self.status}")


@dataclass
class StaffLocation:
    """Real-time location of a staff member within a building."""

    staff_id: str
    building_id: str
    floor: int
    zone_id: str
    last_updated: str  # ISO datetime string


@dataclass
class StaffWorkload:
    """Daily workload snapshot for a staff member."""

    staff_id: str
    date: str  # ISO date string
    total_assignments: int = 0
    completed_assignments: int = 0
    active_assignment: Optional[str] = None
    hours_worked: float = 0.0


# ---------------------------------------------------------------------------
# H2 — Intelligent Scheduling
# ---------------------------------------------------------------------------

@dataclass
class Assignment:
    """A single staff assignment within a schedule plan."""

    staff_id: str
    staff_name: str
    zone_id: str
    zone_name: str
    shift: str  # morning | afternoon | night
    start_time: str  # ISO datetime or HH:MM
    end_time: str  # ISO datetime or HH:MM
    task_type: str
    paired_robot_id: Optional[str] = None

    def __post_init__(self) -> None:
        if self.shift not in ("morning", "afternoon", "night"):
            raise ValueError(f"Invalid shift: {self.shift}")


@dataclass
class RobotAssignment:
    """A single robot assignment within a schedule plan."""

    robot_id: str
    zone_id: str
    shift: str  # morning | afternoon | night
    task_type: str
    battery_level: float = 100.0

    def __post_init__(self) -> None:
        if self.shift not in ("morning", "afternoon", "night"):
            raise ValueError(f"Invalid shift: {self.shift}")


@dataclass
class SchedulePlan:
    """A complete schedule plan for a building on a given date."""

    schedule_id: str
    building_id: str
    date: str  # ISO date string
    assignments: List[Assignment] = field(default_factory=list)
    robot_assignments: List[RobotAssignment] = field(default_factory=list)
    status: str = "draft"  # draft | confirmed | completed
    confidence: float = 1.0  # 0.0 to 1.0
    notes: List[str] = field(default_factory=list)
    generated_at: Optional[str] = None  # ISO datetime string
    confirmed_by: Optional[str] = None

    def __post_init__(self) -> None:
        if self.status not in ("draft", "confirmed", "completed"):
            raise ValueError(f"Invalid schedule status: {self.status}")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"Confidence must be between 0 and 1, got {self.confidence}")


# ---------------------------------------------------------------------------
# H3 — Exception Dispatch
# ---------------------------------------------------------------------------

@dataclass
class ExceptionEvent:
    """An operational exception that may require human dispatch."""

    event_type: str  # robot_error | complaint | urgent_clean | equipment_fault
    source: str
    building_id: str
    zone_id: str
    priority: str = "normal"  # critical | high | normal | low
    description: str = ""
    robot_id: Optional[str] = None
    created_at: Optional[str] = None  # ISO datetime string

    def __post_init__(self) -> None:
        if self.event_type not in (
            "robot_error", "complaint", "urgent_clean", "equipment_fault",
        ):
            raise ValueError(f"Invalid event_type: {self.event_type}")
        if self.priority not in ("critical", "high", "normal", "low"):
            raise ValueError(f"Invalid priority: {self.priority}")


@dataclass
class DispatchResult:
    """The outcome of dispatching staff for an exception event."""

    dispatch_id: str
    assigned_to: Optional[str] = None  # staff_id
    assigned_name: Optional[str] = None
    status: str = "pending_approval"
    # dispatched | pending_approval | no_available_staff | accepted | resolved | escalated
    autonomy_level: float = 0.0
    estimated_response_minutes: float = 0.0

    _VALID_STATUSES = frozenset({
        "dispatched", "pending_approval", "no_available_staff",
        "accepted", "resolved", "escalated",
    })

    def __post_init__(self) -> None:
        if self.status not in self._VALID_STATUSES:
            raise ValueError(f"Invalid dispatch status: {self.status}")


@dataclass
class DispatchRecord:
    """Full lifecycle record of an exception dispatch."""

    dispatch_id: str
    event: ExceptionEvent
    result: DispatchResult
    dispatched_at: Optional[str] = None  # ISO datetime string
    accepted_at: Optional[str] = None
    resolved_at: Optional[str] = None
    resolution_notes: Optional[str] = None


@dataclass
class DispatchStats:
    """Aggregate statistics for exception dispatches."""

    total_dispatches: int = 0
    avg_response_minutes: float = 0.0
    resolution_rate: float = 0.0
    escalation_rate: float = 0.0
    by_priority: Dict[str, int] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# H4 — Work Order Management
# ---------------------------------------------------------------------------

@dataclass
class WorkOrder:
    """A work order for maintenance, cleaning, or other property tasks."""

    order_id: str
    order_type: str
    source: str
    title: str
    description: str = ""
    priority: str = "normal"  # critical | high | normal | low
    status: str = "open"  # open | assigned | in_progress | resolved | closed
    assigned_to: Optional[str] = None  # staff_id
    building_id: Optional[str] = None
    zone_id: Optional[str] = None
    created_at: Optional[str] = None  # ISO datetime string
    resolved_at: Optional[str] = None
    sla_deadline: Optional[str] = None  # ISO datetime string
    resolution: Optional[str] = None

    _VALID_PRIORITIES = frozenset({"critical", "high", "normal", "low"})
    _VALID_STATUSES = frozenset({
        "open", "assigned", "in_progress", "resolved", "closed",
    })

    def __post_init__(self) -> None:
        if self.priority not in self._VALID_PRIORITIES:
            raise ValueError(f"Invalid priority: {self.priority}")
        if self.status not in self._VALID_STATUSES:
            raise ValueError(f"Invalid work order status: {self.status}")


@dataclass
class OrderStats:
    """Aggregate statistics for work orders."""

    total_orders: int = 0
    open_orders: int = 0
    avg_resolution_hours: float = 0.0
    sla_breach_count: int = 0
    by_type: Dict[str, int] = field(default_factory=dict)
