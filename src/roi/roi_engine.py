"""
roi.roi_engine — D5 ROI Statistics Engine.

Computes and tracks Return on Investment metrics for property management
buildings operating with human-robot collaboration.  Key indicators
include managed area per person, task completion rates, robot utilization,
human-robot ratios, cost savings, and efficiency improvements versus
a baseline.

All operations delegate to a :class:`StorageBackend` so the service
is storage-agnostic.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from uuid import uuid4

from human_ops.storage import StorageBackend


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class ROIMetrics:
    """Daily ROI metrics for a building."""

    building_id: str
    date: str                          # ISO date (YYYY-MM-DD)
    managed_area_per_person: float     # sq meters per staff
    task_completion_rate: float        # 0-1
    robot_utilization_rate: float      # 0-1
    human_robot_ratio: float           # e.g. 2.5 means 2.5 humans per robot
    cost_savings_monthly: float        # estimated monthly savings
    efficiency_vs_baseline: float      # percentage improvement (0-100+)
    service_health_index: float        # SHI score 0-100


# Storage collection name
_COL_ROI = "roi_metrics"


class ROIEngine:
    """D5 — ROI statistics engine.

    Calculates daily operational metrics that demonstrate the value
    of human-robot collaboration in property management.

    Parameters
    ----------
    backend:
        A :class:`StorageBackend` for persisting ROI data.
    """

    def __init__(self, backend: StorageBackend) -> None:
        self._backend = backend

    # ------------------------------------------------------------------
    # Metric Calculation
    # ------------------------------------------------------------------

    async def calculate_daily_metrics(
        self,
        building_id: str,
        target_date: str,
        stats: Dict[str, Any],
    ) -> ROIMetrics:
        """Calculate and persist daily ROI metrics for a building.

        Parameters
        ----------
        building_id:
            The building being measured.
        target_date:
            ISO date string (``YYYY-MM-DD``).
        stats:
            Input statistics dict with the following keys:

            - ``total_area`` (float): total managed area in sq meters
            - ``staff_count`` (int): number of active staff
            - ``robot_count`` (int): number of active robots
            - ``tasks_completed`` (int): tasks completed today
            - ``tasks_total`` (int): total tasks assigned today
            - ``robot_hours`` (float): hours robots were operational
            - ``total_hours`` (float): total available operational hours
            - ``baseline_cost`` (float): cost without robot collaboration
            - ``current_cost`` (float): current cost with collaboration
            - ``shi_score`` (float): Service Health Index score 0-100

        Returns
        -------
        ROIMetrics
            The computed and persisted metrics.
        """
        total_area = stats.get("total_area", 0.0)
        staff_count = stats.get("staff_count", 0)
        robot_count = stats.get("robot_count", 0)
        tasks_completed = stats.get("tasks_completed", 0)
        tasks_total = stats.get("tasks_total", 0)
        robot_hours = stats.get("robot_hours", 0.0)
        total_hours = stats.get("total_hours", 0.0)
        baseline_cost = stats.get("baseline_cost", 0.0)
        current_cost = stats.get("current_cost", 0.0)
        shi_score = stats.get("shi_score", 0.0)

        # Managed area per person (avoid division by zero)
        managed_area_per_person = (
            total_area / staff_count if staff_count > 0 else 0.0
        )

        # Task completion rate
        task_completion_rate = (
            tasks_completed / tasks_total if tasks_total > 0 else 0.0
        )

        # Robot utilization rate
        robot_utilization_rate = (
            robot_hours / total_hours if total_hours > 0 else 0.0
        )

        # Human-robot ratio
        human_robot_ratio = (
            staff_count / robot_count if robot_count > 0 else 0.0
        )

        # Cost savings (monthly estimate from daily difference * 30)
        daily_savings = baseline_cost - current_cost
        cost_savings_monthly = daily_savings * 30.0

        # Efficiency vs baseline (percentage improvement)
        efficiency_vs_baseline = (
            ((baseline_cost - current_cost) / baseline_cost) * 100.0
            if baseline_cost > 0
            else 0.0
        )

        metrics = ROIMetrics(
            building_id=building_id,
            date=target_date,
            managed_area_per_person=round(managed_area_per_person, 2),
            task_completion_rate=round(task_completion_rate, 4),
            robot_utilization_rate=round(robot_utilization_rate, 4),
            human_robot_ratio=round(human_robot_ratio, 2),
            cost_savings_monthly=round(cost_savings_monthly, 2),
            efficiency_vs_baseline=round(efficiency_vs_baseline, 2),
            service_health_index=round(shi_score, 2),
        )

        # Use building_id:date as key to allow overwrite on same date
        key = f"{building_id}:{target_date}"
        await self._backend.put(_COL_ROI, key, asdict(metrics))
        return metrics

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    async def get_metrics(
        self,
        building_id: str,
        target_date: str,
    ) -> Optional[ROIMetrics]:
        """Retrieve ROI metrics for a building on a specific date.

        Returns ``None`` if no metrics exist for that date.
        """
        key = f"{building_id}:{target_date}"
        data = await self._backend.get(_COL_ROI, key)
        if data is None:
            return None
        return self._to_metrics(data)

    async def get_trend(
        self,
        building_id: str,
        days: int = 90,
    ) -> List[ROIMetrics]:
        """Return ROI metrics for a building over a date range.

        Parameters
        ----------
        building_id:
            The building to query.
        days:
            Look-back window in days (default 90).

        Returns
        -------
        List[ROIMetrics]
            Metrics within the window, sorted by date ascending.
        """
        cutoff = (
            datetime.utcnow() - timedelta(days=days)
        ).strftime("%Y-%m-%d")

        docs = await self._backend.query(
            _COL_ROI,
            {"building_id": building_id},
        )

        results: List[ROIMetrics] = []
        for doc in docs:
            if doc.get("date", "") >= cutoff:
                results.append(self._to_metrics(doc))

        results.sort(key=lambda m: m.date)
        return results

    async def get_comparison(
        self,
        building_ids: List[str],
    ) -> Dict[str, ROIMetrics]:
        """Return the latest ROI metrics for each building in the list.

        Parameters
        ----------
        building_ids:
            List of building identifiers to compare.

        Returns
        -------
        Dict[str, ROIMetrics]
            Mapping of building_id to its latest :class:`ROIMetrics`.
            Buildings with no data are omitted from the result.
        """
        result: Dict[str, ROIMetrics] = {}

        for bid in building_ids:
            docs = await self._backend.query(
                _COL_ROI,
                {"building_id": bid},
            )
            if not docs:
                continue

            # Find the most recent by date
            docs.sort(key=lambda d: d.get("date", ""), reverse=True)
            result[bid] = self._to_metrics(docs[0])

        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _to_metrics(data: Dict[str, Any]) -> ROIMetrics:
        """Reconstruct a :class:`ROIMetrics` from a storage dict."""
        return ROIMetrics(
            building_id=data["building_id"],
            date=data["date"],
            managed_area_per_person=data.get("managed_area_per_person", 0.0),
            task_completion_rate=data.get("task_completion_rate", 0.0),
            robot_utilization_rate=data.get("robot_utilization_rate", 0.0),
            human_robot_ratio=data.get("human_robot_ratio", 0.0),
            cost_savings_monthly=data.get("cost_savings_monthly", 0.0),
            efficiency_vs_baseline=data.get("efficiency_vs_baseline", 0.0),
            service_health_index=data.get("service_health_index", 0.0),
        )
