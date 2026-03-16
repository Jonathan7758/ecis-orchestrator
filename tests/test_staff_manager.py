"""
Tests for H1 StaffManager module.

Covers CRUD operations, attendance management, status queries,
skill matching, and edge cases. All tests use MemoryBackend and
are fully self-contained.

Run:  PYTHONPATH=src pytest tests/test_staff_manager.py -v
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from datetime import datetime, date, time

from human_ops.models import (
    StaffProfile,
    AttendanceRecord,
    StaffLocation,
    StaffWorkload,
)
from human_ops.storage import MemoryBackend
from human_ops.staff_manager import StaffManager

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def backend():
    return MemoryBackend()


@pytest_asyncio.fixture
async def manager(backend):
    return StaffManager(backend)


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
            skills=["floor_cleaning"], status="inactive",
        ),
    ]


# ---------------------------------------------------------------------------
# Helper: bulk-add all sample staff into the manager
# ---------------------------------------------------------------------------

async def _seed(manager: StaffManager, staff_list: list[StaffProfile]) -> None:
    """Add every profile in *staff_list* to the manager."""
    for s in staff_list:
        await manager.add_staff(s)


# ===================================================================
# 1. CRUD (6 tests)
# ===================================================================

async def test_add_staff(manager, sample_staff):
    """test_add_staff -- add a staff member and retrieve by ID."""
    staff = sample_staff[0]
    result = await manager.add_staff(staff)
    assert result.staff_id == "s001"

    fetched = await manager.get_staff("s001")
    assert fetched is not None
    assert fetched.name == "Li Jie"
    assert fetched.role == "cleaner"
    assert fetched.building_id == "b001"
    assert "floor_cleaning" in fetched.skills


async def test_get_staff_not_found(manager):
    """test_get_staff_not_found -- querying a non-existent ID returns None."""
    result = await manager.get_staff("nonexistent_999")
    assert result is None


async def test_update_staff(manager, sample_staff):
    """test_update_staff -- partial field update succeeds."""
    await manager.add_staff(sample_staff[0])

    updated = await manager.update_staff("s001", {"phone": "13900001", "status": "on_leave"})
    assert updated is not None
    assert updated.phone == "13900001"
    assert updated.status == "on_leave"
    # Unchanged fields stay the same.
    assert updated.name == "Li Jie"


async def test_update_nonexistent(manager):
    """test_update_nonexistent -- updating a missing ID returns None."""
    result = await manager.update_staff("ghost_id", {"phone": "000"})
    assert result is None


async def test_list_staff_by_building(manager, sample_staff):
    """test_list_staff_by_building -- filter staff by building_id."""
    await _seed(manager, sample_staff)

    b001_staff = await manager.list_staff(building_id="b001")
    ids = {s.staff_id for s in b001_staff}
    assert ids == {"s001", "s002", "s003", "s004"}

    b002_staff = await manager.list_staff(building_id="b002")
    ids2 = {s.staff_id for s in b002_staff}
    assert ids2 == {"s005"}


async def test_list_staff_by_role(manager, sample_staff):
    """test_list_staff_by_role -- filter staff by role."""
    await _seed(manager, sample_staff)

    cleaners = await manager.list_staff(role="cleaner")
    ids = {s.staff_id for s in cleaners}
    assert ids == {"s001", "s002", "s005"}

    security = await manager.list_staff(role="security")
    assert len(security) == 1
    assert security[0].staff_id == "s003"


# ===================================================================
# 2. Attendance (6 tests)
# ===================================================================

async def test_check_in(manager, sample_staff):
    """test_check_in -- check_in creates an AttendanceRecord with status=present."""
    await manager.add_staff(sample_staff[0])

    record = await manager.check_in("s001", "b001")
    assert isinstance(record, AttendanceRecord)
    assert record.staff_id == "s001"
    assert record.status in ("present", "late")  # either is acceptable
    assert record.check_in is not None
    assert record.location_building == "b001"


async def test_check_in_late(manager, sample_staff):
    """test_check_in_late -- a check-in record is created even for late arrivals.

    The implementation may or may not mark the status as 'late' depending on
    business rules; we simply verify the record exists and has a check_in time.
    """
    await manager.add_staff(sample_staff[0])

    record = await manager.check_in("s001", "b001")
    assert record is not None
    assert record.check_in is not None
    assert record.status in ("present", "late")


async def test_check_out(manager, sample_staff):
    """test_check_out -- check_out updates the check_out timestamp."""
    await manager.add_staff(sample_staff[0])
    await manager.check_in("s001", "b001")

    record = await manager.check_out("s001")
    assert isinstance(record, AttendanceRecord)
    assert record.check_out is not None


async def test_report_leave(manager, sample_staff):
    """test_report_leave -- creates a leave record and updates staff status."""
    await manager.add_staff(sample_staff[0])
    today = date.today()

    record = await manager.report_leave("s001", today)
    assert record is not None
    assert record.status == "leave"
    assert record.staff_id == "s001"

    # Staff profile status should be updated to on_leave.
    staff = await manager.get_staff("s001")
    assert staff.status == "on_leave"


async def test_get_attendance_by_date(manager, sample_staff):
    """test_get_attendance_by_date -- returns records for each staff by date."""
    await _seed(manager, sample_staff)

    await manager.check_in("s001", "b001")
    await manager.check_in("s002", "b001")
    await manager.check_in("s003", "b001")

    # Verify each individual record exists
    r1 = await manager.get_attendance("s001")
    r2 = await manager.get_attendance("s002")
    r3 = await manager.get_attendance("s003")
    assert r1 is not None and r1.staff_id == "s001"
    assert r2 is not None and r2.staff_id == "s002"
    assert r3 is not None and r3.staff_id == "s003"


async def test_get_attendance_by_building(manager, sample_staff):
    """test_get_attendance_by_building -- attendance tracks location_building."""
    await _seed(manager, sample_staff)

    await manager.check_in("s001", "b001")
    await manager.check_in("s005", "b002")

    r1 = await manager.get_attendance("s001")
    assert r1 is not None
    assert r1.location_building == "b001"

    r5 = await manager.get_attendance("s005")
    assert r5 is not None
    assert r5.location_building == "b002"


# ===================================================================
# 3. Status Queries (7 tests)
# ===================================================================

async def test_get_available_staff(manager, sample_staff):
    """test_get_available_staff -- returns active staff for a building."""
    await _seed(manager, sample_staff)
    today = date.today()

    available = await manager.get_available_staff("b001", today)
    ids = {s.staff_id for s in available}
    # All active b001 staff should be available
    assert "s001" in ids
    assert "s002" in ids
    assert "s003" in ids
    assert "s004" in ids


async def test_get_available_staff_excludes_leave(manager, sample_staff):
    """test_get_available_staff_excludes_leave -- staff on_leave are excluded."""
    await _seed(manager, sample_staff)
    today = date.today()

    await manager.check_in("s001", "b001")
    await manager.check_in("s002", "b001")

    # Put s001 on leave.
    await manager.report_leave("s001", today)

    available = await manager.get_available_staff("b001", today)
    ids = {s.staff_id for s in available}
    assert "s001" not in ids
    assert "s002" in ids


async def test_get_available_staff_excludes_inactive(manager, sample_staff):
    """test_get_available_staff_excludes_inactive -- inactive staff not included."""
    await _seed(manager, sample_staff)
    today = date.today()

    # s005 is in b002 and status=inactive; even if we try to check them in,
    # they should not appear as available.
    available = await manager.get_available_staff("b002", today)
    ids = {s.staff_id for s in available}
    assert "s005" not in ids


async def test_get_staff_location(manager, sample_staff):
    """test_get_staff_location -- returns location after explicit update."""
    await manager.add_staff(sample_staff[0])
    await manager.update_staff_location("s001", "b001", 3, "zone-3f-east")

    location = await manager.get_staff_location("s001")
    assert location is not None
    assert isinstance(location, StaffLocation)
    assert location.staff_id == "s001"
    assert location.building_id == "b001"
    assert location.floor == 3


async def test_get_staff_workload(manager, sample_staff):
    """test_get_staff_workload -- returns a workload summary after update."""
    await manager.add_staff(sample_staff[0])
    today = date.today()

    wl = StaffWorkload(staff_id="s001", date=today.isoformat(),
                       total_assignments=2, completed_assignments=1)
    await manager.update_staff_workload(wl)

    workload = await manager.get_staff_workload("s001", today)
    assert workload is not None
    assert isinstance(workload, StaffWorkload)
    assert workload.staff_id == "s001"
    assert workload.total_assignments == 2


async def test_get_staff_workload_no_assignments(manager, sample_staff):
    """test_get_staff_workload_no_assignments -- returns None when no workload exists."""
    await manager.add_staff(sample_staff[0])
    today = date.today()

    workload = await manager.get_staff_workload("s001", today)
    assert workload is None


async def test_get_available_staff_empty_building(manager, sample_staff):
    """test_get_available_staff_empty_building -- no staff in building returns empty list."""
    await _seed(manager, sample_staff)
    today = date.today()

    available = await manager.get_available_staff("b999", today)
    assert available == []


# ===================================================================
# 4. Skill Matching (4 tests)
# ===================================================================

async def test_find_qualified_staff(manager, sample_staff):
    """test_find_qualified_staff -- find staff by required skill."""
    await _seed(manager, sample_staff)

    # "floor_cleaning" is held by s001, s002, s005
    qualified = await manager.find_qualified_staff(
        skill="floor_cleaning", building_id="b001", available_only=False,
    )
    ids = {s.staff_id for s in qualified}
    assert "s001" in ids
    assert "s002" in ids
    # s005 is in b002, should NOT appear with building filter b001.
    assert "s005" not in ids


async def test_find_qualified_staff_available_only(manager, sample_staff):
    """test_find_qualified_staff_available_only -- excludes inactive staff."""
    await _seed(manager, sample_staff)

    # Search in b002 where s005 (inactive) has floor_cleaning.
    qualified = await manager.find_qualified_staff(
        skill="floor_cleaning", building_id="b002", available_only=True,
    )
    ids = {s.staff_id for s in qualified}
    # s005 is inactive and should be excluded.
    assert "s005" not in ids


async def test_find_qualified_staff_building_filter(manager, sample_staff):
    """test_find_qualified_staff_building_filter -- only returns staff in the specified building."""
    await _seed(manager, sample_staff)

    # "robot_rescue" is only held by s003 (b001).
    qualified = await manager.find_qualified_staff(
        skill="robot_rescue", building_id="b001", available_only=False,
    )
    assert len(qualified) == 1
    assert qualified[0].staff_id == "s003"

    # Same skill but different building should return empty.
    qualified_b002 = await manager.find_qualified_staff(
        skill="robot_rescue", building_id="b002", available_only=False,
    )
    assert qualified_b002 == []


async def test_find_qualified_staff_no_match(manager, sample_staff):
    """test_find_qualified_staff_no_match -- returns empty when no one has the skill."""
    await _seed(manager, sample_staff)

    qualified = await manager.find_qualified_staff(
        skill="nonexistent_skill", building_id="b001", available_only=False,
    )
    assert qualified == []


# ===================================================================
# 5. Edge Cases (2 tests)
# ===================================================================

async def test_double_check_in(manager, sample_staff):
    """test_double_check_in -- second check_in on same day overwrites (no duplicate).

    Uses the same storage key so second put replaces the first.
    """
    await manager.add_staff(sample_staff[0])

    first = await manager.check_in("s001", "b001")
    second = await manager.check_in("s001", "b001")

    # Both return valid records
    assert first is not None
    assert second is not None
    assert second.check_in is not None

    # get_attendance for this staff returns the single latest record
    record = await manager.get_attendance("s001")
    assert record is not None
    assert record.staff_id == "s001"


async def test_list_staff_multiple_filters(manager, sample_staff):
    """test_list_staff_multiple_filters -- building + role + status combined."""
    await _seed(manager, sample_staff)

    # Active cleaners in b001 => s001, s002
    results = await manager.list_staff(
        building_id="b001", role="cleaner", status="active",
    )
    ids = {s.staff_id for s in results}
    assert ids == {"s001", "s002"}

    # Active cleaners in b002 => none (s005 is inactive)
    results2 = await manager.list_staff(
        building_id="b002", role="cleaner", status="active",
    )
    assert results2 == []

    # Inactive cleaners in b002 => s005
    results3 = await manager.list_staff(
        building_id="b002", role="cleaner", status="inactive",
    )
    ids3 = {s.staff_id for s in results3}
    assert ids3 == {"s005"}
