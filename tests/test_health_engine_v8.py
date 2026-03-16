"""
Tests for D4+ HealthEngine module (V8).

Covers health calculation, manual assessments, queries, and edge cases.
All tests use MemoryBackend and are fully self-contained.

Run:  PYTHONPATH=src pytest tests/test_health_engine_v8.py -v
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from datetime import datetime, timedelta

from human_ops.storage import StorageBackend, MemoryBackend
from health.engine import HealthEngine, HealthWeights, HealthSnapshot, ManualAssessment

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def backend():
    return MemoryBackend()


@pytest_asyncio.fixture
async def engine(backend):
    return HealthEngine(backend)


def _full_metrics(
    cleanliness=80.0,
    tenant_satisfaction=90.0,
    staff_attendance=85.0,
    robot_availability=95.0,
    complaint_response=70.0,
    manual_assessment=88.0,
):
    """Return a complete metrics dict with optional overrides."""
    return {
        "cleanliness": cleanliness,
        "tenant_satisfaction": tenant_satisfaction,
        "staff_attendance": staff_attendance,
        "robot_availability": robot_availability,
        "complaint_response": complaint_response,
        "manual_assessment": manual_assessment,
    }


# ===================================================================
# 1. calculate_health (5 tests)
# ===================================================================

async def test_calculate_health_basic(engine):
    """test_calculate_health_basic -- returns a HealthSnapshot with correct fields."""
    snapshot = await engine.calculate_health("b001", "b001_3f", _full_metrics())

    assert isinstance(snapshot, HealthSnapshot)
    assert snapshot.building_id == "b001"
    assert snapshot.area_id == "b001_3f"
    assert snapshot.snapshot_id  # non-empty
    assert snapshot.timestamp  # non-empty
    assert 0 <= snapshot.overall_score <= 100


async def test_calculate_health_all_dimensions(engine):
    """test_calculate_health_all_dimensions -- all six dimensions are recorded."""
    metrics = _full_metrics()
    snapshot = await engine.calculate_health("b001", "b001_3f", metrics)

    expected_keys = {
        "cleanliness", "tenant_satisfaction", "staff_attendance",
        "robot_availability", "complaint_response", "manual_assessment",
    }
    assert set(snapshot.dimensions.keys()) == expected_keys
    for key in expected_keys:
        assert snapshot.dimensions[key] == metrics[key]


async def test_calculate_health_weighted_formula(engine):
    """test_calculate_health_weighted_formula -- SHI = sum(w_i * score_i)."""
    metrics = _full_metrics()
    snapshot = await engine.calculate_health("b001", "b001_3f", metrics)

    w = HealthWeights()
    expected = (
        w.cleanliness * 80.0
        + w.tenant_satisfaction * 90.0
        + w.staff_attendance * 85.0
        + w.robot_availability * 95.0
        + w.complaint_response * 70.0
        + w.manual_assessment * 88.0
    )
    assert snapshot.overall_score == round(expected, 2)


async def test_calculate_health_saves_snapshot(engine, backend):
    """test_calculate_health_saves_snapshot -- snapshot is persisted in storage."""
    snapshot = await engine.calculate_health("b001", "b001_3f", _full_metrics())

    stored = await backend.get("health_snapshots", snapshot.snapshot_id)
    assert stored is not None
    assert stored["building_id"] == "b001"
    assert stored["area_id"] == "b001_3f"
    assert stored["overall_score"] == snapshot.overall_score


async def test_calculate_health_custom_weights(backend):
    """test_calculate_health_custom_weights -- custom weights change the score."""
    custom_weights = HealthWeights(
        cleanliness=0.50,
        tenant_satisfaction=0.10,
        staff_attendance=0.10,
        robot_availability=0.10,
        complaint_response=0.10,
        manual_assessment=0.10,
    )
    engine = HealthEngine(backend, weights=custom_weights)

    # Cleanliness-heavy: 100 cleanliness, 0 everything else
    metrics = {
        "cleanliness": 100.0,
        "tenant_satisfaction": 0.0,
        "staff_attendance": 0.0,
        "robot_availability": 0.0,
        "complaint_response": 0.0,
        "manual_assessment": 0.0,
    }
    snapshot = await engine.calculate_health("b001", "b001_3f", metrics)
    # 0.50 * 100 + 0.10 * 0 * 5 = 50.0
    assert snapshot.overall_score == 50.0


# ===================================================================
# 2. manual_assessment (4 tests)
# ===================================================================

async def test_record_manual_assessment(engine):
    """test_record_manual_assessment -- creates and returns a ManualAssessment."""
    assessment = await engine.record_manual_assessment(
        area_id="b001_3f",
        assessor_id="mgr_001",
        assessor_role="manager",
        score=85.0,
        notes="Lobby looks great",
    )

    assert isinstance(assessment, ManualAssessment)
    assert assessment.area_id == "b001_3f"
    assert assessment.assessor_id == "mgr_001"
    assert assessment.assessor_role == "manager"
    assert assessment.score == 85.0
    assert assessment.notes == "Lobby looks great"
    assert assessment.created_at  # non-empty


async def test_get_manual_assessments_by_area(engine):
    """test_get_manual_assessments_by_area -- retrieves assessments for a specific area."""
    await engine.record_manual_assessment("b001_3f", "mgr_001", "manager", 80.0)
    await engine.record_manual_assessment("b001_3f", "mgr_002", "supervisor", 90.0)
    await engine.record_manual_assessment("b002_1f", "mgr_003", "manager", 75.0)

    results = await engine.get_manual_assessments("b001_3f")
    assert len(results) == 2
    area_ids = {r.area_id for r in results}
    assert area_ids == {"b001_3f"}


async def test_manual_assessment_multiple_assessors(engine):
    """test_manual_assessment_multiple_assessors -- different assessors are tracked."""
    a1 = await engine.record_manual_assessment("b001_3f", "mgr_001", "manager", 80.0)
    a2 = await engine.record_manual_assessment("b001_3f", "sup_001", "supervisor", 90.0)

    assert a1.assessor_id == "mgr_001"
    assert a2.assessor_id == "sup_001"
    assert a1.assessment_id != a2.assessment_id


async def test_manual_assessment_empty_area(engine):
    """test_manual_assessment_empty_area -- no assessments returns empty list."""
    results = await engine.get_manual_assessments("nonexistent_area")
    assert results == []


# ===================================================================
# 3. queries (5 tests)
# ===================================================================

async def test_get_latest_health(engine, backend):
    """test_get_latest_health -- returns the most recent snapshot."""
    # Insert an older snapshot directly with an explicit earlier timestamp
    old_snapshot = {
        "snapshot_id": "old_snap_001",
        "area_id": "b001_3f",
        "building_id": "b001",
        "timestamp": "2026-01-01T00:00:00",
        "overall_score": 50.0,
        "dimensions": {"cleanliness": 70.0},
        "data_sources": {},
    }
    await backend.put("health_snapshots", "old_snap_001", old_snapshot)

    # Calculate a new snapshot (will have a current timestamp, always later)
    await engine.calculate_health("b001", "b001_3f", _full_metrics(cleanliness=90.0))

    latest = await engine.get_latest_health("b001", "b001_3f")
    assert latest is not None
    # The latest snapshot should have cleanliness=90 (not the old 70)
    assert latest.dimensions["cleanliness"] == 90.0


async def test_get_health_history(engine):
    """test_get_health_history -- returns all snapshots within date range."""
    await engine.calculate_health("b001", "b001_3f", _full_metrics(cleanliness=70.0))
    await engine.calculate_health("b001", "b001_3f", _full_metrics(cleanliness=80.0))
    await engine.calculate_health("b001", "b001_3f", _full_metrics(cleanliness=90.0))

    history = await engine.get_health_history("b001", days=30)
    assert len(history) == 3


async def test_get_building_summary(engine):
    """test_get_building_summary -- returns averages and snapshot count."""
    await engine.calculate_health("b001", "b001_3f", _full_metrics(cleanliness=70.0))
    await engine.calculate_health("b001", "b001_5f", _full_metrics(cleanliness=90.0))

    summary = await engine.get_building_summary("b001")
    assert summary["snapshot_count"] == 2
    assert summary["overall_score"] > 0
    assert "cleanliness" in summary["dimensions"]


async def test_get_building_summary_with_trend(engine):
    """test_get_building_summary_with_trend -- trend is detected from last 2 snapshots."""
    # First snapshot: low score
    await engine.calculate_health("b001", "b001_3f", _full_metrics(
        cleanliness=50.0, tenant_satisfaction=50.0, staff_attendance=50.0,
        robot_availability=50.0, complaint_response=50.0, manual_assessment=50.0,
    ))
    # Second snapshot: much higher score
    await engine.calculate_health("b001", "b001_3f", _full_metrics(
        cleanliness=95.0, tenant_satisfaction=95.0, staff_attendance=95.0,
        robot_availability=95.0, complaint_response=95.0, manual_assessment=95.0,
    ))

    summary = await engine.get_building_summary("b001")
    assert summary["trend"] == "improving"


async def test_get_building_summary_no_data(engine):
    """test_get_building_summary_no_data -- returns zeros and insufficient_data."""
    summary = await engine.get_building_summary("nonexistent")
    assert summary["overall_score"] == 0.0
    assert summary["dimensions"] == {}
    assert summary["trend"] == "insufficient_data"
    assert summary["snapshot_count"] == 0


# ===================================================================
# 4. edge_cases (6 tests)
# ===================================================================

async def test_perfect_score(engine):
    """test_perfect_score -- all 100s yields 100.0 overall."""
    metrics = {k: 100.0 for k in [
        "cleanliness", "tenant_satisfaction", "staff_attendance",
        "robot_availability", "complaint_response", "manual_assessment",
    ]}
    snapshot = await engine.calculate_health("b001", "b001_3f", metrics)
    assert snapshot.overall_score == 100.0


async def test_zero_scores(engine):
    """test_zero_scores -- all 0s yields 0.0 overall."""
    metrics = {k: 0.0 for k in [
        "cleanliness", "tenant_satisfaction", "staff_attendance",
        "robot_availability", "complaint_response", "manual_assessment",
    ]}
    snapshot = await engine.calculate_health("b001", "b001_3f", metrics)
    assert snapshot.overall_score == 0.0


async def test_partial_metrics(engine):
    """test_partial_metrics -- missing keys are treated as 0."""
    metrics = {"cleanliness": 100.0}  # only one dimension
    snapshot = await engine.calculate_health("b001", "b001_3f", metrics)

    # Only cleanliness contributes: 0.15 * 100 = 15.0
    w = HealthWeights()
    expected = w.cleanliness * 100.0
    assert snapshot.overall_score == round(expected, 2)


async def test_building_isolation(engine):
    """test_building_isolation -- snapshots from different buildings don't mix."""
    await engine.calculate_health("b001", "b001_3f", _full_metrics(cleanliness=90.0))
    await engine.calculate_health("b002", "b002_1f", _full_metrics(cleanliness=50.0))

    latest_b001 = await engine.get_latest_health("b001")
    latest_b002 = await engine.get_latest_health("b002")

    assert latest_b001 is not None
    assert latest_b002 is not None
    assert latest_b001.building_id == "b001"
    assert latest_b002.building_id == "b002"
    assert latest_b001.dimensions["cleanliness"] == 90.0
    assert latest_b002.dimensions["cleanliness"] == 50.0


async def test_area_filter(engine):
    """test_area_filter -- get_latest_health respects area_id filter."""
    await engine.calculate_health("b001", "b001_3f", _full_metrics(cleanliness=70.0))
    await engine.calculate_health("b001", "b001_5f", _full_metrics(cleanliness=95.0))

    latest_3f = await engine.get_latest_health("b001", area_id="b001_3f")
    latest_5f = await engine.get_latest_health("b001", area_id="b001_5f")

    assert latest_3f is not None
    assert latest_5f is not None
    assert latest_3f.dimensions["cleanliness"] == 70.0
    assert latest_5f.dimensions["cleanliness"] == 95.0


async def test_multiple_areas(engine):
    """test_multiple_areas -- building summary includes all areas."""
    await engine.calculate_health("b001", "b001_1f", _full_metrics(cleanliness=60.0))
    await engine.calculate_health("b001", "b001_2f", _full_metrics(cleanliness=70.0))
    await engine.calculate_health("b001", "b001_3f", _full_metrics(cleanliness=80.0))

    summary = await engine.get_building_summary("b001")
    assert summary["snapshot_count"] == 3
    # Average cleanliness should be (60+70+80)/3 = 70.0
    assert summary["dimensions"]["cleanliness"] == 70.0
