"""
human_ops.work_order_engine — H4 Work Order Management service.

Provides full lifecycle management for property work orders: creation,
assignment, status tracking, resolution, SLA breach detection, and
aggregate statistics.  All operations delegate to a
:class:`StorageBackend` so the service is storage-agnostic.
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from uuid import uuid4

from human_ops.models import OrderStats, WorkOrder
from human_ops.storage import StorageBackend

# Collection name used in the storage backend
_COL_WORK_ORDERS = "work_orders"


class WorkOrderEngine:
    """H4 -- Work order management service.

    Wraps a :class:`StorageBackend` to provide higher-level operations
    on work orders including CRUD, assignment, resolution, SLA breach
    detection, and aggregate statistics.
    """

    def __init__(self, backend: StorageBackend) -> None:
        self._backend = backend

    # ------------------------------------------------------------------
    # Creation
    # ------------------------------------------------------------------

    async def create_order(self, order: WorkOrder) -> str:
        """Persist a new work order.

        If ``order.order_id`` is empty or ``None`` a UUID is generated.
        Sets ``created_at`` to the current UTC time if not already set.
        Returns the ``order_id``.
        """
        if not order.order_id:
            order.order_id = str(uuid4())
        if not order.created_at:
            order.created_at = datetime.utcnow().isoformat()
        data = asdict(order)
        await self._backend.put(_COL_WORK_ORDERS, order.order_id, data)
        return order.order_id

    # ------------------------------------------------------------------
    # Assignment & Status
    # ------------------------------------------------------------------

    async def assign_order(self, order_id: str, staff_id: str) -> bool:
        """Assign a work order to a staff member.

        Sets ``assigned_to`` and changes status to ``"assigned"``.

        Returns ``True`` on success, ``False`` if the order does not
        exist.
        """
        data = await self._backend.get(_COL_WORK_ORDERS, order_id)
        if data is None:
            return False
        data["assigned_to"] = staff_id
        data["status"] = "assigned"
        order = self._to_work_order(data)
        await self._backend.put(_COL_WORK_ORDERS, order_id, asdict(order))
        return True

    async def update_status(
        self,
        order_id: str,
        status: str,
        notes: str = "",
    ) -> bool:
        """Update the status of a work order.

        If *notes* is provided it is appended to the description.

        Returns ``True`` on success, ``False`` if the order does not
        exist.
        """
        data = await self._backend.get(_COL_WORK_ORDERS, order_id)
        if data is None:
            return False
        data["status"] = status
        if notes:
            existing = data.get("description", "")
            data["description"] = (
                f"{existing}\n[{status}] {notes}" if existing else f"[{status}] {notes}"
            )
        order = self._to_work_order(data)
        await self._backend.put(_COL_WORK_ORDERS, order_id, asdict(order))
        return True

    # ------------------------------------------------------------------
    # Resolution
    # ------------------------------------------------------------------

    async def resolve_order(self, order_id: str, resolution: str) -> bool:
        """Mark a work order as resolved.

        Sets status to ``"resolved"``, records the ``resolved_at``
        timestamp and the *resolution* text.

        Returns ``True`` on success, ``False`` if the order does not
        exist.
        """
        data = await self._backend.get(_COL_WORK_ORDERS, order_id)
        if data is None:
            return False
        data["status"] = "resolved"
        data["resolved_at"] = datetime.utcnow().isoformat()
        data["resolution"] = resolution
        order = self._to_work_order(data)
        await self._backend.put(_COL_WORK_ORDERS, order_id, asdict(order))
        return True

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    async def get_order(self, order_id: str) -> Optional[WorkOrder]:
        """Retrieve a single work order by ID, or ``None`` if not found."""
        data = await self._backend.get(_COL_WORK_ORDERS, order_id)
        if data is None:
            return None
        return self._to_work_order(data)

    async def get_orders(
        self,
        building_id: Optional[str] = None,
        status: Optional[str] = None,
        assigned_to: Optional[str] = None,
    ) -> List[WorkOrder]:
        """Return work orders matching the given filters.

        Any combination of *building_id*, *status*, and *assigned_to*
        is accepted; ``None`` values are ignored.
        """
        filters: Dict[str, Any] = {}
        if building_id is not None:
            filters["building_id"] = building_id
        if status is not None:
            filters["status"] = status
        if assigned_to is not None:
            filters["assigned_to"] = assigned_to
        docs = await self._backend.query(_COL_WORK_ORDERS, filters or None)
        return [self._to_work_order(d) for d in docs]

    # ------------------------------------------------------------------
    # SLA Breach Detection
    # ------------------------------------------------------------------

    async def get_sla_breaches(
        self,
        building_id: Optional[str] = None,
    ) -> List[WorkOrder]:
        """Return work orders that have breached their SLA deadline.

        An order is considered breached when its status is not in
        ``("resolved", "closed")`` and its ``sla_deadline`` is in the
        past.  Optionally filter by *building_id*.
        """
        docs = await self._backend.query(_COL_WORK_ORDERS)
        now_str = datetime.utcnow().isoformat()
        results: List[WorkOrder] = []

        for doc in docs:
            if doc.get("status") in ("resolved", "closed"):
                continue
            sla = doc.get("sla_deadline")
            if not sla:
                continue
            if sla >= now_str:
                continue
            if building_id is not None and doc.get("building_id") != building_id:
                continue
            results.append(self._to_work_order(doc))

        return results

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    async def get_order_stats(
        self,
        building_id: str,
        days: int = 30,
    ) -> OrderStats:
        """Compute aggregate statistics for work orders.

        Parameters
        ----------
        building_id:
            Scope statistics to this building.
        days:
            Look-back window in days (default 30).

        Returns
        -------
        OrderStats
            Aggregated totals, open count, average resolution hours,
            SLA breach count, and breakdown by order type.
        """
        docs = await self._backend.query(_COL_WORK_ORDERS)
        cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()

        total = 0
        open_orders = 0
        sla_breach_count = 0
        resolution_hours: List[float] = []
        by_type: Dict[str, int] = {}
        now_str = datetime.utcnow().isoformat()

        for doc in docs:
            # Filter by building
            if doc.get("building_id") != building_id:
                continue
            # Filter by time window
            created_at = doc.get("created_at", "")
            if created_at < cutoff:
                continue

            total += 1
            order_type = doc.get("order_type", "unknown")
            by_type[order_type] = by_type.get(order_type, 0) + 1

            status = doc.get("status", "open")
            if status not in ("resolved", "closed"):
                open_orders += 1

            # SLA breach detection
            sla = doc.get("sla_deadline")
            if sla and status not in ("resolved", "closed") and sla < now_str:
                sla_breach_count += 1

            # Resolution time calculation
            if doc.get("created_at") and doc.get("resolved_at"):
                try:
                    t_created = datetime.fromisoformat(doc["created_at"])
                    t_resolved = datetime.fromisoformat(doc["resolved_at"])
                    delta_hours = (t_resolved - t_created).total_seconds() / 3600.0
                    resolution_hours.append(delta_hours)
                except (ValueError, TypeError):
                    pass

        avg_resolution = (
            round(sum(resolution_hours) / len(resolution_hours), 2)
            if resolution_hours
            else 0.0
        )

        return OrderStats(
            total_orders=total,
            open_orders=open_orders,
            avg_resolution_hours=avg_resolution,
            sla_breach_count=sla_breach_count,
            by_type=by_type,
        )

    # ------------------------------------------------------------------
    # Dataclass Reconstruction Helper
    # ------------------------------------------------------------------

    @staticmethod
    def _to_work_order(data: Dict[str, Any]) -> WorkOrder:
        """Reconstruct a :class:`WorkOrder` from a storage dict."""
        return WorkOrder(
            order_id=data["order_id"],
            order_type=data["order_type"],
            source=data["source"],
            title=data["title"],
            description=data.get("description", ""),
            priority=data.get("priority", "normal"),
            status=data.get("status", "open"),
            assigned_to=data.get("assigned_to"),
            building_id=data.get("building_id"),
            zone_id=data.get("zone_id"),
            created_at=data.get("created_at"),
            resolved_at=data.get("resolved_at"),
            sla_deadline=data.get("sla_deadline"),
            resolution=data.get("resolution"),
        )
