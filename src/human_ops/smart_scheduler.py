"""
human_ops.smart_scheduler — H2 Intelligent Scheduling service.

Generates, adjusts, and manages daily schedule plans for property
management buildings.  Assigns staff to zones using a greedy skill-
matching algorithm and integrates robot assignments.  Accepts
configuration dicts (from K1/K2) rather than depending on the
knowledge layer directly, keeping the module testable in isolation.

All operations delegate to a :class:`StorageBackend` so the service
is storage-agnostic.
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

from human_ops.models import (
    Assignment,
    RobotAssignment,
    SchedulePlan,
    StaffProfile,
)
from human_ops.staff_manager import StaffManager
from human_ops.storage import StorageBackend

# Collection name used in the storage backend
_COL_SCHEDULES = "schedules"

# Default shift time ranges
_SHIFT_TIMES: Dict[str, tuple] = {
    "morning": ("06:00", "14:00"),
    "afternoon": ("14:00", "22:00"),
    "night": ("22:00", "06:00"),
}


class SmartScheduler:
    """H2 -- Intelligent scheduling service.

    Generates daily schedule plans that assign staff members to zones
    within a building.  Supports greedy skill-based matching, robot
    co-assignments, absence adjustments, and ad-hoc temporary tasks.
    """

    def __init__(self, staff_manager: StaffManager, backend: StorageBackend) -> None:
        self._staff = staff_manager
        self._backend = backend

    # ------------------------------------------------------------------
    # Schedule Generation
    # ------------------------------------------------------------------

    async def generate_schedule(
        self,
        building_id: str,
        target_date: str,
        zone_configs: List[Dict[str, Any]],
        robot_status: Optional[List[Dict[str, Any]]] = None,
    ) -> SchedulePlan:
        """Generate a schedule plan for *building_id* on *target_date*.

        Parameters
        ----------
        building_id:
            The building to schedule.
        target_date:
            ISO date string (YYYY-MM-DD) for the target day.
        zone_configs:
            A list of zone configuration dicts.  Each dict must contain:
            ``zone_id``, ``zone_name``, ``shift``, ``task_type``,
            ``staff_required`` (int), and ``skills_needed`` (List[str]).
        robot_status:
            Optional list of robot status dicts.  Each dict must contain:
            ``robot_id``, ``zone_id``, ``battery_level``, ``task_type``.
            A ``shift`` key is optional and defaults to ``"morning"``.

        Returns
        -------
        SchedulePlan
            The generated schedule plan, persisted in storage.
        """
        from datetime import date as _date

        # 1. Parse the target date and get available staff from H1
        parts = target_date.split("-")
        dt = _date(int(parts[0]), int(parts[1]), int(parts[2]))
        available_staff = await self._staff.get_available_staff(
            building_id=building_id, target_date=dt,
        )

        # 2. Sort zone_configs: zones with skills_needed first (higher priority)
        sorted_zones = sorted(
            zone_configs,
            key=lambda zc: (0 if zc.get("skills_needed") else 1),
        )

        assigned_ids: set = set()
        assignments: List[Assignment] = []
        notes: List[str] = []
        unfilled_count = 0

        # 3. Greedy assignment
        for zc in sorted_zones:
            zone_id = zc["zone_id"]
            zone_name = zc["zone_name"]
            shift = zc["shift"]
            task_type = zc["task_type"]
            staff_required = zc.get("staff_required", 1)
            skills_needed = zc.get("skills_needed", [])

            start_time, end_time = _SHIFT_TIMES.get(shift, ("00:00", "00:00"))
            filled = 0

            for _ in range(staff_required):
                candidate = self._find_best_candidate(
                    available_staff, assigned_ids, skills_needed,
                )
                if candidate is not None:
                    assigned_ids.add(candidate.staff_id)
                    assignments.append(
                        Assignment(
                            staff_id=candidate.staff_id,
                            staff_name=candidate.name,
                            zone_id=zone_id,
                            zone_name=zone_name,
                            shift=shift,
                            start_time=start_time,
                            end_time=end_time,
                            task_type=task_type,
                        )
                    )
                    filled += 1

            gap = staff_required - filled
            if gap > 0:
                unfilled_count += gap
                notes.append(
                    f"Zone {zone_name} ({zone_id}): {gap} staff position(s) unfilled"
                )

        # 4. Robot assignments
        robot_assignments: List[RobotAssignment] = []
        if robot_status:
            for rs in robot_status:
                robot_shift = rs.get("shift", "morning")
                robot_assignments.append(
                    RobotAssignment(
                        robot_id=rs["robot_id"],
                        zone_id=rs["zone_id"],
                        shift=robot_shift,
                        task_type=rs["task_type"],
                        battery_level=rs.get("battery_level", 100.0),
                    )
                )

            # Pair robots with staff in the same zone where possible
            for ra in robot_assignments:
                for a in assignments:
                    if a.zone_id == ra.zone_id and a.paired_robot_id is None:
                        a.paired_robot_id = ra.robot_id
                        break

        # 5. Confidence calculation
        total_zones = len(zone_configs)
        if total_zones == 0:
            confidence = 1.0
        else:
            confidence = max(0.0, 1.0 - (unfilled_count * 0.1))

        schedule_id = str(uuid4())
        plan = SchedulePlan(
            schedule_id=schedule_id,
            building_id=building_id,
            date=target_date,
            assignments=assignments,
            robot_assignments=robot_assignments,
            status="draft",
            confidence=round(confidence, 2),
            notes=notes,
            generated_at=datetime.utcnow().isoformat(),
        )

        # 6. Persist
        await self._save_schedule(plan)
        return plan

    # ------------------------------------------------------------------
    # Schedule Adjustment
    # ------------------------------------------------------------------

    async def adjust_for_absence(
        self,
        schedule_id: str,
        absent_staff_id: str,
    ) -> Optional[SchedulePlan]:
        """Adjust a schedule when a staff member reports absent.

        Removes all assignments for *absent_staff_id* and attempts to
        find a replacement from available staff not already assigned.
        Reduces confidence if no replacement is found.

        Returns the updated :class:`SchedulePlan`, or ``None`` if the
        schedule does not exist.
        """
        plan = await self._load_schedule(schedule_id)
        if plan is None:
            return None

        # Find assignments belonging to the absent staff member
        absent_assignments = [
            a for a in plan.assignments if a.staff_id == absent_staff_id
        ]
        if not absent_assignments:
            # Staff member not in schedule -- return plan unchanged
            return plan

        remaining = [
            a for a in plan.assignments if a.staff_id != absent_staff_id
        ]

        # Currently assigned staff IDs (excluding the absent one)
        # Also include the absent staff member so they are not re-assigned
        assigned_ids = {a.staff_id for a in remaining}
        assigned_ids.add(absent_staff_id)

        from datetime import date as _date
        parts = plan.date.split("-")
        dt = _date(int(parts[0]), int(parts[1]), int(parts[2]))
        available_staff = await self._staff.get_available_staff(
            building_id=plan.building_id, target_date=dt,
        )

        new_assignments: List[Assignment] = list(remaining)
        unreplaced = 0

        for old in absent_assignments:
            candidate = self._find_best_candidate(
                available_staff, assigned_ids, [],
            )
            if candidate is not None:
                assigned_ids.add(candidate.staff_id)
                new_assignments.append(
                    Assignment(
                        staff_id=candidate.staff_id,
                        staff_name=candidate.name,
                        zone_id=old.zone_id,
                        zone_name=old.zone_name,
                        shift=old.shift,
                        start_time=old.start_time,
                        end_time=old.end_time,
                        task_type=old.task_type,
                        paired_robot_id=old.paired_robot_id,
                    )
                )
                plan.notes.append(
                    f"Replaced {absent_staff_id} with {candidate.staff_id} "
                    f"in zone {old.zone_name}"
                )
            else:
                unreplaced += 1
                plan.notes.append(
                    f"No replacement found for {absent_staff_id} "
                    f"in zone {old.zone_name}"
                )

        plan.assignments = new_assignments

        if unreplaced > 0:
            plan.confidence = round(max(0.0, plan.confidence - (unreplaced * 0.1)), 2)

        await self._save_schedule(plan)
        return plan

    async def add_temporary_task(
        self,
        schedule_id: str,
        zone_id: str,
        zone_name: str,
        task_type: str,
        priority: str = "normal",
    ) -> Optional[SchedulePlan]:
        """Add a temporary task to an existing schedule.

        Finds the staff member with the fewest current assignments and
        assigns them to the new task.  If no staff are available, a
        note is added about understaffing.

        Returns the updated :class:`SchedulePlan`, or ``None`` if the
        schedule does not exist.
        """
        plan = await self._load_schedule(schedule_id)
        if plan is None:
            return None

        # Find the least-loaded staff member
        assignment_counts: Dict[str, int] = {}
        for a in plan.assignments:
            assignment_counts[a.staff_id] = assignment_counts.get(a.staff_id, 0) + 1

        # Get all available staff
        from datetime import date as _date
        parts = plan.date.split("-")
        dt = _date(int(parts[0]), int(parts[1]), int(parts[2]))
        available_staff = await self._staff.get_available_staff(
            building_id=plan.building_id, target_date=dt,
        )
        _available_ids = {s.staff_id for s in available_staff}

        # Find least-loaded among currently assigned staff who are available
        best_candidate: Optional[StaffProfile] = None
        best_count = float("inf")

        for staff in available_staff:
            count = assignment_counts.get(staff.staff_id, 0)
            if count < best_count:
                best_count = count
                best_candidate = staff

        if best_candidate is not None:
            shift = "morning"  # default for temporary tasks
            start_time, end_time = _SHIFT_TIMES.get(shift, ("00:00", "00:00"))

            plan.assignments.append(
                Assignment(
                    staff_id=best_candidate.staff_id,
                    staff_name=best_candidate.name,
                    zone_id=zone_id,
                    zone_name=zone_name,
                    shift=shift,
                    start_time=start_time,
                    end_time=end_time,
                    task_type=task_type,
                )
            )
            plan.notes.append(
                f"Temporary {priority}-priority task ({task_type}) added "
                f"in zone {zone_name}, assigned to {best_candidate.staff_id}"
            )
        else:
            plan.notes.append(
                f"Understaffed: no staff available for temporary "
                f"{priority}-priority task ({task_type}) in zone {zone_name}"
            )

        await self._save_schedule(plan)
        return plan

    # ------------------------------------------------------------------
    # Confirmation & Queries
    # ------------------------------------------------------------------

    async def confirm_schedule(
        self,
        schedule_id: str,
        confirmed_by: str,
    ) -> bool:
        """Confirm a schedule plan.

        Changes the schedule status to ``"confirmed"`` and records who
        confirmed it.

        Returns ``True`` on success, ``False`` if the schedule does not
        exist.
        """
        plan = await self._load_schedule(schedule_id)
        if plan is None:
            return False

        plan.status = "confirmed"
        plan.confirmed_by = confirmed_by
        await self._save_schedule(plan)
        return True

    async def get_schedule(
        self,
        building_id: str,
        target_date: str,
    ) -> Optional[SchedulePlan]:
        """Retrieve a schedule for a building on a given date.

        Returns ``None`` if no schedule is found.
        """
        docs = await self._backend.query(
            _COL_SCHEDULES,
            {"building_id": building_id, "date": target_date},
        )
        if not docs:
            return None
        return self._to_schedule_plan(docs[0])

    async def get_staff_schedule(
        self,
        staff_id: str,
        target_date: str,
    ) -> List[Assignment]:
        """Return all assignments for a staff member on a given date.

        Searches across all schedules for *target_date* and returns
        assignments matching *staff_id*.
        """
        docs = await self._backend.query(
            _COL_SCHEDULES,
            {"date": target_date},
        )
        result: List[Assignment] = []
        for doc in docs:
            for a_dict in doc.get("assignments", []):
                if a_dict.get("staff_id") == staff_id:
                    result.append(self._to_assignment(a_dict))
        return result

    async def get_schedule_adherence(
        self,
        building_id: str,
        target_date: str,
    ) -> float:
        """Calculate schedule adherence as a percentage.

        Returns ``completed_assignments / total_assignments``.  If there
        are no assignments, returns ``0.0``.
        """
        plan = await self.get_schedule(building_id, target_date)
        if plan is None or len(plan.assignments) == 0:
            return 0.0

        # Check workload records for each assigned staff member
        from datetime import date as _date
        parts = target_date.split("-")
        dt = _date(int(parts[0]), int(parts[1]), int(parts[2]))

        total = len(plan.assignments)
        completed = 0

        for a in plan.assignments:
            workload = await self._staff.get_staff_workload(a.staff_id, dt)
            if workload is not None and workload.completed_assignments > 0:
                completed += min(workload.completed_assignments, 1)

        return round(completed / total, 2) if total > 0 else 0.0

    # ------------------------------------------------------------------
    # Internal Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _find_best_candidate(
        available: List[StaffProfile],
        already_assigned: set,
        skills_needed: List[str],
    ) -> Optional[StaffProfile]:
        """Pick the best unassigned candidate.

        Preference order:
        1. Staff member possessing *all* required skills who has not
           been assigned yet.
        2. Staff member possessing *some* required skills.
        3. Any unassigned staff member (when skills_needed is empty or
           no skilled match exists).
        """
        if not available:
            return None

        # Collect candidates not yet assigned
        candidates = [
            s for s in available if s.staff_id not in already_assigned
        ]
        if not candidates:
            return None

        if skills_needed:
            # Try full match first
            for c in candidates:
                if all(sk in c.skills for sk in skills_needed):
                    return c
            # Then partial match (most skills matched)
            best = None
            best_count = 0
            for c in candidates:
                match_count = sum(1 for sk in skills_needed if sk in c.skills)
                if match_count > best_count:
                    best = c
                    best_count = match_count
            if best is not None and best_count > 0:
                return best

        # Fall back to first available candidate
        return candidates[0] if candidates else None

    async def _save_schedule(self, plan: SchedulePlan) -> None:
        """Serialize and persist a schedule plan."""
        data = asdict(plan)
        await self._backend.put(_COL_SCHEDULES, plan.schedule_id, data)

    async def _load_schedule(self, schedule_id: str) -> Optional[SchedulePlan]:
        """Load a schedule plan from storage by ID."""
        data = await self._backend.get(_COL_SCHEDULES, schedule_id)
        if data is None:
            return None
        return self._to_schedule_plan(data)

    @staticmethod
    def _to_schedule_plan(data: Dict[str, Any]) -> SchedulePlan:
        """Reconstruct a :class:`SchedulePlan` from a storage dict."""
        assignments = [
            SmartScheduler._to_assignment(a)
            for a in data.get("assignments", [])
        ]
        robot_assignments = [
            SmartScheduler._to_robot_assignment(r)
            for r in data.get("robot_assignments", [])
        ]
        return SchedulePlan(
            schedule_id=data["schedule_id"],
            building_id=data["building_id"],
            date=data["date"],
            assignments=assignments,
            robot_assignments=robot_assignments,
            status=data.get("status", "draft"),
            confidence=data.get("confidence", 1.0),
            notes=data.get("notes", []),
            generated_at=data.get("generated_at"),
            confirmed_by=data.get("confirmed_by"),
        )

    @staticmethod
    def _to_assignment(data: Dict[str, Any]) -> Assignment:
        """Reconstruct an :class:`Assignment` from a storage dict."""
        return Assignment(
            staff_id=data["staff_id"],
            staff_name=data["staff_name"],
            zone_id=data["zone_id"],
            zone_name=data["zone_name"],
            shift=data["shift"],
            start_time=data["start_time"],
            end_time=data["end_time"],
            task_type=data["task_type"],
            paired_robot_id=data.get("paired_robot_id"),
        )

    @staticmethod
    def _to_robot_assignment(data: Dict[str, Any]) -> RobotAssignment:
        """Reconstruct a :class:`RobotAssignment` from a storage dict."""
        return RobotAssignment(
            robot_id=data["robot_id"],
            zone_id=data["zone_id"],
            shift=data["shift"],
            task_type=data["task_type"],
            battery_level=data.get("battery_level", 100.0),
        )
