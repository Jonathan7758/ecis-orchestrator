"""
Tests for D5 ROIEngine module (V8).

Covers metric calculation, queries, and edge cases.
All tests use MemoryBackend and are fully self-contained.

Run:  PYTHONPATH=src pytest tests/test_roi_engine.py -v
"""

from __future__ import annotations

import pytest
import pytest_asyncio

from human_ops.storage import StorageBackend, MemoryBackend
from roi.roi_engine import ROIEngine, ROIMetrics

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def backend():
    return MemoryBackend()


@pytest_asyncio.fixture
async def engine(backend):
    return ROIEngine(backend)


def _sample_stats(
    total_area=10000.0,
    staff_count=20,
    robot_count=5,
    tasks_completed=90,
    tasks_total=100,
    robot_hours=40.0,
    total_hours=80.0,
    baseline_cost=5000.0,
    current_cost=3500.0,
    shi_score=85.0,
):
    """Return a complete stats dict with optional overrides."""
    return {
        "total_area": total_area,
        "staff_count": staff_count,
        "robot_count": robot_count,
        "tasks_completed": tasks_completed,
        "tasks_total": tasks_total,
        "robot_hours": robot_hours,
        "total_hours": total_hours,
        "baseline_cost": baseline_cost,
        "current_cost": current_cost,
        "shi_score": shi_score,
    }


# ===================================================================
# 1. calculate (5 tests)
# ===================================================================

async def test_calculate_basic_metrics(engine):
    """test_calculate_basic_metrics -- returns an ROIMetrics with correct fields."""
    metrics = await engine.calculate_daily_metrics("b001", "2026-03-15", _sample_stats())

    assert isinstance(metrics, ROIMetrics)
    assert metrics.building_id == "b001"
    assert metrics.date == "2026-03-15"
    assert metrics.service_health_index == 85.0


async def test_calculate_area_per_person(engine):
    """test_calculate_area_per_person -- managed_area_per_person = total_area / staff_count."""
    stats = _sample_stats(total_area=10000.0, staff_count=20)
    metrics = await engine.calculate_daily_metrics("b001", "2026-03-15", stats)

    assert metrics.managed_area_per_person == 500.0  # 10000 / 20


async def test_calculate_completion_rate(engine):
    """test_calculate_completion_rate -- task_completion_rate = completed / total."""
    stats = _sample_stats(tasks_completed=75, tasks_total=100)
    metrics = await engine.calculate_daily_metrics("b001", "2026-03-15", stats)

    assert metrics.task_completion_rate == 0.75


async def test_calculate_savings(engine):
    """test_calculate_savings -- cost_savings_monthly = (baseline - current) * 30."""
    stats = _sample_stats(baseline_cost=5000.0, current_cost=3500.0)
    metrics = await engine.calculate_daily_metrics("b001", "2026-03-15", stats)

    # Daily savings = 1500, monthly = 1500 * 30 = 45000
    assert metrics.cost_savings_monthly == 45000.0
    # Efficiency = (5000-3500)/5000 * 100 = 30%
    assert metrics.efficiency_vs_baseline == 30.0


async def test_calculate_zero_staff(engine):
    """test_calculate_zero_staff -- zero staff yields 0 area per person (no crash)."""
    stats = _sample_stats(staff_count=0)
    metrics = await engine.calculate_daily_metrics("b001", "2026-03-15", stats)

    assert metrics.managed_area_per_person == 0.0


# ===================================================================
# 2. queries (5 tests)
# ===================================================================

async def test_get_metrics(engine):
    """test_get_metrics -- retrieves metrics for a specific building and date."""
    await engine.calculate_daily_metrics("b001", "2026-03-15", _sample_stats())

    result = await engine.get_metrics("b001", "2026-03-15")
    assert result is not None
    assert result.building_id == "b001"
    assert result.date == "2026-03-15"


async def test_get_trend(engine):
    """test_get_trend -- returns metrics over a date range."""
    for day in range(1, 6):
        date_str = f"2026-03-{day:02d}"
        await engine.calculate_daily_metrics("b001", date_str, _sample_stats())

    trend = await engine.get_trend("b001", days=90)
    assert len(trend) == 5
    # Should be sorted by date ascending
    dates = [m.date for m in trend]
    assert dates == sorted(dates)


async def test_get_comparison(engine):
    """test_get_comparison -- returns latest metrics for multiple buildings."""
    await engine.calculate_daily_metrics("b001", "2026-03-14", _sample_stats(shi_score=80.0))
    await engine.calculate_daily_metrics("b001", "2026-03-15", _sample_stats(shi_score=85.0))
    await engine.calculate_daily_metrics("b002", "2026-03-15", _sample_stats(shi_score=90.0))

    comparison = await engine.get_comparison(["b001", "b002"])
    assert "b001" in comparison
    assert "b002" in comparison
    # b001 latest should be 2026-03-15 (shi_score=85)
    assert comparison["b001"].date == "2026-03-15"
    assert comparison["b001"].service_health_index == 85.0
    assert comparison["b002"].service_health_index == 90.0


async def test_get_trend_empty(engine):
    """test_get_trend_empty -- empty building returns empty list."""
    trend = await engine.get_trend("nonexistent", days=90)
    assert trend == []


async def test_get_comparison_empty(engine):
    """test_get_comparison_empty -- buildings with no data are omitted."""
    comparison = await engine.get_comparison(["nonexistent_1", "nonexistent_2"])
    assert comparison == {}


# ===================================================================
# 3. edge_cases (5 tests)
# ===================================================================

async def test_zero_robots(engine):
    """test_zero_robots -- zero robots yields 0 human_robot_ratio (no crash)."""
    stats = _sample_stats(robot_count=0)
    metrics = await engine.calculate_daily_metrics("b001", "2026-03-15", stats)

    assert metrics.human_robot_ratio == 0.0


async def test_high_efficiency(engine):
    """test_high_efficiency -- very low current cost yields high efficiency."""
    stats = _sample_stats(baseline_cost=10000.0, current_cost=1000.0)
    metrics = await engine.calculate_daily_metrics("b001", "2026-03-15", stats)

    # (10000 - 1000) / 10000 * 100 = 90%
    assert metrics.efficiency_vs_baseline == 90.0
    # Monthly savings = (10000 - 1000) * 30 = 270000
    assert metrics.cost_savings_monthly == 270000.0


async def test_date_isolation(engine):
    """test_date_isolation -- same building different dates stored separately."""
    await engine.calculate_daily_metrics(
        "b001", "2026-03-14", _sample_stats(shi_score=80.0)
    )
    await engine.calculate_daily_metrics(
        "b001", "2026-03-15", _sample_stats(shi_score=90.0)
    )

    m14 = await engine.get_metrics("b001", "2026-03-14")
    m15 = await engine.get_metrics("b001", "2026-03-15")

    assert m14 is not None
    assert m15 is not None
    assert m14.service_health_index == 80.0
    assert m15.service_health_index == 90.0


async def test_multiple_buildings(engine):
    """test_multiple_buildings -- different buildings stored separately."""
    await engine.calculate_daily_metrics(
        "b001", "2026-03-15", _sample_stats(total_area=10000.0, staff_count=20)
    )
    await engine.calculate_daily_metrics(
        "b002", "2026-03-15", _sample_stats(total_area=5000.0, staff_count=10)
    )

    m1 = await engine.get_metrics("b001", "2026-03-15")
    m2 = await engine.get_metrics("b002", "2026-03-15")

    assert m1 is not None
    assert m2 is not None
    assert m1.managed_area_per_person == 500.0
    assert m2.managed_area_per_person == 500.0


async def test_overwrite_same_date(engine):
    """test_overwrite_same_date -- recalculating same date overwrites previous."""
    await engine.calculate_daily_metrics(
        "b001", "2026-03-15", _sample_stats(shi_score=70.0)
    )
    await engine.calculate_daily_metrics(
        "b001", "2026-03-15", _sample_stats(shi_score=95.0)
    )

    result = await engine.get_metrics("b001", "2026-03-15")
    assert result is not None
    assert result.service_health_index == 95.0

    # Should only have one entry for this building+date
    trend = await engine.get_trend("b001", days=90)
    dates_for_0315 = [m for m in trend if m.date == "2026-03-15"]
    assert len(dates_for_0315) == 1
