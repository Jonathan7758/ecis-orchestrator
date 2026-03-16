"""
ECIS V8 Demo Server — Human Operations Layer + Health + ROI

A self-contained FastAPI server exposing all V8 modules as HTTP endpoints.
Runs against an in-memory MemoryBackend seeded with Tower C sample data.

Usage:
    cd /root/projects/ecis/ecis-orchestrator/src
    PYTHONPATH=. uvicorn api.v8_demo_server:app --host 0.0.0.0 --port 9002
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from dataclasses import asdict
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from api.h5_routes import router as h5_router

# V8 Modules
from human_ops.storage import MemoryBackend
from human_ops.staff_manager import StaffManager
from human_ops.smart_scheduler import SmartScheduler
from human_ops.exception_dispatcher import ExceptionDispatcher
from human_ops.work_order_engine import WorkOrderEngine
from human_ops.models import (
    StaffProfile,
    ExceptionEvent,
    WorkOrder,
    SchedulePlan,
    Assignment,
    RobotAssignment,
)
from health.engine import HealthEngine, HealthWeights, HealthSnapshot, ManualAssessment
from roi.roi_engine import ROIEngine, ROIMetrics

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("v8_demo")

# =========================================================================
# Seed data — Tower C building
# =========================================================================

BUILDING_ID = "tower-c"

SEED_STAFF: List[Dict[str, Any]] = [
    {
        "staff_id": "tc-001",
        "name": "Zhang Wei",
        "role": "cleaner",
        "building_id": BUILDING_ID,
        "phone": "138-0001-0001",
        "skills": ["floor_cleaning", "waste_management"],
        "status": "active",
        "hire_date": "2024-03-15",
        "experience_years": 3.0,
    },
    {
        "staff_id": "tc-002",
        "name": "Li Na",
        "role": "cleaner",
        "building_id": BUILDING_ID,
        "phone": "138-0001-0002",
        "skills": ["floor_cleaning", "window_cleaning", "vip_service"],
        "status": "active",
        "hire_date": "2023-08-01",
        "experience_years": 4.5,
    },
    {
        "staff_id": "tc-003",
        "name": "Wang Qiang",
        "role": "security",
        "building_id": BUILDING_ID,
        "phone": "138-0001-0003",
        "skills": ["robot_rescue", "elevator_rescue", "patrol"],
        "status": "active",
        "hire_date": "2022-06-10",
        "experience_years": 6.0,
    },
    {
        "staff_id": "tc-004",
        "name": "Chen Mei",
        "role": "supervisor",
        "building_id": BUILDING_ID,
        "phone": "138-0001-0004",
        "skills": ["floor_cleaning", "vip_service", "inspection"],
        "status": "active",
        "hire_date": "2021-01-20",
        "experience_years": 8.0,
    },
    {
        "staff_id": "tc-005",
        "name": "Liu Gang",
        "role": "manager",
        "building_id": BUILDING_ID,
        "phone": "138-0001-0005",
        "skills": ["inspection", "vip_service", "robot_rescue"],
        "status": "active",
        "hire_date": "2020-04-01",
        "experience_years": 10.0,
    },
]

SEED_ZONE_CONFIGS: List[Dict[str, Any]] = [
    {
        "zone_id": "tc-lobby",
        "zone_name": "Tower C Lobby",
        "shift": "morning",
        "task_type": "floor_cleaning",
        "staff_required": 1,
        "skills_needed": ["floor_cleaning"],
    },
    {
        "zone_id": "tc-3f",
        "zone_name": "Tower C 3rd Floor",
        "shift": "morning",
        "task_type": "floor_cleaning",
        "staff_required": 1,
        "skills_needed": ["floor_cleaning"],
    },
    {
        "zone_id": "tc-parking",
        "zone_name": "Tower C Parking",
        "shift": "morning",
        "task_type": "patrol",
        "staff_required": 1,
        "skills_needed": ["patrol"],
    },
]

SEED_ROBOT_STATUS: List[Dict[str, Any]] = [
    {
        "robot_id": "GX-001",
        "zone_id": "tc-lobby",
        "task_type": "floor_cleaning",
        "battery_level": 92.0,
        "shift": "morning",
    },
    {
        "robot_id": "GX-002",
        "zone_id": "tc-3f",
        "task_type": "floor_cleaning",
        "battery_level": 87.0,
        "shift": "morning",
    },
]


# =========================================================================
# Lifespan — initialise shared modules with seed data
# =========================================================================

@asynccontextmanager
async def lifespan(application: FastAPI):
    """Initialise all V8 modules with a shared MemoryBackend and seed data."""

    backend = MemoryBackend()

    # Module instances
    staff_mgr = StaffManager(backend)
    scheduler = SmartScheduler(staff_mgr, backend)
    dispatcher = ExceptionDispatcher(staff_mgr, backend)
    work_orders = WorkOrderEngine(backend)
    health_eng = HealthEngine(backend)
    roi_eng = ROIEngine(backend)

    # Seed staff profiles
    for s in SEED_STAFF:
        await staff_mgr.add_staff(StaffProfile(**s))
    logger.info("Seeded %d staff profiles", len(SEED_STAFF))

    # Store instances on app state
    application.state.backend = backend
    application.state.staff_mgr = staff_mgr
    application.state.scheduler = scheduler
    application.state.dispatcher = dispatcher
    application.state.work_orders = work_orders
    application.state.health_eng = health_eng
    application.state.roi_eng = roi_eng

    yield  # Application is running

    # Cleanup
    await backend.clear()
    logger.info("V8 demo server shut down — memory cleared")


# =========================================================================
# FastAPI application
# =========================================================================

app = FastAPI(
    title="ECIS V8 Demo Server",
    description="Human Operations Layer + Health + ROI — Tower C Demo",
    version="8.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include H5 frontend routes
app.include_router(h5_router)


# =========================================================================
# Helpers
# =========================================================================

def _dc(obj: Any) -> Any:
    """Safely convert a dataclass (or list of dataclasses) to JSON-ready dicts."""
    if obj is None:
        return None
    if isinstance(obj, list):
        return [asdict(o) for o in obj]
    return asdict(obj)


# =========================================================================
# System endpoints
# =========================================================================

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<title>ECIS V8 Demo — Tower C</title>
<style>
  body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
         max-width: 900px; margin: 40px auto; padding: 0 20px; color: #333; }
  h1 { color: #1a56db; }
  h2 { border-bottom: 2px solid #e5e7eb; padding-bottom: 6px; margin-top: 32px; }
  .module { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px;
            padding: 16px; margin: 12px 0; }
  .module h3 { margin: 0 0 4px 0; color: #1e40af; }
  .module p { margin: 4px 0; color: #64748b; font-size: 0.9em; }
  a { color: #2563eb; text-decoration: none; }
  a:hover { text-decoration: underline; }
  .badge { display: inline-block; padding: 2px 8px; border-radius: 4px;
           font-size: 0.8em; font-weight: 600; }
  .ok { background: #dcfce7; color: #166534; }
  .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
           gap: 12px; margin: 16px 0; }
  .stat-card { background: #fff; border: 1px solid #e2e8f0; border-radius: 8px;
               padding: 16px; text-align: center; }
  .stat-card .value { font-size: 2em; font-weight: 700; color: #1a56db; }
  .stat-card .label { font-size: 0.85em; color: #64748b; margin-top: 4px; }
  ul { padding-left: 20px; }
  li { margin: 4px 0; }
</style>
</head>
<body>
<h1>ECIS V8 Demo Server</h1>
<p>Human Operations Layer + Service Health + ROI — Tower C</p>

<div class="stats" id="stats">
  <div class="stat-card"><div class="value" id="staff-count">--</div><div class="label">Staff Members</div></div>
  <div class="stat-card"><div class="value" id="schedule-status">--</div><div class="label">Today's Schedule</div></div>
  <div class="stat-card"><div class="value" id="pending-dispatch">--</div><div class="label">Pending Dispatches</div></div>
  <div class="stat-card"><div class="value" id="shi-score">--</div><div class="label">SHI Score</div></div>
</div>

<h2>V8 Modules</h2>
<div class="module">
  <h3>G11 Staff Management <span class="badge ok">OK</span></h3>
  <p>Full lifecycle: profiles, attendance, skill matching</p>
</div>
<div class="module">
  <h3>G12 Smart Scheduling <span class="badge ok">OK</span></h3>
  <p>Greedy skill-matching, absence adjustment, temp tasks</p>
</div>
<div class="module">
  <h3>H3 Exception Dispatch <span class="badge ok">OK</span></h3>
  <p>Priority-based autonomy, escalation, statistics</p>
</div>
<div class="module">
  <h3>H4 Work Order Engine <span class="badge ok">OK</span></h3>
  <p>CRUD, assignment, SLA breach detection, statistics</p>
</div>
<div class="module">
  <h3>D4+ Health Engine <span class="badge ok">OK</span></h3>
  <p>Weighted SHI calculation, manual assessments, trend analysis</p>
</div>
<div class="module">
  <h3>D5 ROI Engine <span class="badge ok">OK</span></h3>
  <p>Daily metrics, human-robot ratio, cost savings, trends</p>
</div>

<h2>Quick Links</h2>
<ul>
  <li><a href="/docs">Interactive API Docs (Swagger UI)</a></li>
  <li><a href="/redoc">ReDoc API Reference</a></li>
  <li><a href="/system/health">System Health Check</a></li>
  <li><a href="/system/modules">Module List</a></li>
  <li><a href="/staff">Staff List</a></li>
</ul>

<h2>Endpoint Groups</h2>
<ul>
  <li><strong>Staff</strong> — <code>/staff</code>, <code>/staff/{id}</code>, <code>/staff/{id}/check-in</code>, <code>/staff/{id}/check-out</code>, <code>/staff/{id}/leave</code></li>
  <li><strong>Schedule</strong> — <code>/schedule/generate</code>, <code>/schedule/{building}/{date}</code>, <code>/schedule/{id}/confirm</code></li>
  <li><strong>Dispatch</strong> — <code>/dispatch</code>, <code>/dispatch/{id}/accept</code>, <code>/dispatch/{id}/resolve</code>, <code>/dispatch/{id}/escalate</code></li>
  <li><strong>Orders</strong> — <code>/orders</code>, <code>/orders/{id}</code>, <code>/orders/{id}/assign</code>, <code>/orders/{id}/resolve</code></li>
  <li><strong>Health</strong> — <code>/health/calculate</code>, <code>/health/assessment</code>, <code>/health/{building}</code></li>
  <li><strong>ROI</strong> — <code>/roi/calculate</code>, <code>/roi/{building}</code>, <code>/roi/{building}/trend</code></li>
  <li><strong>Demo</strong> — <code>POST /demo/simulate-day</code></li>
</ul>

<script>
async function loadStats() {
  try {
    const [staffRes, dispatchRes, healthRes] = await Promise.all([
      fetch('/staff').then(r => r.json()),
      fetch('/dispatch/pending').then(r => r.json()),
      fetch('/health/' + 'tower-c').then(r => r.json()),
    ]);
    document.getElementById('staff-count').textContent = staffRes.length;
    document.getElementById('pending-dispatch').textContent = dispatchRes.length;
    const shi = healthRes.overall_score;
    document.getElementById('shi-score').textContent = shi !== undefined ? shi.toFixed(1) : 'N/A';
    document.getElementById('schedule-status').textContent = 'Ready';
  } catch (e) {
    console.log('Stats load error:', e);
  }
}
loadStats();
</script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse, tags=["System"])
async def dashboard():
    """Dashboard HTML page with module overview and live stats."""
    return DASHBOARD_HTML


@app.get("/system/health", tags=["System"])
async def system_health():
    """Health check with module status."""
    modules = {
        "staff_manager": app.state.staff_mgr is not None,
        "scheduler": app.state.scheduler is not None,
        "dispatcher": app.state.dispatcher is not None,
        "work_orders": app.state.work_orders is not None,
        "health_engine": app.state.health_eng is not None,
        "roi_engine": app.state.roi_eng is not None,
    }
    return {
        "status": "ok" if all(modules.values()) else "degraded",
        "version": "8.0.0",
        "building_id": BUILDING_ID,
        "modules": modules,
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.get("/system/modules", tags=["System"])
async def system_modules():
    """List all V8 modules with descriptions."""
    return [
        {"id": "G11", "name": "Staff Management", "service": "StaffManager",
         "description": "Staff profiles, attendance, skill matching"},
        {"id": "G12", "name": "Smart Scheduling", "service": "SmartScheduler",
         "description": "Greedy skill-matching, absence adjustment, temp tasks"},
        {"id": "H3", "name": "Exception Dispatch", "service": "ExceptionDispatcher",
         "description": "Priority-based dispatch, autonomy levels, escalation"},
        {"id": "H4", "name": "Work Order Engine", "service": "WorkOrderEngine",
         "description": "Work order CRUD, SLA breach detection, statistics"},
        {"id": "D4+", "name": "Health Engine", "service": "HealthEngine",
         "description": "Weighted SHI calculation, manual assessments, trends"},
        {"id": "D5", "name": "ROI Engine", "service": "ROIEngine",
         "description": "Daily ROI metrics, human-robot ratio, cost savings"},
    ]


# =========================================================================
# G11 — Staff Management
# =========================================================================

@app.get("/staff", tags=["G11 Staff"])
async def list_staff(
    building_id: Optional[str] = Query(None),
    role: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
):
    """List all staff with optional filters."""
    staff = await app.state.staff_mgr.list_staff(
        building_id=building_id, role=role, status=status,
    )
    return _dc(staff)


@app.get("/staff/available/{building_id}", tags=["G11 Staff"])
async def get_available_staff(building_id: str):
    """Get available (active, not on leave) staff for a building."""
    staff = await app.state.staff_mgr.get_available_staff(building_id=building_id)
    return _dc(staff)


@app.get("/staff/qualified/{skill}", tags=["G11 Staff"])
async def find_qualified_staff(
    skill: str,
    building_id: Optional[str] = Query(None),
):
    """Find staff members who possess a given skill."""
    staff = await app.state.staff_mgr.find_qualified_staff(
        skill=skill, building_id=building_id,
    )
    return _dc(staff)


@app.get("/staff/{staff_id}", tags=["G11 Staff"])
async def get_staff(staff_id: str):
    """Get staff details by ID."""
    profile = await app.state.staff_mgr.get_staff(staff_id)
    if profile is None:
        raise HTTPException(status_code=404, detail=f"Staff {staff_id} not found")
    return _dc(profile)


@app.post("/staff", tags=["G11 Staff"], status_code=201)
async def add_staff(body: Dict[str, Any]):
    """Add a new staff member."""
    try:
        profile = StaffProfile(**body)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    result = await app.state.staff_mgr.add_staff(profile)
    return _dc(result)


@app.put("/staff/{staff_id}", tags=["G11 Staff"])
async def update_staff(staff_id: str, body: Dict[str, Any]):
    """Update a staff member's profile."""
    result = await app.state.staff_mgr.update_staff(staff_id, body)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Staff {staff_id} not found")
    return _dc(result)


@app.post("/staff/{staff_id}/check-in", tags=["G11 Staff"])
async def check_in(staff_id: str, body: Dict[str, Any]):
    """Check in a staff member. Body: {"building_id": "tower-c"}"""
    building = body.get("building_id")
    if not building:
        raise HTTPException(status_code=400, detail="building_id is required")
    record = await app.state.staff_mgr.check_in(staff_id, building)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Staff {staff_id} not found")
    return _dc(record)


@app.post("/staff/{staff_id}/check-out", tags=["G11 Staff"])
async def check_out(staff_id: str):
    """Check out a staff member."""
    record = await app.state.staff_mgr.check_out(staff_id)
    if record is None:
        raise HTTPException(
            status_code=404,
            detail=f"No check-in found for {staff_id} today",
        )
    return _dc(record)


@app.post("/staff/{staff_id}/leave", tags=["G11 Staff"])
async def report_leave(staff_id: str):
    """Report a staff member as on leave today."""
    record = await app.state.staff_mgr.report_leave(staff_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Staff {staff_id} not found")
    return _dc(record)


# =========================================================================
# G12 — Scheduling
# =========================================================================

@app.post("/schedule/generate", tags=["G12 Schedule"])
async def generate_schedule(body: Dict[str, Any]):
    """Generate a schedule plan.

    Body: {
        "building_id": "tower-c",
        "date": "2026-03-16",
        "zone_configs": [...],
        "robot_status": [...]   // optional
    }
    """
    building_id = body.get("building_id", BUILDING_ID)
    target_date = body.get("date", date.today().isoformat())
    zone_configs = body.get("zone_configs", SEED_ZONE_CONFIGS)
    robot_status = body.get("robot_status", SEED_ROBOT_STATUS)

    try:
        plan = await app.state.scheduler.generate_schedule(
            building_id=building_id,
            target_date=target_date,
            zone_configs=zone_configs,
            robot_status=robot_status,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _dc(plan)


@app.get("/schedule/{building_id}/{target_date}", tags=["G12 Schedule"])
async def get_schedule(building_id: str, target_date: str):
    """Get a schedule for a building on a given date."""
    plan = await app.state.scheduler.get_schedule(building_id, target_date)
    if plan is None:
        raise HTTPException(
            status_code=404,
            detail=f"No schedule for {building_id} on {target_date}",
        )
    return _dc(plan)


@app.post("/schedule/{schedule_id}/confirm", tags=["G12 Schedule"])
async def confirm_schedule(schedule_id: str, body: Dict[str, Any] = {}):
    """Confirm a schedule plan. Body: {"confirmed_by": "tc-005"}"""
    confirmed_by = body.get("confirmed_by", "system")
    ok = await app.state.scheduler.confirm_schedule(schedule_id, confirmed_by)
    if not ok:
        raise HTTPException(
            status_code=404,
            detail=f"Schedule {schedule_id} not found",
        )
    return {"status": "confirmed", "schedule_id": schedule_id, "confirmed_by": confirmed_by}


@app.post("/schedule/{schedule_id}/absence", tags=["G12 Schedule"])
async def adjust_for_absence(schedule_id: str, body: Dict[str, Any]):
    """Adjust schedule for staff absence. Body: {"staff_id": "tc-001"}"""
    staff_id = body.get("staff_id")
    if not staff_id:
        raise HTTPException(status_code=400, detail="staff_id is required")
    plan = await app.state.scheduler.adjust_for_absence(schedule_id, staff_id)
    if plan is None:
        raise HTTPException(
            status_code=404,
            detail=f"Schedule {schedule_id} not found",
        )
    return _dc(plan)


@app.post("/schedule/{schedule_id}/temp-task", tags=["G12 Schedule"])
async def add_temp_task(schedule_id: str, body: Dict[str, Any]):
    """Add a temporary task to a schedule.

    Body: {"zone_id": "tc-lobby", "zone_name": "Tower C Lobby",
           "task_type": "urgent_clean", "priority": "high"}
    """
    zone_id = body.get("zone_id", "tc-lobby")
    zone_name = body.get("zone_name", "Tower C Lobby")
    task_type = body.get("task_type", "floor_cleaning")
    priority = body.get("priority", "normal")

    plan = await app.state.scheduler.add_temporary_task(
        schedule_id=schedule_id,
        zone_id=zone_id,
        zone_name=zone_name,
        task_type=task_type,
        priority=priority,
    )
    if plan is None:
        raise HTTPException(
            status_code=404,
            detail=f"Schedule {schedule_id} not found",
        )
    return _dc(plan)


# =========================================================================
# H3 — Exception Dispatch
# =========================================================================

@app.post("/dispatch", tags=["H3 Dispatch"])
async def dispatch_exception(body: Dict[str, Any]):
    """Dispatch staff for an exception event.

    Body: {"event_type": "robot_error", "source": "GX-001",
           "building_id": "tower-c", "zone_id": "tc-lobby",
           "priority": "high", "description": "Robot stuck",
           "robot_id": "GX-001"}
    """
    try:
        event = ExceptionEvent(
            event_type=body["event_type"],
            source=body["source"],
            building_id=body.get("building_id", BUILDING_ID),
            zone_id=body["zone_id"],
            priority=body.get("priority", "normal"),
            description=body.get("description", ""),
            robot_id=body.get("robot_id"),
        )
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    result = await app.state.dispatcher.dispatch(event)
    return _dc(result)


@app.post("/dispatch/{dispatch_id}/accept", tags=["H3 Dispatch"])
async def accept_dispatch(dispatch_id: str, body: Dict[str, Any] = {}):
    """Accept a dispatch. Body: {"staff_id": "tc-003"}"""
    staff_id = body.get("staff_id", "")
    ok = await app.state.dispatcher.accept_dispatch(dispatch_id, staff_id)
    if not ok:
        raise HTTPException(
            status_code=404,
            detail=f"Dispatch {dispatch_id} not found",
        )
    return {"status": "accepted", "dispatch_id": dispatch_id}


@app.post("/dispatch/{dispatch_id}/resolve", tags=["H3 Dispatch"])
async def resolve_dispatch(dispatch_id: str, body: Dict[str, Any] = {}):
    """Resolve a dispatch. Body: {"notes": "Robot rebooted successfully"}"""
    notes = body.get("notes", "")
    ok = await app.state.dispatcher.resolve_dispatch(dispatch_id, notes)
    if not ok:
        raise HTTPException(
            status_code=404,
            detail=f"Dispatch {dispatch_id} not found",
        )
    return {"status": "resolved", "dispatch_id": dispatch_id}


@app.post("/dispatch/{dispatch_id}/escalate", tags=["H3 Dispatch"])
async def escalate_dispatch(dispatch_id: str, body: Dict[str, Any] = {}):
    """Escalate a dispatch. Body: {"reason": "Staff unable to resolve"}"""
    reason = body.get("reason", "")
    new_result = await app.state.dispatcher.escalate(dispatch_id, reason)
    if new_result is None:
        raise HTTPException(
            status_code=404,
            detail=f"Dispatch {dispatch_id} not found or no replacement available",
        )
    return _dc(new_result)


@app.get("/dispatch/pending", tags=["H3 Dispatch"])
async def get_pending_dispatches(building_id: Optional[str] = Query(None)):
    """Get pending (actionable) dispatches."""
    records = await app.state.dispatcher.get_pending_dispatches(building_id)
    return _dc(records)


@app.get("/dispatch/stats/{building_id}", tags=["H3 Dispatch"])
async def get_dispatch_stats(building_id: str, days: int = Query(7)):
    """Get aggregate dispatch statistics for a building."""
    stats = await app.state.dispatcher.get_dispatch_stats(building_id, days)
    return _dc(stats)


# =========================================================================
# H4 — Work Orders
# =========================================================================

@app.post("/orders", tags=["H4 Orders"], status_code=201)
async def create_order(body: Dict[str, Any]):
    """Create a new work order.

    Body: {"order_type": "maintenance", "source": "dispatch",
           "title": "Fix elevator sensor", "priority": "high",
           "building_id": "tower-c", "zone_id": "tc-lobby"}
    """
    try:
        order = WorkOrder(
            order_id=body.get("order_id", ""),
            order_type=body["order_type"],
            source=body["source"],
            title=body["title"],
            description=body.get("description", ""),
            priority=body.get("priority", "normal"),
            building_id=body.get("building_id", BUILDING_ID),
            zone_id=body.get("zone_id"),
            sla_deadline=body.get("sla_deadline"),
        )
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    order_id = await app.state.work_orders.create_order(order)
    return {"order_id": order_id, "status": "open"}


@app.get("/orders", tags=["H4 Orders"])
async def list_orders(
    building_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
):
    """List work orders with optional filters."""
    orders = await app.state.work_orders.get_orders(
        building_id=building_id, status=status,
    )
    return _dc(orders)


@app.get("/orders/sla-breaches", tags=["H4 Orders"])
async def get_sla_breaches(building_id: Optional[str] = Query(None)):
    """Get work orders that have breached their SLA deadline."""
    breaches = await app.state.work_orders.get_sla_breaches(building_id)
    return _dc(breaches)


@app.get("/orders/stats/{building_id}", tags=["H4 Orders"])
async def get_order_stats(building_id: str, days: int = Query(30)):
    """Get aggregate work order statistics for a building."""
    stats = await app.state.work_orders.get_order_stats(building_id, days)
    return _dc(stats)


@app.get("/orders/{order_id}", tags=["H4 Orders"])
async def get_order(order_id: str):
    """Get a work order by ID."""
    order = await app.state.work_orders.get_order(order_id)
    if order is None:
        raise HTTPException(status_code=404, detail=f"Order {order_id} not found")
    return _dc(order)


@app.post("/orders/{order_id}/assign", tags=["H4 Orders"])
async def assign_order(order_id: str, body: Dict[str, Any]):
    """Assign a work order. Body: {"staff_id": "tc-003"}"""
    staff_id = body.get("staff_id")
    if not staff_id:
        raise HTTPException(status_code=400, detail="staff_id is required")
    ok = await app.state.work_orders.assign_order(order_id, staff_id)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Order {order_id} not found")
    return {"order_id": order_id, "status": "assigned", "assigned_to": staff_id}


@app.post("/orders/{order_id}/resolve", tags=["H4 Orders"])
async def resolve_order(order_id: str, body: Dict[str, Any] = {}):
    """Resolve a work order. Body: {"resolution": "Sensor replaced"}"""
    resolution = body.get("resolution", "Resolved")
    ok = await app.state.work_orders.resolve_order(order_id, resolution)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Order {order_id} not found")
    return {"order_id": order_id, "status": "resolved"}


# =========================================================================
# D4+ — Health
# =========================================================================

@app.post("/health/calculate", tags=["D4+ Health"])
async def calculate_health(body: Dict[str, Any]):
    """Calculate Service Health Index.

    Body: {"building_id": "tower-c", "area_id": "tower-c_3f",
           "metrics": {"cleanliness": 85, "tenant_satisfaction": 90,
                       "staff_attendance": 95, "robot_availability": 88,
                       "complaint_response": 82, "manual_assessment": 78}}
    """
    building_id = body.get("building_id", BUILDING_ID)
    area_id = body.get("area_id")
    metrics = body.get("metrics")
    if not area_id or not metrics:
        raise HTTPException(
            status_code=400,
            detail="area_id and metrics are required",
        )
    snapshot = await app.state.health_eng.calculate_health(
        building_id=building_id, area_id=area_id, metrics=metrics,
    )
    return _dc(snapshot)


@app.post("/health/assessment", tags=["D4+ Health"])
async def submit_assessment(body: Dict[str, Any]):
    """Submit a manual health assessment.

    Body: {"area_id": "tower-c_3f", "assessor_id": "tc-005",
           "assessor_role": "manager", "score": 82,
           "notes": "Lobby needs attention"}
    """
    try:
        assessment = await app.state.health_eng.record_manual_assessment(
            area_id=body["area_id"],
            assessor_id=body["assessor_id"],
            assessor_role=body.get("assessor_role", "manager"),
            score=body["score"],
            dimensions=body.get("dimensions"),
            notes=body.get("notes", ""),
        )
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _dc(assessment)


@app.get("/health/{building_id}", tags=["D4+ Health"])
async def get_building_health(building_id: str):
    """Get building health summary (average score, dimensions, trend)."""
    summary = await app.state.health_eng.get_building_summary(building_id)
    return summary


@app.get("/health/{building_id}/history", tags=["D4+ Health"])
async def get_health_history(building_id: str, days: int = Query(30)):
    """Get health snapshots history for a building."""
    snapshots = await app.state.health_eng.get_health_history(building_id, days)
    return _dc(snapshots)


# =========================================================================
# D5 — ROI
# =========================================================================

@app.post("/roi/calculate", tags=["D5 ROI"])
async def calculate_roi(body: Dict[str, Any]):
    """Calculate daily ROI metrics.

    Body: {"building_id": "tower-c", "date": "2026-03-16",
           "stats": {"total_area": 15000, "staff_count": 5,
                     "robot_count": 2, "tasks_completed": 18,
                     "tasks_total": 20, "robot_hours": 14,
                     "total_hours": 16, "baseline_cost": 5000,
                     "current_cost": 3200, "shi_score": 85.5}}
    """
    building_id = body.get("building_id", BUILDING_ID)
    target_date = body.get("date", date.today().isoformat())
    stats = body.get("stats")
    if not stats:
        raise HTTPException(status_code=400, detail="stats dict is required")

    metrics = await app.state.roi_eng.calculate_daily_metrics(
        building_id=building_id, target_date=target_date, stats=stats,
    )
    return _dc(metrics)


@app.get("/roi/{building_id}", tags=["D5 ROI"])
async def get_latest_roi(building_id: str):
    """Get the latest ROI metrics for a building."""
    docs = await app.state.backend.query("roi_metrics", {"building_id": building_id})
    if not docs:
        raise HTTPException(
            status_code=404,
            detail=f"No ROI data for {building_id}",
        )
    docs.sort(key=lambda d: d.get("date", ""), reverse=True)
    return docs[0]


@app.get("/roi/{building_id}/trend", tags=["D5 ROI"])
async def get_roi_trend(building_id: str, days: int = Query(90)):
    """Get ROI metrics trend for a building."""
    metrics = await app.state.roi_eng.get_trend(building_id, days)
    if not metrics:
        raise HTTPException(
            status_code=404,
            detail=f"No ROI trend data for {building_id}",
        )
    return _dc(metrics)


# =========================================================================
# Demo Scenarios
# =========================================================================

@app.post("/demo/simulate-day", tags=["Demo"])
async def simulate_day(body: Dict[str, Any] = {}):
    """Simulate a full Tower C operational day.

    Runs through: schedule generation -> staff check-ins ->
    exception events -> work order -> health calculation -> ROI.

    Returns all results in a single response.
    """
    target_date = body.get("date", date.today().isoformat())
    results: Dict[str, Any] = {"date": target_date, "building_id": BUILDING_ID}

    # ------------------------------------------------------------------
    # 1. Generate schedule
    # ------------------------------------------------------------------
    plan = await app.state.scheduler.generate_schedule(
        building_id=BUILDING_ID,
        target_date=target_date,
        zone_configs=SEED_ZONE_CONFIGS,
        robot_status=SEED_ROBOT_STATUS,
    )
    results["schedule"] = {
        "schedule_id": plan.schedule_id,
        "assignments": len(plan.assignments),
        "robot_assignments": len(plan.robot_assignments),
        "confidence": plan.confidence,
        "status": plan.status,
    }

    # Confirm the schedule
    await app.state.scheduler.confirm_schedule(plan.schedule_id, "tc-005")
    results["schedule"]["status"] = "confirmed"

    # ------------------------------------------------------------------
    # 2. Staff check-ins
    # ------------------------------------------------------------------
    check_ins = []
    for staff_data in SEED_STAFF:
        sid = staff_data["staff_id"]
        record = await app.state.staff_mgr.check_in(sid, BUILDING_ID)
        if record is not None:
            check_ins.append({"staff_id": sid, "status": record.status})
    results["check_ins"] = check_ins

    # ------------------------------------------------------------------
    # 3. Exception event — robot error in lobby
    # ------------------------------------------------------------------
    event = ExceptionEvent(
        event_type="robot_error",
        source="GX-001",
        building_id=BUILDING_ID,
        zone_id="tc-lobby",
        priority="high",
        description="Robot GX-001 navigation sensor malfunction in lobby",
        robot_id="GX-001",
    )
    dispatch_result = await app.state.dispatcher.dispatch(event)
    results["exception_dispatch"] = _dc(dispatch_result)

    # Accept and resolve
    await app.state.dispatcher.accept_dispatch(
        dispatch_result.dispatch_id,
        dispatch_result.assigned_to or "",
    )
    await app.state.dispatcher.resolve_dispatch(
        dispatch_result.dispatch_id,
        "Rebooted sensor module, robot resumed cleaning",
    )
    results["exception_dispatch"]["final_status"] = "resolved"

    # ------------------------------------------------------------------
    # 4. Exception event — complaint on 3F
    # ------------------------------------------------------------------
    complaint = ExceptionEvent(
        event_type="complaint",
        source="tenant-portal",
        building_id=BUILDING_ID,
        zone_id="tc-3f",
        priority="normal",
        description="Tenant reports coffee spill near elevator",
    )
    complaint_result = await app.state.dispatcher.dispatch(complaint)
    results["complaint_dispatch"] = _dc(complaint_result)

    # ------------------------------------------------------------------
    # 5. Work order — maintenance
    # ------------------------------------------------------------------
    order = WorkOrder(
        order_id="",
        order_type="maintenance",
        source="dispatch",
        title="Replace lobby floor scrubber filter",
        description="Filter clogged, reduced cleaning efficiency",
        priority="normal",
        building_id=BUILDING_ID,
        zone_id="tc-lobby",
        sla_deadline=(datetime.utcnow() + timedelta(hours=24)).isoformat(),
    )
    order_id = await app.state.work_orders.create_order(order)
    await app.state.work_orders.assign_order(order_id, "tc-003")
    results["work_order"] = {"order_id": order_id, "status": "assigned"}

    # ------------------------------------------------------------------
    # 6. Health calculation — three areas
    # ------------------------------------------------------------------
    health_areas = [
        ("tower-c_lobby", {"cleanliness": 88, "tenant_satisfaction": 85,
                           "staff_attendance": 100, "robot_availability": 92,
                           "complaint_response": 80, "manual_assessment": 82}),
        ("tower-c_3f", {"cleanliness": 75, "tenant_satisfaction": 78,
                        "staff_attendance": 100, "robot_availability": 87,
                        "complaint_response": 70, "manual_assessment": 76}),
        ("tower-c_parking", {"cleanliness": 90, "tenant_satisfaction": 92,
                             "staff_attendance": 100, "robot_availability": 0,
                             "complaint_response": 95, "manual_assessment": 88}),
    ]
    health_results = []
    for area_id, metrics in health_areas:
        snap = await app.state.health_eng.calculate_health(
            building_id=BUILDING_ID, area_id=area_id, metrics=metrics,
        )
        health_results.append({
            "area_id": area_id,
            "overall_score": snap.overall_score,
        })
    results["health"] = health_results

    # Manual assessment from manager
    assessment = await app.state.health_eng.record_manual_assessment(
        area_id="tower-c_lobby",
        assessor_id="tc-005",
        assessor_role="manager",
        score=84.0,
        notes="Lobby generally clean, minor scuff marks near entrance",
    )
    results["manual_assessment"] = {
        "area_id": assessment.area_id,
        "score": assessment.score,
    }

    # Building summary
    summary = await app.state.health_eng.get_building_summary(BUILDING_ID)
    results["building_health_summary"] = summary

    # ------------------------------------------------------------------
    # 7. ROI calculation
    # ------------------------------------------------------------------
    roi_stats = {
        "total_area": 15000.0,
        "staff_count": 5,
        "robot_count": 2,
        "tasks_completed": 18,
        "tasks_total": 20,
        "robot_hours": 14.0,
        "total_hours": 16.0,
        "baseline_cost": 5000.0,
        "current_cost": 3200.0,
        "shi_score": summary.get("overall_score", 0.0),
    }
    roi_metrics = await app.state.roi_eng.calculate_daily_metrics(
        building_id=BUILDING_ID, target_date=target_date, stats=roi_stats,
    )
    results["roi"] = _dc(roi_metrics)

    # ------------------------------------------------------------------
    # 8. Staff check-outs
    # ------------------------------------------------------------------
    for staff_data in SEED_STAFF:
        await app.state.staff_mgr.check_out(staff_data["staff_id"])
    results["check_outs"] = "all_completed"

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    results["summary"] = {
        "schedule_assignments": len(plan.assignments),
        "staff_checked_in": len(check_ins),
        "exceptions_handled": 2,
        "work_orders_created": 1,
        "health_areas_measured": len(health_results),
        "avg_health_score": round(
            sum(h["overall_score"] for h in health_results) / len(health_results), 2
        ),
        "roi_efficiency_vs_baseline": roi_metrics.efficiency_vs_baseline,
        "roi_cost_savings_monthly": roi_metrics.cost_savings_monthly,
    }

    return results


# =========================================================================
# Entrypoint
# =========================================================================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "api.v8_demo_server:app",
        host="0.0.0.0",
        port=9002,
        reload=True,
    )
