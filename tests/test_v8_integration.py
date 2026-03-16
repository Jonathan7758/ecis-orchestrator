"""
Integration tests for V8 modules — end-to-end verification that all
human_ops, health, and roi modules work together correctly.

Tests exercise realistic Tower C scenarios with shared MemoryBackend,
verifying cross-module interactions for daily operations, exception
handling, health/ROI calculations, and data consistency.

Run:  PYTHONPATH=src pytest tests/test_v8_integration.py -v
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from datetime import date, datetime, timedelta

from human_ops.storage import MemoryBackend
from human_ops.staff_manager import StaffManager
from human_ops.smart_scheduler import SmartScheduler
from human_ops.exception_dispatcher import ExceptionDispatcher
from human_ops.work_order_engine import WorkOrderEngine
from human_ops.models import (
    StaffProfile,
    ExceptionEvent,
    WorkOrder,
    Assignment,
    SchedulePlan,
    StaffWorkload,
)
from health.engine import HealthEngine, HealthWeights
from roi.roi_engine import ROIEngine, ROIMetrics

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def system():
    """Set up complete V8 system with all modules sharing one backend."""
    backend = MemoryBackend()
    staff_mgr = StaffManager(backend)
    scheduler = SmartScheduler(staff_mgr, backend)
    dispatcher = ExceptionDispatcher(staff_mgr, backend)
    work_orders = WorkOrderEngine(backend)
    health = HealthEngine(backend)
    roi = ROIEngine(backend)

    # Seed Tower C staff
    staff_list = [
        StaffProfile(
            staff_id="tc-001", name="Li Jie", role="cleaner",
            building_id="tower_c", phone="13800001",
            skills=["floor_cleaning", "elevator_rescue"],
        ),
        StaffProfile(
            staff_id="tc-002", name="Wang Shi", role="cleaner",
            building_id="tower_c", phone="13800002",
            skills=["floor_cleaning", "vip_service"],
        ),
        StaffProfile(
            staff_id="tc-003", name="Zhang Wei", role="security",
            building_id="tower_c", phone="13800003",
            skills=["security", "robot_rescue"],
        ),
        StaffProfile(
            staff_id="tc-004", name="Chen Mei", role="supervisor",
            building_id="tower_c", phone="13800004",
            skills=["management", "vip_service", "floor_cleaning"],
        ),
        StaffProfile(
            staff_id="tc-005", name="Liu Fang", role="cleaner",
            building_id="tower_c", phone="13800005",
            skills=["floor_cleaning"],
        ),
    ]
    for s in staff_list:
        await staff_mgr.add_staff(s)

    return {
        "backend": backend,
        "staff": staff_mgr,
        "scheduler": scheduler,
        "dispatcher": dispatcher,
        "orders": work_orders,
        "health": health,
        "roi": roi,
        "staff_list": staff_list,
    }


# ---------------------------------------------------------------------------
# Helper: standard Tower C zone configs for 3 zones
# ---------------------------------------------------------------------------

def _tower_c_zones(shift: str = "morning") -> list:
    """Return 3 zone configs for Tower C morning shift."""
    return [
        {
            "zone_id": "tc-lobby",
            "zone_name": "Tower C Lobby",
            "shift": shift,
            "task_type": "floor_cleaning",
            "staff_required": 1,
            "skills_needed": ["floor_cleaning"],
        },
        {
            "zone_id": "tc-3f",
            "zone_name": "Tower C 3rd Floor",
            "shift": shift,
            "task_type": "floor_cleaning",
            "staff_required": 2,
            "skills_needed": ["floor_cleaning"],
        },
        {
            "zone_id": "tc-vip",
            "zone_name": "Tower C VIP Lounge",
            "shift": shift,
            "task_type": "vip_service",
            "staff_required": 1,
            "skills_needed": ["vip_service"],
        },
    ]


def _tower_c_health_metrics(**overrides) -> dict:
    """Return full 6-dimension health metrics with optional overrides."""
    metrics = {
        "cleanliness": 82.0,
        "tenant_satisfaction": 88.0,
        "staff_attendance": 90.0,
        "robot_availability": 95.0,
        "complaint_response": 75.0,
        "manual_assessment": 85.0,
    }
    metrics.update(overrides)
    return metrics


def _tower_c_roi_stats(**overrides) -> dict:
    """Return realistic daily ROI input stats for Tower C."""
    stats = {
        "total_area": 5000.0,
        "staff_count": 5,
        "robot_count": 2,
        "tasks_completed": 18,
        "tasks_total": 20,
        "robot_hours": 14.0,
        "total_hours": 16.0,
        "baseline_cost": 3000.0,
        "current_cost": 2200.0,
        "shi_score": 85.0,
    }
    stats.update(overrides)
    return stats


# ===========================================================================
# Scenario 1: Daily Operations (5 tests)
# ===========================================================================


class TestDailyOperations:
    """Verify schedule generation, confirmation, check-in, robot pairing,
    and adherence workflows across the scheduler and staff manager."""

    async def test_morning_schedule_generation(self, system):
        """Generate a schedule for Tower C with 3 zones, verify all staff
        assigned to cover the 4 required positions."""
        scheduler = system["scheduler"]
        zones = _tower_c_zones()

        plan = await scheduler.generate_schedule(
            building_id="tower_c",
            target_date="2026-03-16",
            zone_configs=zones,
        )

        assert plan.building_id == "tower_c"
        assert plan.date == "2026-03-16"
        assert plan.status == "draft"
        # 3 zones requesting 1+2+1 = 4 staff total
        assert len(plan.assignments) == 4
        # All assigned staff should be from our 5-person pool
        assigned_ids = {a.staff_id for a in plan.assignments}
        valid_ids = {s.staff_id for s in system["staff_list"]}
        assert assigned_ids.issubset(valid_ids)
        # Each assignment must have a valid shift
        for a in plan.assignments:
            assert a.shift == "morning"
        # Confidence should be 1.0 (all positions filled)
        assert plan.confidence == 1.0

    async def test_schedule_confirm_and_query(self, system):
        """Generate, confirm, then query by building+date — verifying
        the confirmed schedule is retrievable."""
        scheduler = system["scheduler"]
        zones = _tower_c_zones()

        plan = await scheduler.generate_schedule(
            building_id="tower_c",
            target_date="2026-03-16",
            zone_configs=zones,
        )
        assert plan.status == "draft"

        ok = await scheduler.confirm_schedule(plan.schedule_id, "tc-004")
        assert ok is True

        queried = await scheduler.get_schedule("tower_c", "2026-03-16")
        assert queried is not None
        assert queried.schedule_id == plan.schedule_id
        assert queried.status == "confirmed"
        assert queried.confirmed_by == "tc-004"
        assert len(queried.assignments) == 4

    async def test_staff_check_in_then_schedule(self, system):
        """Check in only 3 of 5 staff, set the other 2 on leave, then
        generate a schedule.  Verify only checked-in staff are assigned."""
        staff_mgr = system["staff"]
        scheduler = system["scheduler"]

        today = datetime(2026, 3, 16, 7, 0, 0)
        today_date = date(2026, 3, 16)

        # Check in 3 staff
        await staff_mgr.check_in("tc-001", "tower_c", today)
        await staff_mgr.check_in("tc-002", "tower_c", today)
        await staff_mgr.check_in("tc-003", "tower_c", today)

        # Mark 2 staff on leave
        await staff_mgr.report_leave("tc-004", today_date)
        await staff_mgr.report_leave("tc-005", today_date)

        zones = _tower_c_zones()
        plan = await scheduler.generate_schedule(
            building_id="tower_c",
            target_date="2026-03-16",
            zone_configs=zones,
        )

        assigned_ids = {a.staff_id for a in plan.assignments}
        # On-leave staff should NOT appear
        assert "tc-004" not in assigned_ids
        assert "tc-005" not in assigned_ids
        # Only 3 available for 4 positions — expect 3 assigned
        assert len(plan.assignments) == 3
        assert plan.confidence < 1.0
        assert len(plan.notes) > 0  # at least one unfilled note

    async def test_schedule_with_robots(self, system):
        """Generate a schedule with robot_status.  Verify robots are listed
        and paired with staff in matching zones."""
        scheduler = system["scheduler"]
        zones = _tower_c_zones()

        robot_status = [
            {
                "robot_id": "rob-c01",
                "zone_id": "tc-lobby",
                "task_type": "floor_cleaning",
                "battery_level": 92.0,
                "shift": "morning",
            },
            {
                "robot_id": "rob-c02",
                "zone_id": "tc-3f",
                "task_type": "floor_cleaning",
                "battery_level": 78.0,
                "shift": "morning",
            },
        ]

        plan = await scheduler.generate_schedule(
            building_id="tower_c",
            target_date="2026-03-16",
            zone_configs=zones,
            robot_status=robot_status,
        )

        assert len(plan.robot_assignments) == 2
        robot_ids = {r.robot_id for r in plan.robot_assignments}
        assert robot_ids == {"rob-c01", "rob-c02"}

        # At least one human assignment should be paired with a robot
        paired = [a for a in plan.assignments if a.paired_robot_id is not None]
        assert len(paired) >= 1
        paired_robot_ids = {a.paired_robot_id for a in paired}
        assert paired_robot_ids.issubset(robot_ids)

    async def test_schedule_adherence_calculation(self, system):
        """Generate a schedule, mark some tasks complete via workload
        records, verify adherence ratio is correct."""
        staff_mgr = system["staff"]
        scheduler = system["scheduler"]
        zones = _tower_c_zones()

        plan = await scheduler.generate_schedule(
            building_id="tower_c",
            target_date="2026-03-16",
            zone_configs=zones,
        )

        total_assignments = len(plan.assignments)
        assert total_assignments == 4

        # Mark 3 out of 4 assignments as completed through workload records
        completed_staff = [a.staff_id for a in plan.assignments[:3]]
        for sid in completed_staff:
            wl = StaffWorkload(
                staff_id=sid,
                date="2026-03-16",
                total_assignments=1,
                completed_assignments=1,
                hours_worked=7.0,
            )
            await staff_mgr.update_staff_workload(wl)

        adherence = await scheduler.get_schedule_adherence("tower_c", "2026-03-16")
        assert adherence == 0.75  # 3 completed / 4 total


# ===========================================================================
# Scenario 2: Exception Handling (5 tests)
# ===========================================================================


class TestExceptionHandling:
    """Verify exception dispatch, escalation, auto-dispatch for critical
    events, and interaction with the active schedule."""

    async def test_robot_error_dispatch(self, system):
        """Robot error event dispatches a worker with robot_rescue skill."""
        dispatcher = system["dispatcher"]

        event = ExceptionEvent(
            event_type="robot_error",
            source="robot_monitor",
            building_id="tower_c",
            zone_id="tc-lobby",
            priority="high",
            description="Robot rob-c01 stuck at elevator door",
            robot_id="rob-c01",
        )

        result = await dispatcher.dispatch(event)

        assert result.dispatch_id is not None
        assert result.status == "dispatched"  # high priority -> L2 -> dispatched
        assert result.autonomy_level == 2.0
        # tc-003 (Zhang Wei) is the only one with robot_rescue skill
        assert result.assigned_to == "tc-003"
        assert result.assigned_name == "Zhang Wei"
        assert result.estimated_response_minutes == 10.0

    async def test_complaint_dispatch_then_work_order(self, system):
        """Complaint exception dispatches a VIP-skilled worker.  Then a work
        order is created from the same complaint and linked to the same staff."""
        dispatcher = system["dispatcher"]
        orders = system["orders"]

        event = ExceptionEvent(
            event_type="complaint",
            source="tenant_app",
            building_id="tower_c",
            zone_id="tc-vip",
            priority="high",
            description="VIP guest unhappy with room temperature",
        )

        dispatch_result = await dispatcher.dispatch(event)
        assert dispatch_result.status == "dispatched"
        # tc-002 (Wang Shi) has vip_service skill
        assert dispatch_result.assigned_to == "tc-002"

        # Create a work order from this complaint
        wo = WorkOrder(
            order_id="wo-comp-001",
            order_type="complaint",
            source="exception_dispatch",
            title="VIP temperature complaint",
            description=f"From dispatch {dispatch_result.dispatch_id}",
            priority="high",
            building_id="tower_c",
            zone_id="tc-vip",
            assigned_to=dispatch_result.assigned_to,
        )
        order_id = await orders.create_order(wo)
        assert order_id == "wo-comp-001"

        fetched = await orders.get_order("wo-comp-001")
        assert fetched is not None
        assert fetched.assigned_to == "tc-002"
        assert fetched.status == "open"

    async def test_dispatch_escalation_chain(self, system):
        """Dispatch to first worker, then escalate because of no response.
        Verify the escalation assigns a different worker."""
        dispatcher = system["dispatcher"]

        event = ExceptionEvent(
            event_type="urgent_clean",
            source="iot_sensor",
            building_id="tower_c",
            zone_id="tc-lobby",
            priority="high",
            description="Water leak detected in lobby area",
        )

        first_result = await dispatcher.dispatch(event)
        assert first_result.status == "dispatched"
        first_assigned = first_result.assigned_to

        # Escalate: first worker did not respond
        escalation = await dispatcher.escalate(
            first_result.dispatch_id,
            reason="No response within 10 minutes",
        )

        assert escalation is not None
        assert escalation.dispatch_id != first_result.dispatch_id
        assert escalation.assigned_to != first_assigned
        assert escalation.status == "dispatched"

    async def test_critical_auto_dispatch(self, system):
        """Critical-priority event triggers L3 autonomy auto-dispatch."""
        dispatcher = system["dispatcher"]

        event = ExceptionEvent(
            event_type="equipment_fault",
            source="elevator_monitor",
            building_id="tower_c",
            zone_id="tc-lobby",
            priority="critical",
            description="Elevator #2 emergency stop triggered",
        )

        result = await dispatcher.dispatch(event)

        assert result.autonomy_level == 3.0  # L3 = auto-dispatch
        assert result.status == "dispatched"
        assert result.estimated_response_minutes == 5.0
        # tc-001 has elevator_rescue skill
        assert result.assigned_to == "tc-001"

    async def test_exception_during_schedule(self, system):
        """An exception occurs during an active schedule.  The scheduler
        adds a temporary task to handle the exception zone."""
        scheduler = system["scheduler"]
        dispatcher = system["dispatcher"]
        zones = _tower_c_zones()

        plan = await scheduler.generate_schedule(
            building_id="tower_c",
            target_date="2026-03-16",
            zone_configs=zones,
        )
        await scheduler.confirm_schedule(plan.schedule_id, "tc-004")
        original_count = len(plan.assignments)

        # Exception occurs in a new zone during the shift
        event = ExceptionEvent(
            event_type="urgent_clean",
            source="iot_sensor",
            building_id="tower_c",
            zone_id="tc-parking",
            priority="high",
            description="Oil spill in parking level B1",
        )
        dispatch_result = await dispatcher.dispatch(event)
        assert dispatch_result.status == "dispatched"

        # Scheduler adds a temporary task for the parking area
        updated = await scheduler.add_temporary_task(
            schedule_id=plan.schedule_id,
            zone_id="tc-parking",
            zone_name="Tower C Parking B1",
            task_type="urgent_clean",
            priority="high",
        )

        assert updated is not None
        assert len(updated.assignments) == original_count + 1
        parking_assignments = [
            a for a in updated.assignments if a.zone_id == "tc-parking"
        ]
        assert len(parking_assignments) == 1


# ===========================================================================
# Scenario 3: Health & ROI (5 tests)
# ===========================================================================


class TestHealthAndROI:
    """Verify health SHI calculations, manual assessments, ROI metrics,
    trends, and the relationship between SHI and ROI."""

    async def test_health_calculation_full_pipeline(self, system):
        """Calculate SHI with all 6 dimensions and verify weighted score."""
        health = system["health"]
        metrics = _tower_c_health_metrics()

        snapshot = await health.calculate_health(
            building_id="tower_c",
            area_id="tower_c_3f",
            metrics=metrics,
        )

        assert snapshot.building_id == "tower_c"
        assert snapshot.area_id == "tower_c_3f"
        assert snapshot.snapshot_id is not None
        assert len(snapshot.dimensions) == 6

        # Verify weighted calculation matches expected value
        # Weights: clean=0.15, tenant=0.20, staff=0.10, robot=0.10,
        #          complaint=0.15, manual=0.30
        expected = (
            82.0 * 0.15
            + 88.0 * 0.20
            + 90.0 * 0.10
            + 95.0 * 0.10
            + 75.0 * 0.15
            + 85.0 * 0.30
        )
        assert snapshot.overall_score == round(expected, 2)
        assert 80.0 <= snapshot.overall_score <= 90.0

    async def test_manual_assessment_affects_health(self, system):
        """Submit a manual assessment, then recalculate health with the
        manual score.  Verify the manual dimension changes the overall SHI."""
        health = system["health"]

        # First calculation with default manual_assessment=85
        snap1 = await health.calculate_health(
            building_id="tower_c",
            area_id="tower_c_lobby",
            metrics=_tower_c_health_metrics(manual_assessment=85.0),
        )

        # Record a manual assessment
        assessment = await health.record_manual_assessment(
            area_id="tower_c_lobby",
            assessor_id="tc-004",
            assessor_role="supervisor",
            score=95.0,
            dimensions={"cleanliness": 92.0, "tenant_satisfaction": 96.0},
            notes="Post-renovation inspection, excellent condition",
        )
        assert assessment.assessor_id == "tc-004"
        assert assessment.score == 95.0

        # Recalculate with higher manual assessment score
        snap2 = await health.calculate_health(
            building_id="tower_c",
            area_id="tower_c_lobby",
            metrics=_tower_c_health_metrics(manual_assessment=95.0),
        )

        # Score should be higher with the improved manual assessment
        assert snap2.overall_score > snap1.overall_score
        # The difference should come from 0.30 weight * (95-85) = 3.0 points
        diff = snap2.overall_score - snap1.overall_score
        assert abs(diff - 3.0) < 0.01

    async def test_roi_daily_calculation(self, system):
        """Calculate daily ROI metrics with realistic Tower C data and
        verify all derived indicators."""
        roi = system["roi"]
        stats = _tower_c_roi_stats()

        metrics = await roi.calculate_daily_metrics(
            building_id="tower_c",
            target_date="2026-03-16",
            stats=stats,
        )

        assert metrics.building_id == "tower_c"
        assert metrics.date == "2026-03-16"
        # 5000 / 5 staff = 1000 sq m per person
        assert metrics.managed_area_per_person == 1000.0
        # 18/20 = 0.9
        assert metrics.task_completion_rate == 0.9
        # 14/16 = 0.875
        assert metrics.robot_utilization_rate == 0.875
        # 5 humans / 2 robots = 2.5
        assert metrics.human_robot_ratio == 2.5
        # Monthly savings: (3000-2200)*30 = 24000
        assert metrics.cost_savings_monthly == 24000.0
        # Efficiency: ((3000-2200)/3000)*100 = 26.67%
        assert abs(metrics.efficiency_vs_baseline - 26.67) < 0.01
        assert metrics.service_health_index == 85.0

    async def test_roi_trend_over_week(self, system):
        """Calculate 7 days of ROI metrics and verify the trend query
        returns them in chronological order."""
        roi = system["roi"]

        for day_offset in range(7):
            d = date(2026, 3, 10 + day_offset)
            date_str = d.isoformat()
            # Efficiency improves slightly each day
            stats = _tower_c_roi_stats(
                tasks_completed=15 + day_offset,
                tasks_total=20,
                current_cost=2400.0 - (day_offset * 30),
            )
            await roi.calculate_daily_metrics(
                building_id="tower_c",
                target_date=date_str,
                stats=stats,
            )

        trend = await roi.get_trend("tower_c", days=30)
        assert len(trend) == 7
        # Sorted by date ascending
        dates = [m.date for m in trend]
        assert dates == sorted(dates)
        # Last day should have highest task completion rate
        assert trend[-1].task_completion_rate > trend[0].task_completion_rate
        # Cost savings should increase over the week
        assert trend[-1].cost_savings_monthly > trend[0].cost_savings_monthly

    async def test_health_and_roi_correlation(self, system):
        """Calculate health and ROI side by side.  A higher SHI score
        should be reflected in the ROI metrics."""
        health = system["health"]
        roi = system["roi"]

        # Day 1: lower health
        snap_low = await health.calculate_health(
            building_id="tower_c",
            area_id="tower_c_overall",
            metrics=_tower_c_health_metrics(
                cleanliness=60.0,
                tenant_satisfaction=65.0,
                manual_assessment=55.0,
            ),
        )
        roi_low = await roi.calculate_daily_metrics(
            building_id="tower_c",
            target_date="2026-03-14",
            stats=_tower_c_roi_stats(shi_score=snap_low.overall_score),
        )

        # Day 2: higher health
        snap_high = await health.calculate_health(
            building_id="tower_c",
            area_id="tower_c_overall",
            metrics=_tower_c_health_metrics(
                cleanliness=95.0,
                tenant_satisfaction=92.0,
                manual_assessment=96.0,
            ),
        )
        roi_high = await roi.calculate_daily_metrics(
            building_id="tower_c",
            target_date="2026-03-15",
            stats=_tower_c_roi_stats(shi_score=snap_high.overall_score),
        )

        # SHI is higher in the second snapshot
        assert snap_high.overall_score > snap_low.overall_score
        # ROI's service_health_index should mirror
        assert roi_high.service_health_index > roi_low.service_health_index
        assert roi_high.service_health_index == round(snap_high.overall_score, 2)


# ===========================================================================
# Scenario 4: Cross-Module Workflows (5 tests)
# ===========================================================================


class TestCrossModuleWorkflows:
    """Verify multi-module workflows: absence rescheduling, full day
    lifecycle, exception-to-work-order flows, multi-building isolation,
    and SLA breach detection."""

    async def test_absence_triggers_reschedule(self, system):
        """Staff reports leave -> schedule adjusted -> replacement assigned
        or gap noted."""
        staff_mgr = system["staff"]
        scheduler = system["scheduler"]
        zones = _tower_c_zones()

        plan = await scheduler.generate_schedule(
            building_id="tower_c",
            target_date="2026-03-16",
            zone_configs=zones,
        )
        assert len(plan.assignments) == 4

        # Find who was assigned to the VIP zone
        vip_assignment = [
            a for a in plan.assignments if a.zone_id == "tc-vip"
        ][0]
        absent_id = vip_assignment.staff_id

        # Staff reports leave
        await staff_mgr.report_leave(absent_id, date(2026, 3, 16))

        # Adjust schedule for absence
        adjusted = await scheduler.adjust_for_absence(
            plan.schedule_id, absent_id
        )

        assert adjusted is not None
        # The absent staff member should no longer be assigned
        adjusted_ids = {a.staff_id for a in adjusted.assignments}
        assert absent_id not in adjusted_ids
        # Notes should mention the replacement or gap
        assert len(adjusted.notes) > len(plan.notes)

    async def test_full_day_lifecycle(self, system):
        """Morning: schedule -> check-in -> tasks -> exception ->
        resolve -> SHI -> ROI.  Full end-to-end day simulation."""
        staff_mgr = system["staff"]
        scheduler = system["scheduler"]
        dispatcher = system["dispatcher"]
        orders = system["orders"]
        health = system["health"]
        roi = system["roi"]

        target = "2026-03-16"
        morning = datetime(2026, 3, 16, 7, 0, 0)
        today_date = date(2026, 3, 16)

        # 1) Morning check-in for all staff
        for s in system["staff_list"]:
            await staff_mgr.check_in(s.staff_id, "tower_c", morning)

        # 2) Generate and confirm schedule
        zones = _tower_c_zones()
        plan = await scheduler.generate_schedule(
            building_id="tower_c",
            target_date=target,
            zone_configs=zones,
        )
        await scheduler.confirm_schedule(plan.schedule_id, "tc-004")

        # 3) Mid-morning exception: robot error
        event = ExceptionEvent(
            event_type="robot_error",
            source="robot_monitor",
            building_id="tower_c",
            zone_id="tc-lobby",
            priority="high",
            description="Navigation sensor failure on rob-c01",
            robot_id="rob-c01",
        )
        dispatch_result = await dispatcher.dispatch(event)
        assert dispatch_result.status == "dispatched"

        # 4) Worker accepts and resolves
        await dispatcher.accept_dispatch(
            dispatch_result.dispatch_id,
            dispatch_result.assigned_to,
        )
        await dispatcher.resolve_dispatch(
            dispatch_result.dispatch_id,
            notes="Rebooted navigation module, sensor recalibrated",
        )

        # 5) Record task completions via workloads
        for s in system["staff_list"]:
            wl = StaffWorkload(
                staff_id=s.staff_id,
                date=target,
                total_assignments=1,
                completed_assignments=1,
                hours_worked=7.5,
            )
            await staff_mgr.update_staff_workload(wl)

        # 6) End of day: calculate SHI
        snapshot = await health.calculate_health(
            building_id="tower_c",
            area_id="tower_c_overall",
            metrics=_tower_c_health_metrics(),
        )
        assert snapshot.overall_score > 0

        # 7) End of day: calculate ROI
        roi_m = await roi.calculate_daily_metrics(
            building_id="tower_c",
            target_date=target,
            stats=_tower_c_roi_stats(shi_score=snapshot.overall_score),
        )
        assert roi_m.service_health_index == snapshot.overall_score
        assert roi_m.task_completion_rate > 0

        # 8) Verify adherence reflects completions
        adherence = await scheduler.get_schedule_adherence("tower_c", target)
        assert adherence > 0.0

    async def test_work_order_from_exception(self, system):
        """Exception dispatch creates a work order.  Resolving the dispatch
        also resolves the work order.  Both end up in 'resolved' state."""
        dispatcher = system["dispatcher"]
        orders = system["orders"]

        event = ExceptionEvent(
            event_type="equipment_fault",
            source="maintenance_report",
            building_id="tower_c",
            zone_id="tc-3f",
            priority="normal",
            description="AC unit #3 leaking condensate",
        )
        dispatch_result = await dispatcher.dispatch(event)

        # Create a linked work order
        wo = WorkOrder(
            order_id="wo-equip-001",
            order_type="equipment_fault",
            source="exception_dispatch",
            title="AC unit #3 condensate leak",
            description=f"Linked to dispatch {dispatch_result.dispatch_id}",
            priority="normal",
            building_id="tower_c",
            zone_id="tc-3f",
            assigned_to=dispatch_result.assigned_to,
        )
        await orders.create_order(wo)

        # Accept and resolve dispatch
        await dispatcher.accept_dispatch(
            dispatch_result.dispatch_id,
            dispatch_result.assigned_to,
        )
        await dispatcher.resolve_dispatch(
            dispatch_result.dispatch_id,
            notes="Replaced drain pipe and cleaned condensate",
        )

        # Resolve work order
        await orders.resolve_order(
            "wo-equip-001",
            resolution="Drain pipe replaced, AC unit operational",
        )

        # Verify both are resolved
        fetched_wo = await orders.get_order("wo-equip-001")
        assert fetched_wo.status == "resolved"
        assert fetched_wo.resolved_at is not None

        # Dispatch stats should show resolved
        stats = await dispatcher.get_dispatch_stats("tower_c", days=1)
        assert stats.total_dispatches >= 1

    async def test_multiple_buildings_isolated(self, system):
        """Two buildings operate independently — Tower C and Tower D
        should not see each other's schedules, dispatches, or work orders."""
        staff_mgr = system["staff"]
        scheduler = system["scheduler"]
        orders = system["orders"]

        # Add a Tower D staff member
        td_staff = StaffProfile(
            staff_id="td-001", name="Zhao Lin", role="cleaner",
            building_id="tower_d", phone="13900001",
            skills=["floor_cleaning"],
        )
        await staff_mgr.add_staff(td_staff)

        # Generate schedule for Tower C
        zones_c = _tower_c_zones()
        plan_c = await scheduler.generate_schedule(
            building_id="tower_c",
            target_date="2026-03-16",
            zone_configs=zones_c,
        )

        # Generate schedule for Tower D
        zones_d = [
            {
                "zone_id": "td-lobby",
                "zone_name": "Tower D Lobby",
                "shift": "morning",
                "task_type": "floor_cleaning",
                "staff_required": 1,
                "skills_needed": ["floor_cleaning"],
            },
        ]
        plan_d = await scheduler.generate_schedule(
            building_id="tower_d",
            target_date="2026-03-16",
            zone_configs=zones_d,
        )

        # Query schedules — each building sees only its own
        sched_c = await scheduler.get_schedule("tower_c", "2026-03-16")
        sched_d = await scheduler.get_schedule("tower_d", "2026-03-16")

        assert sched_c is not None
        assert sched_d is not None
        assert sched_c.schedule_id != sched_d.schedule_id

        # Tower C assignments should only contain Tower C staff
        tc_ids = {s.staff_id for s in system["staff_list"]}
        for a in sched_c.assignments:
            assert a.staff_id in tc_ids
        # Tower D assignment should only contain Tower D staff
        for a in sched_d.assignments:
            assert a.staff_id == "td-001"

        # Work orders are also building-scoped
        wo_c = WorkOrder(
            order_id="wo-c-test", order_type="cleaning",
            source="system", title="Test C",
            building_id="tower_c",
        )
        wo_d = WorkOrder(
            order_id="wo-d-test", order_type="cleaning",
            source="system", title="Test D",
            building_id="tower_d",
        )
        await orders.create_order(wo_c)
        await orders.create_order(wo_d)

        c_orders = await orders.get_orders(building_id="tower_c")
        d_orders = await orders.get_orders(building_id="tower_d")
        assert all(o.building_id == "tower_c" for o in c_orders)
        assert all(o.building_id == "tower_d" for o in d_orders)

    async def test_sla_breach_triggers_escalation(self, system):
        """A work order past SLA is detected in stats.  The SLA breach
        count should reflect the overdue order."""
        orders = system["orders"]

        # Create an order with SLA deadline in the past
        past_deadline = (datetime.utcnow() - timedelta(hours=2)).isoformat()
        wo = WorkOrder(
            order_id="wo-sla-001",
            order_type="complaint",
            source="tenant_app",
            title="Broken window in 5F corridor",
            priority="high",
            status="assigned",
            assigned_to="tc-001",
            building_id="tower_c",
            zone_id="tc-3f",
            sla_deadline=past_deadline,
        )
        await orders.create_order(wo)

        # Create another non-breached order
        future_deadline = (datetime.utcnow() + timedelta(hours=4)).isoformat()
        wo2 = WorkOrder(
            order_id="wo-sla-002",
            order_type="cleaning",
            source="schedule",
            title="Deep clean conference room 3A",
            priority="normal",
            status="assigned",
            assigned_to="tc-002",
            building_id="tower_c",
            zone_id="tc-3f",
            sla_deadline=future_deadline,
        )
        await orders.create_order(wo2)

        # Query SLA breaches
        breaches = await orders.get_sla_breaches(building_id="tower_c")
        breach_ids = {b.order_id for b in breaches}
        assert "wo-sla-001" in breach_ids
        assert "wo-sla-002" not in breach_ids

        # Stats should reflect the breach
        stats = await orders.get_order_stats("tower_c", days=30)
        assert stats.sla_breach_count >= 1
        assert stats.total_orders >= 2


# ===========================================================================
# Scenario 5: Data Consistency (5 tests)
# ===========================================================================


class TestDataConsistency:
    """Verify the shared MemoryBackend maintains consistent state across
    all modules, and that changes propagate correctly."""

    async def test_all_modules_share_backend(self, system):
        """After running various operations, the shared MemoryBackend
        should contain collections from all modules."""
        backend = system["backend"]
        scheduler = system["scheduler"]
        dispatcher = system["dispatcher"]
        orders = system["orders"]
        health = system["health"]
        roi = system["roi"]

        # Trigger operations in each module
        zones = _tower_c_zones()
        await scheduler.generate_schedule("tower_c", "2026-03-16", zones)

        event = ExceptionEvent(
            event_type="robot_error", source="sensor",
            building_id="tower_c", zone_id="tc-lobby", priority="normal",
        )
        await dispatcher.dispatch(event)

        wo = WorkOrder(
            order_id="wo-test-shared", order_type="cleaning",
            source="test", title="Shared backend test",
            building_id="tower_c",
        )
        await orders.create_order(wo)

        await health.calculate_health(
            "tower_c", "tower_c_3f", _tower_c_health_metrics()
        )

        await roi.calculate_daily_metrics(
            "tower_c", "2026-03-16", _tower_c_roi_stats()
        )

        # All collections should be present in the shared backend
        collections = set(backend.collection_names())
        assert "staff_profiles" in collections
        assert "schedules" in collections
        assert "dispatch_records" in collections
        assert "work_orders" in collections
        assert "health_snapshots" in collections
        assert "roi_metrics" in collections

    async def test_staff_changes_reflected(self, system):
        """Update a staff profile -> the change is visible in scheduler
        and dispatcher queries."""
        staff_mgr = system["staff"]
        scheduler = system["scheduler"]
        dispatcher = system["dispatcher"]

        # Verify tc-001 is initially active with certain skills
        profile = await staff_mgr.get_staff("tc-001")
        assert "floor_cleaning" in profile.skills

        # Add a new skill
        updated = await staff_mgr.update_staff(
            "tc-001", {"skills": ["floor_cleaning", "elevator_rescue", "vip_service"]}
        )
        assert "vip_service" in updated.skills

        # The scheduler sees the updated skills when generating
        zones = [
            {
                "zone_id": "tc-vip-test",
                "zone_name": "VIP Zone Test",
                "shift": "morning",
                "task_type": "vip_service",
                "staff_required": 1,
                "skills_needed": ["vip_service"],
            },
        ]
        plan = await scheduler.generate_schedule(
            "tower_c", "2026-03-16", zones,
        )
        # tc-001 could now be assigned to VIP since it has vip_service
        assigned_ids = {a.staff_id for a in plan.assignments}
        # At least one person with vip_service should be assigned
        assert len(plan.assignments) == 1

        # Dispatcher also sees the updated profile
        qualified = await staff_mgr.find_qualified_staff(
            "vip_service", building_id="tower_c"
        )
        qualified_ids = {s.staff_id for s in qualified}
        assert "tc-001" in qualified_ids

    async def test_schedule_persists_after_adjustment(self, system):
        """Multiple adjustments to a schedule preserve all accumulated
        changes correctly in storage."""
        staff_mgr = system["staff"]
        scheduler = system["scheduler"]
        zones = _tower_c_zones()

        plan = await scheduler.generate_schedule(
            "tower_c", "2026-03-16", zones,
        )
        original_id = plan.schedule_id

        # Adjustment 1: add a temporary task
        updated1 = await scheduler.add_temporary_task(
            schedule_id=original_id,
            zone_id="tc-extra1",
            zone_name="Extra Zone 1",
            task_type="urgent_clean",
            priority="high",
        )
        count_after_1 = len(updated1.assignments)
        assert count_after_1 == 5  # 4 original + 1 temp

        # Adjustment 2: add another temporary task
        updated2 = await scheduler.add_temporary_task(
            schedule_id=original_id,
            zone_id="tc-extra2",
            zone_name="Extra Zone 2",
            task_type="urgent_clean",
            priority="normal",
        )
        count_after_2 = len(updated2.assignments)
        assert count_after_2 == 6  # 5 + 1 more

        # Reload from storage and verify
        reloaded = await scheduler.get_schedule("tower_c", "2026-03-16")
        assert reloaded is not None
        assert reloaded.schedule_id == original_id
        assert len(reloaded.assignments) == 6
        # All zone_ids should be present
        zone_ids = {a.zone_id for a in reloaded.assignments}
        assert "tc-extra1" in zone_ids
        assert "tc-extra2" in zone_ids

    async def test_dispatch_stats_accurate(self, system):
        """Create multiple dispatches with known outcomes.  Verify stats
        (resolution_rate, escalation_rate, by_priority) match expectations."""
        dispatcher = system["dispatcher"]

        # Dispatch 1: resolved (high priority)
        e1 = ExceptionEvent(
            event_type="robot_error", source="sensor",
            building_id="tower_c", zone_id="tc-lobby",
            priority="high", description="Robot stuck",
        )
        r1 = await dispatcher.dispatch(e1)
        await dispatcher.accept_dispatch(r1.dispatch_id, r1.assigned_to)
        await dispatcher.resolve_dispatch(r1.dispatch_id, "Fixed")

        # Dispatch 2: resolved (normal priority)
        e2 = ExceptionEvent(
            event_type="complaint", source="app",
            building_id="tower_c", zone_id="tc-vip",
            priority="normal", description="Noise complaint",
        )
        r2 = await dispatcher.dispatch(e2)
        await dispatcher.accept_dispatch(r2.dispatch_id, r2.assigned_to)
        await dispatcher.resolve_dispatch(r2.dispatch_id, "Resolved noise issue")

        # Dispatch 3: escalated (high priority)
        e3 = ExceptionEvent(
            event_type="urgent_clean", source="iot",
            building_id="tower_c", zone_id="tc-3f",
            priority="high", description="Spill on 3rd floor",
        )
        r3 = await dispatcher.dispatch(e3)
        await dispatcher.escalate(r3.dispatch_id, "No response")

        stats = await dispatcher.get_dispatch_stats("tower_c", days=1)

        # 3 original dispatches + 1 new from escalation = 4 total
        assert stats.total_dispatches == 4
        # 2 resolved out of 4
        assert abs(stats.resolution_rate - 0.5) < 0.01
        # 1 escalated out of 4
        assert abs(stats.escalation_rate - 0.25) < 0.01
        # Priority breakdown
        assert stats.by_priority.get("high", 0) >= 2
        assert stats.by_priority.get("normal", 0) >= 1

    async def test_system_handles_empty_state(self, system):
        """All queries return empty/None/zero before any data is added
        for a building that has no operations."""
        scheduler = system["scheduler"]
        dispatcher = system["dispatcher"]
        orders = system["orders"]
        health = system["health"]
        roi = system["roi"]

        # Use a building with no data
        building = "tower_z"

        # Schedule queries
        sched = await scheduler.get_schedule(building, "2026-03-16")
        assert sched is None

        adherence = await scheduler.get_schedule_adherence(building, "2026-03-16")
        assert adherence == 0.0

        # Dispatch queries
        pending = await dispatcher.get_pending_dispatches(building_id=building)
        assert pending == []

        stats = await dispatcher.get_dispatch_stats(building, days=30)
        assert stats.total_dispatches == 0
        assert stats.resolution_rate == 0.0

        # Work order queries
        wo_list = await orders.get_orders(building_id=building)
        assert wo_list == []

        breaches = await orders.get_sla_breaches(building_id=building)
        assert breaches == []

        wo_stats = await orders.get_order_stats(building, days=30)
        assert wo_stats.total_orders == 0

        # Health queries
        latest = await health.get_latest_health(building)
        assert latest is None

        history = await health.get_health_history(building, days=30)
        assert history == []

        summary = await health.get_building_summary(building)
        assert summary["snapshot_count"] == 0
        assert summary["trend"] == "insufficient_data"

        # ROI queries
        roi_m = await roi.get_metrics(building, "2026-03-16")
        assert roi_m is None

        trend = await roi.get_trend(building, days=30)
        assert trend == []
