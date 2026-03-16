"""
human_ops.exception_dispatcher — H3 Exception Dispatch service.

Handles operational exception events (robot errors, complaints, urgent
cleaning, equipment faults) by finding and dispatching available staff.
Autonomy checks are simulated with priority-based rules; notifications
are logged but not actually sent (V8 Phase 1 simplification).

All methods are async.  Persistence is delegated to a
:class:`StorageBackend` so the service is storage-agnostic.
"""

from __future__ import annotations

import logging
from dataclasses import asdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from uuid import uuid4

from human_ops.models import (
    DispatchRecord,
    DispatchResult,
    DispatchStats,
    ExceptionEvent,
    StaffProfile,
)
from human_ops.staff_manager import StaffManager
from human_ops.storage import StorageBackend

logger = logging.getLogger(__name__)

# Storage collection name for dispatch records.
_COL_DISPATCH = "dispatch_records"

# Mapping from event_type to the preferred staff skill.
_SKILL_MAP: Dict[str, str] = {
    "robot_error": "robot_rescue",
    "complaint": "vip_service",
    "urgent_clean": "floor_cleaning",
    "equipment_fault": "elevator_rescue",
}

# Mapping from priority to autonomy level (float encoding).
# L0 = 0.0 (log only), L1 = 1.0 (suggest), L2 = 2.0 (dispatch + notify),
# L3 = 3.0 (auto-dispatch).
_AUTONOMY_MAP: Dict[str, float] = {
    "critical": 3.0,
    "high": 2.0,
    "normal": 1.0,
    "low": 0.0,
}

# Estimated response minutes by priority (simple heuristic).
_RESPONSE_ESTIMATE: Dict[str, float] = {
    "critical": 5.0,
    "high": 10.0,
    "normal": 20.0,
    "low": 60.0,
}


class ExceptionDispatcher:
    """H3 -- Exception dispatch service.

    Coordinates the response to operational exceptions by matching
    available staff to incoming events based on skill requirements,
    priority-based autonomy rules, and building affiliation.

    Parameters
    ----------
    staff_manager:
        An :class:`StaffManager` instance used to query available and
        qualified staff (H1 dependency).
    backend:
        A :class:`StorageBackend` for persisting dispatch records.
    """

    def __init__(
        self,
        staff_manager: StaffManager,
        backend: StorageBackend,
    ) -> None:
        self._staff = staff_manager
        self._backend = backend

    # ------------------------------------------------------------------
    # Core dispatch
    # ------------------------------------------------------------------

    async def dispatch(self, event: ExceptionEvent) -> DispatchResult:
        """Dispatch staff for an operational exception.

        The algorithm:
        1. Determine the required skill from ``event.event_type``.
        2. Find available staff in the building via H1.
        3. Sort candidates so those with the matching skill appear first.
        4. Determine the autonomy level from ``event.priority``.
        5. Decide the initial status (dispatched / pending_approval /
           no_available_staff).
        6. Persist a :class:`DispatchRecord` and return a
           :class:`DispatchResult`.

        Returns
        -------
        DispatchResult
            Always returned; check ``status`` for the outcome.
        """
        dispatch_id = str(uuid4())
        required_skill = _SKILL_MAP.get(event.event_type, "")
        autonomy = _AUTONOMY_MAP.get(event.priority, 1.0)
        now_str = datetime.utcnow().isoformat()

        # Ensure event has a creation timestamp.
        if not event.created_at:
            event.created_at = now_str

        # --- Find candidates ---
        candidates = await self._staff.get_available_staff(
            building_id=event.building_id,
        )

        if not candidates:
            result = DispatchResult(
                dispatch_id=dispatch_id,
                status="no_available_staff",
                autonomy_level=autonomy,
                estimated_response_minutes=_RESPONSE_ESTIMATE.get(
                    event.priority, 20.0
                ),
            )
            record = DispatchRecord(
                dispatch_id=dispatch_id,
                event=event,
                result=result,
                dispatched_at=now_str,
            )
            await self._save_record(record)
            return result

        # --- Rank candidates: matching skill first ---
        assigned = self._pick_candidate(candidates, required_skill)

        # --- Determine status from autonomy level ---
        if autonomy >= 2.0:  # L2 or L3
            status = "dispatched"
        else:  # L1 or L0
            status = "pending_approval"

        result = DispatchResult(
            dispatch_id=dispatch_id,
            assigned_to=assigned.staff_id,
            assigned_name=assigned.name,
            status=status,
            autonomy_level=autonomy,
            estimated_response_minutes=_RESPONSE_ESTIMATE.get(
                event.priority, 20.0
            ),
        )

        record = DispatchRecord(
            dispatch_id=dispatch_id,
            event=event,
            result=result,
            dispatched_at=now_str,
        )

        await self._save_record(record)

        logger.info(
            "Dispatched %s to %s (%s) for %s [autonomy=L%d]",
            dispatch_id,
            assigned.name,
            assigned.staff_id,
            event.event_type,
            int(autonomy),
        )
        return result

    # ------------------------------------------------------------------
    # Lifecycle transitions
    # ------------------------------------------------------------------

    async def accept_dispatch(
        self,
        dispatch_id: str,
        staff_id: str,
    ) -> bool:
        """Mark a dispatch as accepted by the assigned staff member.

        Parameters
        ----------
        dispatch_id:
            The dispatch to accept.
        staff_id:
            The staff member accepting (must match assigned_to).

        Returns
        -------
        bool
            ``True`` on success, ``False`` if the record does not exist.
        """
        record = await self._load_record(dispatch_id)
        if record is None:
            return False

        record.result.status = "accepted"
        record.accepted_at = datetime.utcnow().isoformat()
        await self._save_record(record)
        return True

    async def resolve_dispatch(
        self,
        dispatch_id: str,
        notes: str = "",
    ) -> bool:
        """Mark a dispatch as resolved.

        Parameters
        ----------
        dispatch_id:
            The dispatch to resolve.
        notes:
            Optional resolution notes.

        Returns
        -------
        bool
            ``True`` on success, ``False`` if the record does not exist.
        """
        record = await self._load_record(dispatch_id)
        if record is None:
            return False

        record.result.status = "resolved"
        record.resolved_at = datetime.utcnow().isoformat()
        record.resolution_notes = notes
        await self._save_record(record)
        return True

    async def escalate(
        self,
        dispatch_id: str,
        reason: str = "",
    ) -> Optional[DispatchResult]:
        """Escalate a dispatch to a different staff member.

        The current record is marked ``escalated``.  A replacement is
        sought from available staff (excluding the currently assigned
        member).  If a replacement is found a new :class:`DispatchResult`
        is returned; otherwise ``None``.

        Parameters
        ----------
        dispatch_id:
            The dispatch to escalate.
        reason:
            Optional escalation reason (stored in resolution_notes).

        Returns
        -------
        Optional[DispatchResult]
            A new dispatch result when a replacement is found, else
            ``None``.
        """
        record = await self._load_record(dispatch_id)
        if record is None:
            return None

        # Mark the current record as escalated.
        record.result.status = "escalated"
        record.resolution_notes = reason or "escalated"
        await self._save_record(record)

        # Try to find a replacement.
        event = record.event
        required_skill = _SKILL_MAP.get(event.event_type, "")
        candidates = await self._staff.get_available_staff(
            building_id=event.building_id,
        )

        # Exclude the currently assigned staff member.
        current_id = record.result.assigned_to
        candidates = [c for c in candidates if c.staff_id != current_id]

        if not candidates:
            logger.warning(
                "Escalation %s: no replacement staff available", dispatch_id
            )
            return None

        # Pick the best replacement.
        assigned = self._pick_candidate(candidates, required_skill)
        autonomy = _AUTONOMY_MAP.get(event.priority, 1.0)
        new_dispatch_id = str(uuid4())

        new_result = DispatchResult(
            dispatch_id=new_dispatch_id,
            assigned_to=assigned.staff_id,
            assigned_name=assigned.name,
            status="dispatched",
            autonomy_level=autonomy,
            estimated_response_minutes=_RESPONSE_ESTIMATE.get(
                event.priority, 20.0
            ),
        )

        new_record = DispatchRecord(
            dispatch_id=new_dispatch_id,
            event=event,
            result=new_result,
            dispatched_at=datetime.utcnow().isoformat(),
        )
        await self._save_record(new_record)

        logger.info(
            "Escalated %s -> %s (assigned to %s)",
            dispatch_id,
            new_dispatch_id,
            assigned.staff_id,
        )
        return new_result

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    async def get_pending_dispatches(
        self,
        building_id: Optional[str] = None,
    ) -> List[DispatchRecord]:
        """Return dispatch records that are still actionable.

        Actionable statuses are ``dispatched`` and ``pending_approval``.
        Optionally filter by *building_id*.

        Returns
        -------
        List[DispatchRecord]
            Matching records, possibly empty.
        """
        docs = await self._backend.query(_COL_DISPATCH)
        results: List[DispatchRecord] = []
        for doc in docs:
            record = self._to_dispatch_record(doc)
            if record.result.status not in ("dispatched", "pending_approval"):
                continue
            if building_id is not None and record.event.building_id != building_id:
                continue
            results.append(record)
        return results

    async def get_dispatch_stats(
        self,
        building_id: str,
        days: int = 7,
    ) -> DispatchStats:
        """Compute aggregate statistics for exception dispatches.

        Parameters
        ----------
        building_id:
            Scope statistics to this building.
        days:
            Look-back window in days (default 7).

        Returns
        -------
        DispatchStats
            Aggregated totals and rates.
        """
        docs = await self._backend.query(_COL_DISPATCH)
        cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()

        total = 0
        resolved = 0
        escalated = 0
        response_times: List[float] = []
        by_priority: Dict[str, int] = {}

        for doc in docs:
            record = self._to_dispatch_record(doc)
            # Filter by building.
            if record.event.building_id != building_id:
                continue
            # Filter by time window.
            dispatched_at = record.dispatched_at or ""
            if dispatched_at < cutoff:
                continue

            total += 1
            priority = record.event.priority
            by_priority[priority] = by_priority.get(priority, 0) + 1

            if record.result.status == "resolved":
                resolved += 1
            if record.result.status == "escalated":
                escalated += 1

            # Compute response time if accepted_at is available.
            if record.dispatched_at and record.accepted_at:
                try:
                    t_dispatch = datetime.fromisoformat(record.dispatched_at)
                    t_accept = datetime.fromisoformat(record.accepted_at)
                    delta_min = (t_accept - t_dispatch).total_seconds() / 60.0
                    response_times.append(delta_min)
                except (ValueError, TypeError):
                    pass

        avg_response = (
            sum(response_times) / len(response_times)
            if response_times
            else 0.0
        )
        resolution_rate = (resolved / total) if total > 0 else 0.0
        escalation_rate = (escalated / total) if total > 0 else 0.0

        return DispatchStats(
            total_dispatches=total,
            avg_response_minutes=round(avg_response, 2),
            resolution_rate=round(resolution_rate, 4),
            escalation_rate=round(escalation_rate, 4),
            by_priority=by_priority,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _pick_candidate(
        candidates: List[StaffProfile],
        required_skill: str,
    ) -> StaffProfile:
        """Pick the best candidate from *candidates*.

        Candidates with the required skill are preferred.  Within each
        group the original ordering (from the staff manager) is kept.
        Falls back to the first candidate when nobody has the skill.
        """
        with_skill = [c for c in candidates if required_skill in c.skills]
        if with_skill:
            return with_skill[0]
        return candidates[0]

    async def _save_record(self, record: DispatchRecord) -> None:
        """Serialize and persist a dispatch record."""
        data = self._record_to_dict(record)
        await self._backend.put(_COL_DISPATCH, record.dispatch_id, data)

    async def _load_record(
        self,
        dispatch_id: str,
    ) -> Optional[DispatchRecord]:
        """Load and deserialize a dispatch record."""
        data = await self._backend.get(_COL_DISPATCH, dispatch_id)
        if data is None:
            return None
        return self._to_dispatch_record(data)

    # ------------------------------------------------------------------
    # Serialization helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _record_to_dict(record: DispatchRecord) -> Dict[str, Any]:
        """Convert a :class:`DispatchRecord` to a plain dict for storage.

        Nested dataclasses (:class:`ExceptionEvent`, :class:`DispatchResult`)
        are serialized via ``dataclasses.asdict``.
        """
        return {
            "dispatch_id": record.dispatch_id,
            "event": asdict(record.event),
            "result": asdict(record.result),
            "dispatched_at": record.dispatched_at,
            "accepted_at": record.accepted_at,
            "resolved_at": record.resolved_at,
            "resolution_notes": record.resolution_notes,
        }

    @staticmethod
    def _to_dispatch_record(data: Dict[str, Any]) -> DispatchRecord:
        """Reconstruct a :class:`DispatchRecord` from a storage dict."""
        event_data = data["event"]
        result_data = data["result"]

        event = ExceptionEvent(
            event_type=event_data["event_type"],
            source=event_data["source"],
            building_id=event_data["building_id"],
            zone_id=event_data["zone_id"],
            priority=event_data.get("priority", "normal"),
            description=event_data.get("description", ""),
            robot_id=event_data.get("robot_id"),
            created_at=event_data.get("created_at"),
        )

        # Strip the class-level _VALID_STATUSES that asdict may include.
        result = DispatchResult(
            dispatch_id=result_data["dispatch_id"],
            assigned_to=result_data.get("assigned_to"),
            assigned_name=result_data.get("assigned_name"),
            status=result_data.get("status", "pending_approval"),
            autonomy_level=result_data.get("autonomy_level", 0.0),
            estimated_response_minutes=result_data.get(
                "estimated_response_minutes", 0.0
            ),
        )

        return DispatchRecord(
            dispatch_id=data["dispatch_id"],
            event=event,
            result=result,
            dispatched_at=data.get("dispatched_at"),
            accepted_at=data.get("accepted_at"),
            resolved_at=data.get("resolved_at"),
            resolution_notes=data.get("resolution_notes"),
        )
