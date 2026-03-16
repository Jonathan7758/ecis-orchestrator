"""
Tests for H2 SmartScheduler module.

Covers schedule generation, absence adjustment, temporary tasks,
confirmation, queries, adherence, and integration-like workflows.
All tests use MemoryBackend and are fully self-contained.

Run:  PYTHONPATH=src pytest tests/test_smart_scheduler.py -v
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from datetime import date

from human_ops.models import (
    Assignment,
    RobotAssignment,
    SchedulePlan,
    StaffProfile,
    StaffWorkload,
)
from human_ops.storage import MemoryBackend
from human_ops.staff_manager import StaffManager
from human_ops.smart_scheduler import SmartScheduler

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
async def scheduler(staff_manager, backend):
    return SmartScheduler(staff_manager, backend)


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
            building_id="b001", phone="13800005",
            skills=["floor_cleaning", "window_cleaning"], status="active",
        ),
    ]


# ---------------------------------------------------------------------------
# Helper: bulk-add all sample staff
# ---------------------------------------------------------------------------

async def _seed(manager: StaffManager, staff_list: list[StaffProfile]) -> None:
    """Add every profile in *staff_list* to the manager."""
    for s in staff_list:
        await manager.add_staff(s)


# ---------------------------------------------------------------------------
# Shared zone_configs and helpers
# ---------------------------------------------------------------------------

def _single_zone():
    """Return a single-zone config requiring 1 cleaner."""
    return [
        {
            "zone_id": "z001",
            "zone_name": "Lobby",
            "shift": "morning",
            "task_type": "cleaning",
            "staff_required": 1,
            "skills_needed": ["floor_cleaning"],
        },
    ]


def _multi_zone():
    """Return 3 zone configs."""
    return [
        {
            "zone_id": "z001",
            "zone_name": "Lobby",
            "shift": "morning",
            "task_type": "cleaning",
            "staff_required": 1,
            "skills_needed": ["floor_cleaning"],
        },
        {
            "zone_id": "z002",
            "zone_name": "Parking",
            "shift": "morning",
            "task_type": "security_patrol",
            "staff_required": 1,
            "skills_needed": ["security"],
        },
        {
            "zone_id": "z003",
            "zone_name": "VIP Lounge",
            "shift": "morning",
            "task_type": "vip_cleaning",
            "staff_required": 1,
            "skills_needed": ["vip_service"],
        },
    ]


TARGET_DATE = "2026-03-16"


# ===================================================================
# 1. Schedule Generation (10 tests)
# ===================================================================

async def test_generate_basic_schedule(scheduler, staff_manager, sample_staff):
    """test_generate_basic_schedule -- single zone, enough staff."""
    await _seed(staff_manager, sample_staff)

    plan = await scheduler.generate_schedule("b001", TARGET_DATE, _single_zone())
    assert isinstance(plan, SchedulePlan)
    assert plan.building_id == "b001"
    assert plan.date == TARGET_DATE
    assert len(plan.assignments) == 1
    assert plan.assignments[0].zone_id == "z001"
    assert plan.confidence == 1.0


async def test_generate_multi_zone(scheduler, staff_manager, sample_staff):
    """test_generate_multi_zone -- 3 zones, correct assignments."""
    await _seed(staff_manager, sample_staff)

    plan = await scheduler.generate_schedule("b001", TARGET_DATE, _multi_zone())
    assert len(plan.assignments) == 3

    zone_ids = {a.zone_id for a in plan.assignments}
    assert zone_ids == {"z001", "z002", "z003"}


async def test_generate_with_skills(scheduler, staff_manager, sample_staff):
    """test_generate_with_skills -- zones requiring specific skills get matched staff."""
    await _seed(staff_manager, sample_staff)

    zones = [
        {
            "zone_id": "z_sec",
            "zone_name": "Security Post",
            "shift": "morning",
            "task_type": "patrol",
            "staff_required": 1,
            "skills_needed": ["security"],
        },
        {
            "zone_id": "z_vip",
            "zone_name": "VIP Room",
            "shift": "morning",
            "task_type": "vip_cleaning",
            "staff_required": 1,
            "skills_needed": ["vip_service"],
        },
    ]
    plan = await scheduler.generate_schedule("b001", TARGET_DATE, zones)

    # Security zone should be assigned to s003 (has "security" skill)
    sec_assignment = [a for a in plan.assignments if a.zone_id == "z_sec"][0]
    assert sec_assignment.staff_id == "s003"

    # VIP zone should be assigned to s002 or s004 (both have "vip_service")
    vip_assignment = [a for a in plan.assignments if a.zone_id == "z_vip"][0]
    assert vip_assignment.staff_id in ("s002", "s004")


async def test_generate_with_robots(scheduler, staff_manager, sample_staff):
    """test_generate_with_robots -- robot assignments included."""
    await _seed(staff_manager, sample_staff)

    robots = [
        {"robot_id": "r001", "zone_id": "z001", "battery_level": 85.0, "task_type": "floor_sweep"},
    ]
    plan = await scheduler.generate_schedule(
        "b001", TARGET_DATE, _single_zone(), robot_status=robots,
    )
    assert len(plan.robot_assignments) == 1
    assert plan.robot_assignments[0].robot_id == "r001"
    assert plan.robot_assignments[0].battery_level == 85.0


async def test_generate_insufficient_staff(scheduler, staff_manager, sample_staff):
    """test_generate_insufficient_staff -- confidence < 1.0 when not enough people."""
    await _seed(staff_manager, sample_staff)

    # Request 10 staff for one zone but only 5 are available
    zones = [
        {
            "zone_id": "z001",
            "zone_name": "Lobby",
            "shift": "morning",
            "task_type": "cleaning",
            "staff_required": 10,
            "skills_needed": [],
        },
    ]
    plan = await scheduler.generate_schedule("b001", TARGET_DATE, zones)
    assert plan.confidence < 1.0
    assert len(plan.assignments) == 5  # only 5 staff available


async def test_generate_empty_staff(scheduler, staff_manager):
    """test_generate_empty_staff -- no available staff, confidence near 0."""
    # No staff seeded at all
    zones = [
        {
            "zone_id": "z001",
            "zone_name": "Lobby",
            "shift": "morning",
            "task_type": "cleaning",
            "staff_required": 3,
            "skills_needed": [],
        },
    ]
    plan = await scheduler.generate_schedule("b001", TARGET_DATE, zones)
    assert len(plan.assignments) == 0
    assert plan.confidence < 1.0


async def test_generate_schedule_saved(scheduler, staff_manager, sample_staff, backend):
    """test_generate_schedule_saved -- schedule persisted in storage."""
    await _seed(staff_manager, sample_staff)

    plan = await scheduler.generate_schedule("b001", TARGET_DATE, _single_zone())

    # Directly query backend
    stored = await backend.get("schedules", plan.schedule_id)
    assert stored is not None
    assert stored["building_id"] == "b001"
    assert stored["date"] == TARGET_DATE


async def test_generate_schedule_has_id(scheduler, staff_manager, sample_staff):
    """test_generate_schedule_has_id -- schedule_id is generated."""
    await _seed(staff_manager, sample_staff)

    plan = await scheduler.generate_schedule("b001", TARGET_DATE, _single_zone())
    assert plan.schedule_id is not None
    assert len(plan.schedule_id) > 0


async def test_generate_no_double_assign(scheduler, staff_manager, sample_staff):
    """test_generate_no_double_assign -- same staff not assigned twice."""
    await _seed(staff_manager, sample_staff)

    # 5 zones each requiring 1 staff = exactly 5 staff needed = exactly 5 available
    zones = [
        {
            "zone_id": f"z{i:03d}",
            "zone_name": f"Zone {i}",
            "shift": "morning",
            "task_type": "cleaning",
            "staff_required": 1,
            "skills_needed": [],
        }
        for i in range(5)
    ]
    plan = await scheduler.generate_schedule("b001", TARGET_DATE, zones)

    staff_ids = [a.staff_id for a in plan.assignments]
    assert len(staff_ids) == len(set(staff_ids)), "Staff IDs must be unique"


async def test_generate_notes_for_gaps(scheduler, staff_manager, sample_staff):
    """test_generate_notes_for_gaps -- notes added for unfilled zones."""
    await _seed(staff_manager, sample_staff)

    # 2 zones each needing 4 staff = 8 needed, only 5 available
    zones = [
        {
            "zone_id": "z001",
            "zone_name": "Lobby",
            "shift": "morning",
            "task_type": "cleaning",
            "staff_required": 4,
            "skills_needed": [],
        },
        {
            "zone_id": "z002",
            "zone_name": "Garage",
            "shift": "morning",
            "task_type": "cleaning",
            "staff_required": 4,
            "skills_needed": [],
        },
    ]
    plan = await scheduler.generate_schedule("b001", TARGET_DATE, zones)

    # At least one zone should have unfilled notes
    assert any("unfilled" in n for n in plan.notes)


# ===================================================================
# 2. Schedule Adjustment (8 tests)
# ===================================================================

async def test_adjust_absence_replacement(scheduler, staff_manager, sample_staff):
    """test_adjust_absence_replacement -- absent staff replaced."""
    await _seed(staff_manager, sample_staff)

    # Generate schedule using only 1 zone (1 staff)
    plan = await scheduler.generate_schedule("b001", TARGET_DATE, _single_zone())
    original_staff_id = plan.assignments[0].staff_id

    adjusted = await scheduler.adjust_for_absence(plan.schedule_id, original_staff_id)
    assert adjusted is not None
    assert len(adjusted.assignments) == 1
    # The replacement should be a different staff member
    assert adjusted.assignments[0].staff_id != original_staff_id


async def test_adjust_absence_no_replacement(scheduler, staff_manager, sample_staff):
    """test_adjust_absence_no_replacement -- confidence drops, note added."""
    # Use only 1 staff member so there is no replacement
    single_staff = [sample_staff[0]]
    await _seed(staff_manager, single_staff)

    plan = await scheduler.generate_schedule("b001", TARGET_DATE, _single_zone())
    original_confidence = plan.confidence
    absent_id = plan.assignments[0].staff_id

    adjusted = await scheduler.adjust_for_absence(plan.schedule_id, absent_id)
    assert adjusted is not None
    assert len(adjusted.assignments) == 0
    assert adjusted.confidence < original_confidence
    assert any("No replacement" in n for n in adjusted.notes)


async def test_adjust_nonexistent_schedule(scheduler):
    """test_adjust_nonexistent_schedule -- returns None."""
    result = await scheduler.adjust_for_absence("nonexistent_id", "s001")
    assert result is None


async def test_adjust_staff_not_in_schedule(scheduler, staff_manager, sample_staff):
    """test_adjust_staff_not_in_schedule -- no change."""
    await _seed(staff_manager, sample_staff)

    plan = await scheduler.generate_schedule("b001", TARGET_DATE, _single_zone())
    original_count = len(plan.assignments)

    # Try to adjust for a staff member not in the schedule
    adjusted = await scheduler.adjust_for_absence(plan.schedule_id, "nonexistent_staff")
    assert adjusted is not None
    assert len(adjusted.assignments) == original_count


async def test_add_temp_task(scheduler, staff_manager, sample_staff):
    """test_add_temp_task -- new assignment added."""
    await _seed(staff_manager, sample_staff)

    plan = await scheduler.generate_schedule("b001", TARGET_DATE, _single_zone())
    original_count = len(plan.assignments)

    updated = await scheduler.add_temporary_task(
        plan.schedule_id, "z_temp", "Emergency Room", "urgent_clean", "high",
    )
    assert updated is not None
    assert len(updated.assignments) == original_count + 1

    temp = [a for a in updated.assignments if a.zone_id == "z_temp"]
    assert len(temp) == 1
    assert temp[0].task_type == "urgent_clean"


async def test_add_temp_task_no_staff(scheduler, staff_manager):
    """test_add_temp_task_no_staff -- note about understaffing."""
    # No staff seeded
    # First create a schedule (empty)
    plan = await scheduler.generate_schedule("b001", TARGET_DATE, [])

    updated = await scheduler.add_temporary_task(
        plan.schedule_id, "z_temp", "Emergency Room", "urgent_clean", "high",
    )
    assert updated is not None
    assert any("Understaffed" in n for n in updated.notes)


async def test_add_temp_least_loaded(scheduler, staff_manager, sample_staff):
    """test_add_temp_least_loaded -- picks staff with fewest assignments."""
    await _seed(staff_manager, sample_staff)

    # Create a schedule with multiple zones (each gets 1 staff)
    zones = [
        {
            "zone_id": f"z{i:03d}",
            "zone_name": f"Zone {i}",
            "shift": "morning",
            "task_type": "cleaning",
            "staff_required": 1,
            "skills_needed": [],
        }
        for i in range(3)
    ]
    plan = await scheduler.generate_schedule("b001", TARGET_DATE, zones)

    # Assigned staff each have 1 assignment. Unassigned staff have 0.
    assigned_ids = {a.staff_id for a in plan.assignments}
    unassigned = [s for s in sample_staff if s.staff_id not in assigned_ids]

    updated = await scheduler.add_temporary_task(
        plan.schedule_id, "z_temp", "Temp Zone", "urgent_clean", "normal",
    )
    assert updated is not None

    temp_assignment = [a for a in updated.assignments if a.zone_id == "z_temp"][0]
    # Should pick one of the unassigned (0 assignments) staff members
    assert temp_assignment.staff_id in {s.staff_id for s in unassigned}


async def test_add_temp_nonexistent_schedule(scheduler):
    """test_add_temp_nonexistent_schedule -- returns None."""
    result = await scheduler.add_temporary_task(
        "nonexistent_id", "z001", "Lobby", "cleaning", "normal",
    )
    assert result is None


# ===================================================================
# 3. Confirmation & Query (7 tests)
# ===================================================================

async def test_confirm_schedule(scheduler, staff_manager, sample_staff):
    """test_confirm_schedule -- status changes to confirmed."""
    await _seed(staff_manager, sample_staff)

    plan = await scheduler.generate_schedule("b001", TARGET_DATE, _single_zone())
    assert plan.status == "draft"

    success = await scheduler.confirm_schedule(plan.schedule_id, "manager_001")
    assert success is True

    # Re-fetch and verify
    fetched = await scheduler.get_schedule("b001", TARGET_DATE)
    assert fetched is not None
    assert fetched.status == "confirmed"
    assert fetched.confirmed_by == "manager_001"


async def test_confirm_nonexistent(scheduler):
    """test_confirm_nonexistent -- returns False."""
    result = await scheduler.confirm_schedule("nonexistent_id", "manager_001")
    assert result is False


async def test_get_schedule(scheduler, staff_manager, sample_staff):
    """test_get_schedule -- retrieve by building+date."""
    await _seed(staff_manager, sample_staff)

    plan = await scheduler.generate_schedule("b001", TARGET_DATE, _single_zone())

    fetched = await scheduler.get_schedule("b001", TARGET_DATE)
    assert fetched is not None
    assert fetched.schedule_id == plan.schedule_id
    assert fetched.building_id == "b001"
    assert fetched.date == TARGET_DATE


async def test_get_schedule_not_found(scheduler):
    """test_get_schedule_not_found -- returns None."""
    result = await scheduler.get_schedule("b999", "2099-01-01")
    assert result is None


async def test_get_staff_schedule(scheduler, staff_manager, sample_staff):
    """test_get_staff_schedule -- returns assignments for staff."""
    await _seed(staff_manager, sample_staff)

    plan = await scheduler.generate_schedule("b001", TARGET_DATE, _single_zone())
    assigned_staff_id = plan.assignments[0].staff_id

    assignments = await scheduler.get_staff_schedule(assigned_staff_id, TARGET_DATE)
    assert len(assignments) == 1
    assert assignments[0].staff_id == assigned_staff_id
    assert isinstance(assignments[0], Assignment)


async def test_get_staff_schedule_none(scheduler, staff_manager, sample_staff):
    """test_get_staff_schedule_none -- empty list when no assignments."""
    await _seed(staff_manager, sample_staff)

    assignments = await scheduler.get_staff_schedule("s999", TARGET_DATE)
    assert assignments == []


async def test_schedule_adherence(scheduler, staff_manager, sample_staff):
    """test_schedule_adherence -- correct ratio calculation."""
    await _seed(staff_manager, sample_staff)

    # Generate a schedule with 2 assignments
    zones = [
        {
            "zone_id": "z001",
            "zone_name": "Lobby",
            "shift": "morning",
            "task_type": "cleaning",
            "staff_required": 1,
            "skills_needed": [],
        },
        {
            "zone_id": "z002",
            "zone_name": "Garage",
            "shift": "morning",
            "task_type": "cleaning",
            "staff_required": 1,
            "skills_needed": [],
        },
    ]
    plan = await scheduler.generate_schedule("b001", TARGET_DATE, zones)
    assert len(plan.assignments) == 2

    # Mark one staff member as having completed their assignment
    first_staff = plan.assignments[0].staff_id
    parts = TARGET_DATE.split("-")
    dt = date(int(parts[0]), int(parts[1]), int(parts[2]))

    wl = StaffWorkload(
        staff_id=first_staff,
        date=TARGET_DATE,
        total_assignments=1,
        completed_assignments=1,
    )
    await staff_manager.update_staff_workload(wl)

    adherence = await scheduler.get_schedule_adherence("b001", TARGET_DATE)
    # 1 completed out of 2 total = 0.5
    assert adherence == 0.5


# ===================================================================
# 4. Integration-like (5 tests)
# ===================================================================

async def test_full_workflow(scheduler, staff_manager, sample_staff):
    """test_full_workflow -- generate -> adjust -> confirm."""
    await _seed(staff_manager, sample_staff)

    # 1. Generate
    plan = await scheduler.generate_schedule("b001", TARGET_DATE, _multi_zone())
    assert plan.status == "draft"
    assert len(plan.assignments) == 3

    # 2. Simulate absence
    absent_id = plan.assignments[0].staff_id
    adjusted = await scheduler.adjust_for_absence(plan.schedule_id, absent_id)
    assert adjusted is not None
    assert len(adjusted.assignments) == 3  # replacement found

    # 3. Confirm
    success = await scheduler.confirm_schedule(plan.schedule_id, "supervisor_01")
    assert success is True

    fetched = await scheduler.get_schedule("b001", TARGET_DATE)
    assert fetched.status == "confirmed"


async def test_multiple_shifts(scheduler, staff_manager, sample_staff):
    """test_multiple_shifts -- morning + afternoon different staff."""
    await _seed(staff_manager, sample_staff)

    zones = [
        {
            "zone_id": "z001",
            "zone_name": "Lobby",
            "shift": "morning",
            "task_type": "cleaning",
            "staff_required": 2,
            "skills_needed": [],
        },
        {
            "zone_id": "z001",
            "zone_name": "Lobby",
            "shift": "afternoon",
            "task_type": "cleaning",
            "staff_required": 2,
            "skills_needed": [],
        },
    ]
    plan = await scheduler.generate_schedule("b001", TARGET_DATE, zones)

    morning = [a for a in plan.assignments if a.shift == "morning"]
    afternoon = [a for a in plan.assignments if a.shift == "afternoon"]
    assert len(morning) == 2
    assert len(afternoon) == 2

    # All 4 assignments should be different staff (no double-assign)
    all_ids = [a.staff_id for a in plan.assignments]
    assert len(all_ids) == len(set(all_ids))


async def test_schedule_with_paired_robots(scheduler, staff_manager, sample_staff):
    """test_schedule_with_paired_robots -- staff paired with robots."""
    await _seed(staff_manager, sample_staff)

    robots = [
        {"robot_id": "r001", "zone_id": "z001", "battery_level": 90.0, "task_type": "floor_sweep"},
        {"robot_id": "r002", "zone_id": "z002", "battery_level": 75.0, "task_type": "patrol_scan"},
    ]
    zones = [
        {
            "zone_id": "z001",
            "zone_name": "Lobby",
            "shift": "morning",
            "task_type": "cleaning",
            "staff_required": 1,
            "skills_needed": [],
        },
        {
            "zone_id": "z002",
            "zone_name": "Parking",
            "shift": "morning",
            "task_type": "security_patrol",
            "staff_required": 1,
            "skills_needed": [],
        },
    ]
    plan = await scheduler.generate_schedule(
        "b001", TARGET_DATE, zones, robot_status=robots,
    )

    # Both zones should have staff paired with the co-located robot
    z1_assign = [a for a in plan.assignments if a.zone_id == "z001"][0]
    z2_assign = [a for a in plan.assignments if a.zone_id == "z002"][0]
    assert z1_assign.paired_robot_id == "r001"
    assert z2_assign.paired_robot_id == "r002"


async def test_absence_then_temp_task(scheduler, staff_manager, sample_staff):
    """test_absence_then_temp_task -- chain of adjustments."""
    await _seed(staff_manager, sample_staff)

    # Generate a 2-zone schedule
    zones = _multi_zone()[:2]  # Lobby + Parking
    plan = await scheduler.generate_schedule("b001", TARGET_DATE, zones)
    assert len(plan.assignments) == 2

    # Remove one staff member
    absent_id = plan.assignments[0].staff_id
    adjusted = await scheduler.adjust_for_absence(plan.schedule_id, absent_id)
    assert adjusted is not None

    # Now add a temp task on top of the adjustment
    updated = await scheduler.add_temporary_task(
        plan.schedule_id, "z_emergency", "Emergency Spill", "urgent_clean", "high",
    )
    assert updated is not None
    # Should have 2 original (1 replaced) + 1 temp = 3
    assert len(updated.assignments) == 3

    temp = [a for a in updated.assignments if a.zone_id == "z_emergency"]
    assert len(temp) == 1


async def test_schedule_date_isolation(scheduler, staff_manager, sample_staff):
    """test_schedule_date_isolation -- different dates independent."""
    await _seed(staff_manager, sample_staff)

    date1 = "2026-03-16"
    date2 = "2026-03-17"

    plan1 = await scheduler.generate_schedule("b001", date1, _single_zone())
    plan2 = await scheduler.generate_schedule("b001", date2, _single_zone())

    assert plan1.schedule_id != plan2.schedule_id

    fetched1 = await scheduler.get_schedule("b001", date1)
    fetched2 = await scheduler.get_schedule("b001", date2)

    assert fetched1 is not None
    assert fetched2 is not None
    assert fetched1.schedule_id == plan1.schedule_id
    assert fetched2.schedule_id == plan2.schedule_id
    assert fetched1.date == date1
    assert fetched2.date == date2
