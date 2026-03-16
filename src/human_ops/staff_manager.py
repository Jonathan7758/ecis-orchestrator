"""
human_ops.staff_manager — H1 Staff Management service.

Provides full lifecycle management for property-management staff:
profile CRUD, attendance tracking, location/workload queries, and
skill-based staff lookup.  All operations delegate to a
:class:`StorageBackend` so the service is storage-agnostic.
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, date
from typing import Any, Dict, List, Optional
from uuid import uuid4

from human_ops.models import (
    AttendanceRecord,
    StaffLocation,
    StaffProfile,
    StaffWorkload,
)
from human_ops.storage import StorageBackend


# Collection names used in the storage backend
_COL_STAFF = "staff_profiles"
_COL_ATTENDANCE = "attendance_records"
_COL_LOCATION = "staff_locations"
_COL_WORKLOAD = "staff_workloads"


class StaffManager:
    """H1 — Staff management service.

    Wraps a :class:`StorageBackend` to provide higher-level operations
    on staff profiles, attendance, location tracking, and workload
    queries.
    """

    def __init__(self, backend: StorageBackend) -> None:
        self._backend = backend

    # ------------------------------------------------------------------
    # Staff Profile CRUD
    # ------------------------------------------------------------------

    async def add_staff(self, profile: StaffProfile) -> StaffProfile:
        """Persist a new staff profile.

        If ``profile.staff_id`` is empty or ``None`` a UUID is generated.
        Returns the profile (with its final ``staff_id``).
        """
        if not profile.staff_id:
            profile.staff_id = str(uuid4())
        data = asdict(profile)
        await self._backend.put(_COL_STAFF, profile.staff_id, data)
        return profile

    async def get_staff(self, staff_id: str) -> Optional[StaffProfile]:
        """Retrieve a staff profile by ID, or ``None`` if not found."""
        data = await self._backend.get(_COL_STAFF, staff_id)
        if data is None:
            return None
        return self._to_staff_profile(data)

    async def update_staff(
        self,
        staff_id: str,
        updates: Dict[str, Any],
    ) -> Optional[StaffProfile]:
        """Apply partial updates to an existing staff profile.

        Returns the updated profile, or ``None`` if the staff member does
        not exist.
        """
        data = await self._backend.get(_COL_STAFF, staff_id)
        if data is None:
            return None
        data.update(updates)
        # Re-validate by constructing a dataclass
        profile = self._to_staff_profile(data)
        await self._backend.put(_COL_STAFF, staff_id, asdict(profile))
        return profile

    async def list_staff(
        self,
        building_id: Optional[str] = None,
        role: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[StaffProfile]:
        """List staff profiles with optional filters.

        Any combination of *building_id*, *role*, and *status* is accepted;
        ``None`` values are ignored.
        """
        filters: Dict[str, Any] = {}
        if building_id is not None:
            filters["building_id"] = building_id
        if role is not None:
            filters["role"] = role
        if status is not None:
            filters["status"] = status
        docs = await self._backend.query(_COL_STAFF, filters or None)
        return [self._to_staff_profile(d) for d in docs]

    # ------------------------------------------------------------------
    # Attendance
    # ------------------------------------------------------------------

    async def check_in(
        self,
        staff_id: str,
        building_id: str,
        check_in_time: Optional[datetime] = None,
    ) -> Optional[AttendanceRecord]:
        """Record a staff check-in and mark the profile as active.

        Creates a new :class:`AttendanceRecord` for today.  Returns
        ``None`` if the staff member does not exist.
        """
        profile = await self.get_staff(staff_id)
        if profile is None:
            return None

        now = check_in_time or datetime.utcnow()
        today_str = now.strftime("%Y-%m-%d")
        now_str = now.isoformat()

        record = AttendanceRecord(
            staff_id=staff_id,
            date=today_str,
            status="present",
            check_in=now_str,
            location_building=building_id,
        )
        record_key = f"{staff_id}:{today_str}"
        await self._backend.put(_COL_ATTENDANCE, record_key, asdict(record))

        # Mark the staff member active
        await self.update_staff(staff_id, {"status": "active"})
        return record

    async def check_out(
        self,
        staff_id: str,
        check_out_time: Optional[datetime] = None,
    ) -> Optional[AttendanceRecord]:
        """Record a staff check-out for today.

        Returns the updated attendance record, or ``None`` if no check-in
        exists for today.
        """
        now = check_out_time or datetime.utcnow()
        today_str = now.strftime("%Y-%m-%d")
        record_key = f"{staff_id}:{today_str}"

        data = await self._backend.get(_COL_ATTENDANCE, record_key)
        if data is None:
            return None

        data["check_out"] = now.isoformat()
        record = self._to_attendance_record(data)
        await self._backend.put(_COL_ATTENDANCE, record_key, asdict(record))
        return record

    async def report_leave(
        self,
        staff_id: str,
        leave_date: Optional[date] = None,
    ) -> Optional[AttendanceRecord]:
        """Record a leave day for a staff member.

        Also updates the staff profile status to ``on_leave``.  Returns
        ``None`` if the staff member does not exist.
        """
        profile = await self.get_staff(staff_id)
        if profile is None:
            return None

        target = leave_date or date.today()
        date_str = target.isoformat()

        record = AttendanceRecord(
            staff_id=staff_id,
            date=date_str,
            status="leave",
        )
        record_key = f"{staff_id}:{date_str}"
        await self._backend.put(_COL_ATTENDANCE, record_key, asdict(record))
        await self.update_staff(staff_id, {"status": "on_leave"})
        return record

    async def get_attendance(
        self,
        staff_id: str,
        target_date: Optional[date] = None,
    ) -> Optional[AttendanceRecord]:
        """Retrieve the attendance record for a staff member on a given date.

        Defaults to today when *target_date* is ``None``.
        """
        target = target_date or date.today()
        record_key = f"{staff_id}:{target.isoformat()}"
        data = await self._backend.get(_COL_ATTENDANCE, record_key)
        if data is None:
            return None
        return self._to_attendance_record(data)

    # ------------------------------------------------------------------
    # Status Queries
    # ------------------------------------------------------------------

    async def get_available_staff(
        self,
        building_id: Optional[str] = None,
        target_date: Optional[date] = None,
        shift: Optional[str] = None,
    ) -> List[StaffProfile]:
        """Return active staff who are NOT on leave for the given date.

        Optionally filter by *building_id*.  If *shift* is provided it is
        stored for informational purposes but all active staff at the
        building are returned (shift filtering is done at the schedule
        layer).
        """
        filters: Dict[str, Any] = {"status": "active"}
        if building_id is not None:
            filters["building_id"] = building_id

        candidates = await self._backend.query(_COL_STAFF, filters)

        # Exclude anyone who has reported leave for target_date
        target = target_date or date.today()
        available: List[StaffProfile] = []
        for doc in candidates:
            sid = doc["staff_id"]
            att = await self._backend.get(
                _COL_ATTENDANCE, f"{sid}:{target.isoformat()}"
            )
            if att is not None and att.get("status") == "leave":
                continue
            available.append(self._to_staff_profile(doc))
        return available

    async def get_staff_location(
        self, staff_id: str,
    ) -> Optional[StaffLocation]:
        """Return the most recent location for a staff member."""
        data = await self._backend.get(_COL_LOCATION, staff_id)
        if data is None:
            return None
        return self._to_staff_location(data)

    async def update_staff_location(
        self,
        staff_id: str,
        building_id: str,
        floor: int,
        zone_id: str,
        timestamp: Optional[datetime] = None,
    ) -> StaffLocation:
        """Record or update the real-time location of a staff member."""
        now = timestamp or datetime.utcnow()
        loc = StaffLocation(
            staff_id=staff_id,
            building_id=building_id,
            floor=floor,
            zone_id=zone_id,
            last_updated=now.isoformat(),
        )
        await self._backend.put(_COL_LOCATION, staff_id, asdict(loc))
        return loc

    async def get_staff_workload(
        self,
        staff_id: str,
        target_date: Optional[date] = None,
    ) -> Optional[StaffWorkload]:
        """Return the workload snapshot for a staff member on a date."""
        target = target_date or date.today()
        key = f"{staff_id}:{target.isoformat()}"
        data = await self._backend.get(_COL_WORKLOAD, key)
        if data is None:
            return None
        return self._to_staff_workload(data)

    async def update_staff_workload(
        self,
        workload: StaffWorkload,
    ) -> StaffWorkload:
        """Persist a workload snapshot."""
        key = f"{workload.staff_id}:{workload.date}"
        await self._backend.put(_COL_WORKLOAD, key, asdict(workload))
        return workload

    # ------------------------------------------------------------------
    # Skill Matching
    # ------------------------------------------------------------------

    async def find_qualified_staff(
        self,
        skill: str,
        building_id: Optional[str] = None,
        available_only: bool = True,
    ) -> List[StaffProfile]:
        """Find staff members who possess a given *skill*.

        When *available_only* is ``True`` (the default), only active and
        non-leave staff are returned.  When *building_id* is given, results
        are further scoped to that building.
        """
        filters: Dict[str, Any] = {}
        if building_id is not None:
            filters["building_id"] = building_id
        if available_only:
            filters["status"] = "active"

        docs = await self._backend.query(_COL_STAFF, filters or None)

        results: List[StaffProfile] = []
        for doc in docs:
            skills = doc.get("skills", [])
            if skill in skills:
                results.append(self._to_staff_profile(doc))
        return results

    # ------------------------------------------------------------------
    # Dataclass Reconstruction Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _to_staff_profile(data: Dict[str, Any]) -> StaffProfile:
        """Reconstruct a :class:`StaffProfile` from a storage dict."""
        return StaffProfile(
            staff_id=data["staff_id"],
            name=data["name"],
            role=data["role"],
            building_id=data["building_id"],
            phone=data["phone"],
            skills=data.get("skills", []),
            status=data.get("status", "active"),
            hire_date=data.get("hire_date"),
            experience_years=data.get("experience_years", 0.0),
        )

    @staticmethod
    def _to_attendance_record(data: Dict[str, Any]) -> AttendanceRecord:
        """Reconstruct an :class:`AttendanceRecord` from a storage dict."""
        return AttendanceRecord(
            staff_id=data["staff_id"],
            date=data["date"],
            status=data.get("status", "present"),
            check_in=data.get("check_in"),
            check_out=data.get("check_out"),
            location_building=data.get("location_building"),
        )

    @staticmethod
    def _to_staff_location(data: Dict[str, Any]) -> StaffLocation:
        """Reconstruct a :class:`StaffLocation` from a storage dict."""
        return StaffLocation(
            staff_id=data["staff_id"],
            building_id=data["building_id"],
            floor=data["floor"],
            zone_id=data["zone_id"],
            last_updated=data["last_updated"],
        )

    @staticmethod
    def _to_staff_workload(data: Dict[str, Any]) -> StaffWorkload:
        """Reconstruct a :class:`StaffWorkload` from a storage dict."""
        return StaffWorkload(
            staff_id=data["staff_id"],
            date=data["date"],
            total_assignments=data.get("total_assignments", 0),
            completed_assignments=data.get("completed_assignments", 0),
            active_assignment=data.get("active_assignment"),
            hours_worked=data.get("hours_worked", 0.0),
        )
