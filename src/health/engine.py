"""
health.engine — D4+ Service Health Index (SHI) Engine.

Computes a composite Service Health Index for property management areas
by weighting multiple operational dimensions (cleanliness, tenant
satisfaction, staff attendance, robot availability, complaint response,
and manual assessment).  Supports manual manager assessments, historical
queries, and building-level summaries with trend detection.

All operations delegate to a :class:`StorageBackend` so the service
is storage-agnostic.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from uuid import uuid4

from human_ops.storage import StorageBackend


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class HealthSnapshot:
    """A point-in-time health measurement for a building area."""

    snapshot_id: str
    area_id: str          # e.g. "building_001_3f"
    building_id: str
    timestamp: str        # ISO datetime
    overall_score: float  # 0-100
    dimensions: Dict[str, float] = field(default_factory=dict)
    # Keys: cleanliness, tenant_satisfaction, staff_attendance,
    #        robot_availability, complaint_response, manual_assessment
    data_sources: Dict[str, str] = field(default_factory=dict)


@dataclass
class ManualAssessment:
    """A manual health assessment recorded by a manager or supervisor."""

    assessment_id: str
    area_id: str
    assessor_id: str
    assessor_role: str    # manager / supervisor
    score: float          # 0-100
    dimensions: Dict[str, float] = field(default_factory=dict)
    notes: str = ""
    created_at: str = ""  # ISO datetime


@dataclass
class HealthWeights:
    """Configurable weights for each SHI dimension.  Must sum to 1.0."""

    cleanliness: float = 0.15
    tenant_satisfaction: float = 0.20
    staff_attendance: float = 0.10
    robot_availability: float = 0.10
    complaint_response: float = 0.15
    manual_assessment: float = 0.30


# Storage collection names
_COL_SNAPSHOTS = "health_snapshots"
_COL_ASSESSMENTS = "manual_assessments"


class HealthEngine:
    """D4+ — Service Health Index engine.

    Computes weighted health scores across multiple operational
    dimensions and persists snapshots for trend analysis.

    Parameters
    ----------
    backend:
        A :class:`StorageBackend` for persisting health data.
    weights:
        Optional :class:`HealthWeights` override.  Uses default
        weights when ``None``.
    """

    def __init__(
        self,
        backend: StorageBackend,
        weights: Optional[HealthWeights] = None,
    ) -> None:
        self._backend = backend
        self._weights = weights or HealthWeights()

    # ------------------------------------------------------------------
    # Health Calculation
    # ------------------------------------------------------------------

    async def calculate_health(
        self,
        building_id: str,
        area_id: str,
        metrics: Dict[str, float],
    ) -> HealthSnapshot:
        """Calculate the Service Health Index for an area.

        Parameters
        ----------
        building_id:
            The building this area belongs to.
        area_id:
            Identifier for the specific area (e.g. ``"building_001_3f"``).
        metrics:
            Dict with keys matching :class:`HealthWeights` fields and
            values in the range 0-100.  Missing keys are treated as 0.

        Returns
        -------
        HealthSnapshot
            The computed and persisted snapshot.
        """
        w = self._weights
        weight_map: Dict[str, float] = {
            "cleanliness": w.cleanliness,
            "tenant_satisfaction": w.tenant_satisfaction,
            "staff_attendance": w.staff_attendance,
            "robot_availability": w.robot_availability,
            "complaint_response": w.complaint_response,
            "manual_assessment": w.manual_assessment,
        }

        # Weighted sum: SHI = sum(w_i * score_i)
        overall = 0.0
        dimensions: Dict[str, float] = {}
        for dim, weight in weight_map.items():
            score = metrics.get(dim, 0.0)
            dimensions[dim] = score
            overall += weight * score

        overall = round(overall, 2)

        snapshot = HealthSnapshot(
            snapshot_id=str(uuid4()),
            area_id=area_id,
            building_id=building_id,
            timestamp=datetime.utcnow().isoformat(),
            overall_score=overall,
            dimensions=dimensions,
            data_sources={k: "metric_input" for k in metrics},
        )

        await self._save_snapshot(snapshot)
        return snapshot

    # ------------------------------------------------------------------
    # Manual Assessments
    # ------------------------------------------------------------------

    async def record_manual_assessment(
        self,
        area_id: str,
        assessor_id: str,
        assessor_role: str,
        score: float,
        dimensions: Optional[Dict[str, float]] = None,
        notes: str = "",
    ) -> ManualAssessment:
        """Record a manual assessment from a manager or supervisor.

        Parameters
        ----------
        area_id:
            The area being assessed.
        assessor_id:
            Identifier of the person performing the assessment.
        assessor_role:
            Role of the assessor (e.g. ``"manager"``, ``"supervisor"``).
        score:
            Overall manual score, 0-100.
        dimensions:
            Optional per-dimension breakdown.
        notes:
            Free-text notes about the assessment.

        Returns
        -------
        ManualAssessment
            The persisted assessment record.
        """
        assessment = ManualAssessment(
            assessment_id=str(uuid4()),
            area_id=area_id,
            assessor_id=assessor_id,
            assessor_role=assessor_role,
            score=score,
            dimensions=dimensions or {},
            notes=notes,
            created_at=datetime.utcnow().isoformat(),
        )

        await self._backend.put(
            _COL_ASSESSMENTS,
            assessment.assessment_id,
            asdict(assessment),
        )
        return assessment

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    async def get_latest_health(
        self,
        building_id: str,
        area_id: Optional[str] = None,
    ) -> Optional[HealthSnapshot]:
        """Return the most recent health snapshot for a building/area.

        Parameters
        ----------
        building_id:
            The building to query.
        area_id:
            Optional area filter.  When ``None``, the latest snapshot
            for the entire building is returned.

        Returns
        -------
        Optional[HealthSnapshot]
            The most recent snapshot, or ``None`` if none exist.
        """
        filters: Dict[str, Any] = {"building_id": building_id}
        if area_id is not None:
            filters["area_id"] = area_id

        docs = await self._backend.query(_COL_SNAPSHOTS, filters)
        if not docs:
            return None

        # Sort by timestamp descending, return the most recent
        docs.sort(key=lambda d: d.get("timestamp", ""), reverse=True)
        return self._to_snapshot(docs[0])

    async def get_health_history(
        self,
        building_id: str,
        days: int = 30,
    ) -> List[HealthSnapshot]:
        """Return all health snapshots for a building within a date range.

        Parameters
        ----------
        building_id:
            The building to query.
        days:
            Look-back window in days (default 30).

        Returns
        -------
        List[HealthSnapshot]
            Snapshots within the window, sorted by timestamp ascending.
        """
        cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
        docs = await self._backend.query(
            _COL_SNAPSHOTS,
            {"building_id": building_id},
        )

        results: List[HealthSnapshot] = []
        for doc in docs:
            ts = doc.get("timestamp", "")
            if ts >= cutoff:
                results.append(self._to_snapshot(doc))

        # Sort ascending by timestamp
        results.sort(key=lambda s: s.timestamp)
        return results

    async def get_manual_assessments(
        self,
        area_id: str,
        days: int = 30,
    ) -> List[ManualAssessment]:
        """Return recent manual assessments for an area.

        Parameters
        ----------
        area_id:
            The area to query.
        days:
            Look-back window in days (default 30).

        Returns
        -------
        List[ManualAssessment]
            Assessments within the window, sorted by created_at ascending.
        """
        cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
        docs = await self._backend.query(
            _COL_ASSESSMENTS,
            {"area_id": area_id},
        )

        results: List[ManualAssessment] = []
        for doc in docs:
            ts = doc.get("created_at", "")
            if ts >= cutoff:
                results.append(self._to_assessment(doc))

        results.sort(key=lambda a: a.created_at)
        return results

    async def get_building_summary(
        self,
        building_id: str,
    ) -> Dict[str, Any]:
        """Return a summary of health for a building.

        Returns
        -------
        Dict[str, Any]
            Keys: ``overall_score``, ``dimensions`` (dict of averages),
            ``trend`` (``"improving"``, ``"declining"``, ``"stable"``,
            or ``"insufficient_data"``), ``snapshot_count``.
        """
        docs = await self._backend.query(
            _COL_SNAPSHOTS,
            {"building_id": building_id},
        )

        if not docs:
            return {
                "overall_score": 0.0,
                "dimensions": {},
                "trend": "insufficient_data",
                "snapshot_count": 0,
            }

        # Sort ascending by timestamp for trend calculation
        docs.sort(key=lambda d: d.get("timestamp", ""))

        # Compute averages
        total_score = 0.0
        dim_totals: Dict[str, float] = {}
        dim_counts: Dict[str, int] = {}

        for doc in docs:
            total_score += doc.get("overall_score", 0.0)
            for dim_key, dim_val in doc.get("dimensions", {}).items():
                dim_totals[dim_key] = dim_totals.get(dim_key, 0.0) + dim_val
                dim_counts[dim_key] = dim_counts.get(dim_key, 0) + 1

        count = len(docs)
        avg_score = round(total_score / count, 2)
        avg_dimensions = {
            k: round(dim_totals[k] / dim_counts[k], 2)
            for k in dim_totals
        }

        # Trend: compare last two snapshots
        if count < 2:
            trend = "insufficient_data"
        else:
            prev_score = docs[-2].get("overall_score", 0.0)
            last_score = docs[-1].get("overall_score", 0.0)
            diff = last_score - prev_score
            if diff > 1.0:
                trend = "improving"
            elif diff < -1.0:
                trend = "declining"
            else:
                trend = "stable"

        return {
            "overall_score": avg_score,
            "dimensions": avg_dimensions,
            "trend": trend,
            "snapshot_count": count,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _save_snapshot(self, snapshot: HealthSnapshot) -> None:
        """Serialize and persist a health snapshot."""
        await self._backend.put(
            _COL_SNAPSHOTS,
            snapshot.snapshot_id,
            asdict(snapshot),
        )

    @staticmethod
    def _to_snapshot(data: Dict[str, Any]) -> HealthSnapshot:
        """Reconstruct a :class:`HealthSnapshot` from a storage dict."""
        return HealthSnapshot(
            snapshot_id=data["snapshot_id"],
            area_id=data["area_id"],
            building_id=data["building_id"],
            timestamp=data["timestamp"],
            overall_score=data["overall_score"],
            dimensions=data.get("dimensions", {}),
            data_sources=data.get("data_sources", {}),
        )

    @staticmethod
    def _to_assessment(data: Dict[str, Any]) -> ManualAssessment:
        """Reconstruct a :class:`ManualAssessment` from a storage dict."""
        return ManualAssessment(
            assessment_id=data["assessment_id"],
            area_id=data["area_id"],
            assessor_id=data["assessor_id"],
            assessor_role=data["assessor_role"],
            score=data["score"],
            dimensions=data.get("dimensions", {}),
            notes=data.get("notes", ""),
            created_at=data.get("created_at", ""),
        )
