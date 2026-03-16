"""
Tests for H3 ExceptionDispatcher module.

Covers dispatch logic, lifecycle transitions, queries, and edge cases.
All tests use MemoryBackend and are fully self-contained.

Run:  PYTHONPATH=src pytest tests/test_exception_dispatcher.py -v
"""

from __future__ import annotations

import pytest
import pytest_asyncio

from human_ops.models import (
    DispatchRecord,
    DispatchResult,
    DispatchStats,
    ExceptionEvent,
    StaffProfile,
)
from human_ops.storage import MemoryBackend
from human_ops.staff_manager import StaffManager
from human_ops.exception_dispatcher import ExceptionDispatcher

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def backend():
    return MemoryBackend()


@pytest_asyncio.fixture
async def staff_manager(backend):
    return StaffManager(backend)


@pytest_asyncio.fixture
async def dispatcher(staff_manager, backend):
    return ExceptionDispatcher(staff_manager, backend)


@pytest_asyncio.fixture
async def sample_staff():
    return [
        StaffProfile(
            staff_id="s001", name="Li Jie", role="cleaner",
            building_id="b001", phone="13800001",
            skills=["floor_cleaning", "elevator_rescue"], status="active",
        ),
        StaffProfile(
            staff_id="s002", name="Wang Shi", role="cleaner",
            building_id="b001", phone="13800002",
            skills=["floor_cleaning", "vip_service"], status="active",
        ),
        StaffProfile(
            staff_id="s003", name="Zhang Wei", role="security",
            building_id="b001", phone="13800003",
            skills=["security", "robot_rescue"], status="active",
        ),
        StaffProfile(
            staff_id="s004", name="Chen Mei", role="supervisor",
            building_id="b001", phone="13800004",
            skills=["management", "vip_service"], status="active",
        ),
        StaffProfile(
            staff_id="s005", name="Liu Fang", role="cleaner",
            building_id="b002", phone="13800005",
            skills=["floor_cleaning"], status="active",
        ),
    ]


# ---------------------------------------------------------------------------
# Helper: bulk-add all sample staff into the manager
# ---------------------------------------------------------------------------

async def _seed(manager: StaffManager, staff_list: list[StaffProfile]) -> None:
    """Add every profile in *staff_list* to the manager."""
    for s in staff_list:
        await manager.add_staff(s)


def _make_event(
    event_type: str = "robot_error",
    priority: str = "normal",
    building_id: str = "b001",
    zone_id: str = "zone-1f",
) -> ExceptionEvent:
    """Create a test exception event with sensible defaults."""
    return ExceptionEvent(
        event_type=event_type,
        source="test",
        building_id=building_id,
        zone_id=zone_id,
        priority=priority,
        description=f"Test {event_type} event",
    )


# ===================================================================
# 1. Dispatch Logic (8 tests)
# ===================================================================

async def test_dispatch_critical(dispatcher, staff_manager, sample_staff):
    """test_dispatch_critical -- auto-dispatch, status=dispatched, autonomy=L3."""
    await _seed(staff_manager, sample_staff)

    event = _make_event(priority="critical")
    result = await dispatcher.dispatch(event)

    assert isinstance(result, DispatchResult)
    assert result.status == "dispatched"
    assert result.autonomy_level == 3.0  # L3
    assert result.assigned_to is not None


async def test_dispatch_high(dispatcher, staff_manager, sample_staff):
    """test_dispatch_high -- dispatch + notify, status=dispatched, autonomy=L2."""
    await _seed(staff_manager, sample_staff)

    event = _make_event(priority="high")
    result = await dispatcher.dispatch(event)

    assert result.status == "dispatched"
    assert result.autonomy_level == 2.0  # L2
    assert result.assigned_to is not None


async def test_dispatch_normal(dispatcher, staff_manager, sample_staff):
    """test_dispatch_normal -- pending approval, autonomy=L1."""
    await _seed(staff_manager, sample_staff)

    event = _make_event(priority="normal")
    result = await dispatcher.dispatch(event)

    assert result.status == "pending_approval"
    assert result.autonomy_level == 1.0  # L1


async def test_dispatch_low(dispatcher, staff_manager, sample_staff):
    """test_dispatch_low -- pending approval, autonomy=L0."""
    await _seed(staff_manager, sample_staff)

    event = _make_event(priority="low")
    result = await dispatcher.dispatch(event)

    assert result.status == "pending_approval"
    assert result.autonomy_level == 0.0  # L0


async def test_dispatch_skill_match(dispatcher, staff_manager, sample_staff):
    """test_dispatch_skill_match -- robot_error matches robot_rescue skill (s003)."""
    await _seed(staff_manager, sample_staff)

    event = _make_event(event_type="robot_error", priority="critical")
    result = await dispatcher.dispatch(event)

    # s003 (Zhang Wei) has robot_rescue and should be selected.
    assert result.assigned_to == "s003"
    assert result.assigned_name == "Zhang Wei"


async def test_dispatch_no_staff(dispatcher, staff_manager, sample_staff):
    """test_dispatch_no_staff -- no_available_staff status when building is empty."""
    await _seed(staff_manager, sample_staff)

    # Building b999 has no staff.
    event = _make_event(building_id="b999")
    result = await dispatcher.dispatch(event)

    assert result.status == "no_available_staff"
    assert result.assigned_to is None


async def test_dispatch_creates_record(dispatcher, staff_manager, sample_staff, backend):
    """test_dispatch_creates_record -- record saved to storage."""
    await _seed(staff_manager, sample_staff)

    event = _make_event(priority="high")
    result = await dispatcher.dispatch(event)

    # Verify persistence.
    data = await backend.get("dispatch_records", result.dispatch_id)
    assert data is not None
    assert data["dispatch_id"] == result.dispatch_id
    assert data["result"]["status"] == "dispatched"


async def test_dispatch_generates_id(dispatcher, staff_manager, sample_staff):
    """test_dispatch_generates_id -- dispatch_id is a uuid string."""
    await _seed(staff_manager, sample_staff)

    event = _make_event()
    result = await dispatcher.dispatch(event)

    assert result.dispatch_id is not None
    assert len(result.dispatch_id) == 36  # UUID4 format: 8-4-4-4-12
    assert result.dispatch_id.count("-") == 4


# ===================================================================
# 2. Lifecycle (7 tests)
# ===================================================================

async def test_accept_dispatch(dispatcher, staff_manager, sample_staff):
    """test_accept_dispatch -- status changes to accepted."""
    await _seed(staff_manager, sample_staff)

    event = _make_event(priority="critical")
    result = await dispatcher.dispatch(event)

    ok = await dispatcher.accept_dispatch(result.dispatch_id, result.assigned_to)
    assert ok is True

    # Verify the record is updated.
    record_data = await dispatcher._load_record(result.dispatch_id)
    assert record_data.result.status == "accepted"
    assert record_data.accepted_at is not None


async def test_accept_nonexistent(dispatcher):
    """test_accept_nonexistent -- returns False for nonexistent dispatch."""
    ok = await dispatcher.accept_dispatch("nonexistent-id", "s001")
    assert ok is False


async def test_resolve_dispatch(dispatcher, staff_manager, sample_staff):
    """test_resolve_dispatch -- status changes to resolved."""
    await _seed(staff_manager, sample_staff)

    event = _make_event(priority="critical")
    result = await dispatcher.dispatch(event)
    await dispatcher.accept_dispatch(result.dispatch_id, result.assigned_to)

    ok = await dispatcher.resolve_dispatch(result.dispatch_id)
    assert ok is True

    record = await dispatcher._load_record(result.dispatch_id)
    assert record.result.status == "resolved"
    assert record.resolved_at is not None


async def test_resolve_with_notes(dispatcher, staff_manager, sample_staff):
    """test_resolve_with_notes -- resolution_notes saved."""
    await _seed(staff_manager, sample_staff)

    event = _make_event(priority="high")
    result = await dispatcher.dispatch(event)

    ok = await dispatcher.resolve_dispatch(
        result.dispatch_id, notes="Robot rebooted and operational."
    )
    assert ok is True

    record = await dispatcher._load_record(result.dispatch_id)
    assert record.resolution_notes == "Robot rebooted and operational."


async def test_escalate(dispatcher, staff_manager, sample_staff):
    """test_escalate -- finds replacement staff after escalation."""
    await _seed(staff_manager, sample_staff)

    event = _make_event(event_type="robot_error", priority="critical")
    result = await dispatcher.dispatch(event)
    original_staff = result.assigned_to

    new_result = await dispatcher.escalate(result.dispatch_id, reason="too busy")
    assert new_result is not None
    assert isinstance(new_result, DispatchResult)
    assert new_result.assigned_to != original_staff
    assert new_result.status == "dispatched"
    assert new_result.dispatch_id != result.dispatch_id

    # The original record should be marked as escalated.
    original_record = await dispatcher._load_record(result.dispatch_id)
    assert original_record.result.status == "escalated"


async def test_escalate_no_replacement(dispatcher, staff_manager, backend):
    """test_escalate_no_replacement -- returns None when no replacement is available."""
    # Only one staff member in the building.
    solo = StaffProfile(
        staff_id="s100", name="Solo Worker", role="cleaner",
        building_id="b100", phone="13800100",
        skills=["floor_cleaning"], status="active",
    )
    await staff_manager.add_staff(solo)

    event = _make_event(
        event_type="urgent_clean", priority="critical", building_id="b100",
    )
    result = await dispatcher.dispatch(event)
    assert result.assigned_to == "s100"

    # Escalate — no other staff in b100.
    new_result = await dispatcher.escalate(result.dispatch_id, reason="busy")
    assert new_result is None

    # Original record should still be marked escalated.
    original = await dispatcher._load_record(result.dispatch_id)
    assert original.result.status == "escalated"


async def test_escalate_nonexistent(dispatcher):
    """test_escalate_nonexistent -- returns None for nonexistent dispatch."""
    new_result = await dispatcher.escalate("nonexistent-id", reason="test")
    assert new_result is None


# ===================================================================
# 3. Queries (5 tests)
# ===================================================================

async def test_get_pending_dispatches(dispatcher, staff_manager, sample_staff):
    """test_get_pending_dispatches -- returns dispatched/pending records."""
    await _seed(staff_manager, sample_staff)

    # Create one dispatched (critical) and one pending (normal).
    r1 = await dispatcher.dispatch(_make_event(priority="critical"))
    r2 = await dispatcher.dispatch(_make_event(priority="normal"))

    pending = await dispatcher.get_pending_dispatches()
    ids = {r.dispatch_id for r in pending}
    assert r1.dispatch_id in ids
    assert r2.dispatch_id in ids
    assert len(pending) >= 2


async def test_get_pending_by_building(dispatcher, staff_manager, sample_staff):
    """test_get_pending_by_building -- filters by building."""
    await _seed(staff_manager, sample_staff)

    await dispatcher.dispatch(_make_event(priority="critical", building_id="b001"))
    await dispatcher.dispatch(_make_event(priority="critical", building_id="b002"))

    b001_pending = await dispatcher.get_pending_dispatches(building_id="b001")
    assert all(r.event.building_id == "b001" for r in b001_pending)
    assert len(b001_pending) >= 1

    b002_pending = await dispatcher.get_pending_dispatches(building_id="b002")
    assert all(r.event.building_id == "b002" for r in b002_pending)
    assert len(b002_pending) >= 1


async def test_get_pending_excludes_resolved(dispatcher, staff_manager, sample_staff):
    """test_get_pending_excludes_resolved -- resolved not included."""
    await _seed(staff_manager, sample_staff)

    result = await dispatcher.dispatch(_make_event(priority="critical"))
    await dispatcher.accept_dispatch(result.dispatch_id, result.assigned_to)
    await dispatcher.resolve_dispatch(result.dispatch_id)

    pending = await dispatcher.get_pending_dispatches()
    ids = {r.dispatch_id for r in pending}
    assert result.dispatch_id not in ids


async def test_dispatch_stats_basic(dispatcher, staff_manager, sample_staff):
    """test_dispatch_stats_basic -- correct totals and rates."""
    await _seed(staff_manager, sample_staff)

    # Create three dispatches.
    r1 = await dispatcher.dispatch(_make_event(priority="critical"))
    r2 = await dispatcher.dispatch(_make_event(priority="high"))
    r3 = await dispatcher.dispatch(_make_event(priority="normal"))

    # Resolve one, escalate one.
    await dispatcher.resolve_dispatch(r1.dispatch_id)
    await dispatcher.escalate(r2.dispatch_id, reason="test")

    stats = await dispatcher.get_dispatch_stats("b001", days=7)
    assert isinstance(stats, DispatchStats)
    assert stats.total_dispatches >= 3
    assert stats.by_priority.get("critical", 0) >= 1
    assert stats.by_priority.get("high", 0) >= 1
    assert stats.by_priority.get("normal", 0) >= 1
    # One resolved out of at least 3 => resolution_rate > 0
    assert stats.resolution_rate > 0


async def test_dispatch_stats_empty(dispatcher):
    """test_dispatch_stats_empty -- zero stats when no records."""
    stats = await dispatcher.get_dispatch_stats("b001", days=7)

    assert isinstance(stats, DispatchStats)
    assert stats.total_dispatches == 0
    assert stats.avg_response_minutes == 0.0
    assert stats.resolution_rate == 0.0
    assert stats.escalation_rate == 0.0
    assert stats.by_priority == {}


# ===================================================================
# 4. Edge Cases (5 tests)
# ===================================================================

async def test_dispatch_complaint_skill(dispatcher, staff_manager, sample_staff):
    """test_dispatch_complaint_skill -- complaint matches vip_service skill."""
    await _seed(staff_manager, sample_staff)

    event = _make_event(event_type="complaint", priority="critical")
    result = await dispatcher.dispatch(event)

    # s002 (Wang Shi) or s004 (Chen Mei) has vip_service.
    assert result.assigned_to in ("s002", "s004")


async def test_dispatch_equipment_fault(dispatcher, staff_manager, sample_staff):
    """test_dispatch_equipment_fault -- equipment_fault matches elevator_rescue skill."""
    await _seed(staff_manager, sample_staff)

    event = _make_event(event_type="equipment_fault", priority="high")
    result = await dispatcher.dispatch(event)

    # s001 (Li Jie) has elevator_rescue.
    assert result.assigned_to == "s001"
    assert result.assigned_name == "Li Jie"


async def test_multiple_dispatches(dispatcher, staff_manager, sample_staff):
    """test_multiple_dispatches -- several events dispatched independently."""
    await _seed(staff_manager, sample_staff)

    results = []
    for priority in ("critical", "high", "normal", "low"):
        r = await dispatcher.dispatch(_make_event(priority=priority))
        results.append(r)

    # All should have unique dispatch_ids.
    ids = {r.dispatch_id for r in results}
    assert len(ids) == 4

    # Check statuses align with autonomy.
    assert results[0].status == "dispatched"       # critical
    assert results[1].status == "dispatched"       # high
    assert results[2].status == "pending_approval"  # normal
    assert results[3].status == "pending_approval"  # low


async def test_dispatch_then_escalate_then_resolve(
    dispatcher, staff_manager, sample_staff,
):
    """test_dispatch_then_escalate_then_resolve -- full lifecycle chain."""
    await _seed(staff_manager, sample_staff)

    # Step 1: Dispatch.
    event = _make_event(event_type="robot_error", priority="critical")
    r1 = await dispatcher.dispatch(event)
    assert r1.status == "dispatched"
    first_staff = r1.assigned_to

    # Step 2: Escalate.
    r2 = await dispatcher.escalate(r1.dispatch_id, reason="too busy")
    assert r2 is not None
    assert r2.assigned_to != first_staff

    # Step 3: Accept the new dispatch.
    ok = await dispatcher.accept_dispatch(r2.dispatch_id, r2.assigned_to)
    assert ok is True

    # Step 4: Resolve.
    ok = await dispatcher.resolve_dispatch(r2.dispatch_id, notes="Robot restarted.")
    assert ok is True

    # Verify final states.
    original = await dispatcher._load_record(r1.dispatch_id)
    assert original.result.status == "escalated"

    resolved = await dispatcher._load_record(r2.dispatch_id)
    assert resolved.result.status == "resolved"
    assert resolved.resolution_notes == "Robot restarted."


async def test_dispatch_fallback_no_skill(dispatcher, staff_manager, backend):
    """test_dispatch_fallback_no_skill -- assigns any available staff when no skill match."""
    # Create staff with no relevant skills.
    staff = StaffProfile(
        staff_id="s200", name="Generic Worker", role="cleaner",
        building_id="b200", phone="13800200",
        skills=["generic_duty"], status="active",
    )
    await staff_manager.add_staff(staff)

    # robot_error requires robot_rescue skill, which s200 does not have.
    event = _make_event(
        event_type="robot_error", priority="critical", building_id="b200",
    )
    result = await dispatcher.dispatch(event)

    # Should still assign the only available staff member.
    assert result.status == "dispatched"
    assert result.assigned_to == "s200"
    assert result.assigned_name == "Generic Worker"
