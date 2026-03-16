"""
Tests for H4 WorkOrderEngine module.

Covers CRUD operations, resolution lifecycle, filtered queries,
SLA breach detection, and aggregate statistics. All tests use
MemoryBackend and are fully self-contained.

Run:  PYTHONPATH=src pytest tests/test_work_order_engine.py -v
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from datetime import datetime, timedelta

from human_ops.models import OrderStats, WorkOrder
from human_ops.storage import MemoryBackend
from human_ops.work_order_engine import WorkOrderEngine

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def backend():
    return MemoryBackend()


@pytest_asyncio.fixture
async def engine(backend):
    return WorkOrderEngine(backend)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_order(
    order_id: str = "",
    order_type: str = "maintenance",
    building_id: str = "b001",
    title: str = "Fix leaky faucet",
    priority: str = "normal",
    status: str = "open",
    assigned_to: str | None = None,
    sla_deadline: str | None = None,
) -> WorkOrder:
    """Create a test work order with sensible defaults."""
    return WorkOrder(
        order_id=order_id,
        order_type=order_type,
        source="test",
        title=title,
        description=f"Test {order_type} order",
        priority=priority,
        status=status,
        assigned_to=assigned_to,
        building_id=building_id,
        zone_id="zone-1f",
        sla_deadline=sla_deadline,
    )


# ===================================================================
# 1. CRUD (5 tests)
# ===================================================================

async def test_create_order(engine):
    """test_create_order -- create a work order and retrieve by ID."""
    order = _make_order(order_id="wo001")
    order_id = await engine.create_order(order)
    assert order_id == "wo001"

    fetched = await engine.get_order("wo001")
    assert fetched is not None
    assert fetched.title == "Fix leaky faucet"
    assert fetched.order_type == "maintenance"
    assert fetched.building_id == "b001"
    assert fetched.created_at is not None


async def test_get_order(engine):
    """test_get_order -- retrieve an existing order by ID."""
    order = _make_order(order_id="wo002", title="Replace light bulb")
    await engine.create_order(order)

    fetched = await engine.get_order("wo002")
    assert fetched is not None
    assert fetched.order_id == "wo002"
    assert fetched.title == "Replace light bulb"


async def test_get_order_not_found(engine):
    """test_get_order_not_found -- querying a non-existent ID returns None."""
    result = await engine.get_order("nonexistent_999")
    assert result is None


async def test_assign_order(engine):
    """test_assign_order -- assign a work order to a staff member."""
    order = _make_order(order_id="wo003")
    await engine.create_order(order)

    ok = await engine.assign_order("wo003", "s001")
    assert ok is True

    fetched = await engine.get_order("wo003")
    assert fetched is not None
    assert fetched.assigned_to == "s001"
    assert fetched.status == "assigned"


async def test_update_status(engine):
    """test_update_status -- update order status field."""
    order = _make_order(order_id="wo004")
    await engine.create_order(order)

    ok = await engine.update_status("wo004", "in_progress")
    assert ok is True

    fetched = await engine.get_order("wo004")
    assert fetched is not None
    assert fetched.status == "in_progress"


# ===================================================================
# 2. Resolution (4 tests)
# ===================================================================

async def test_resolve_order(engine):
    """test_resolve_order -- status changes to resolved."""
    order = _make_order(order_id="wo010")
    await engine.create_order(order)

    ok = await engine.resolve_order("wo010", "Faucet replaced.")
    assert ok is True

    fetched = await engine.get_order("wo010")
    assert fetched is not None
    assert fetched.status == "resolved"
    assert fetched.resolution == "Faucet replaced."


async def test_resolve_with_notes(engine):
    """test_resolve_with_notes -- resolution text stored correctly."""
    order = _make_order(order_id="wo011")
    await engine.create_order(order)

    ok = await engine.resolve_order(
        "wo011", "Light bulb replaced with LED. Tested OK."
    )
    assert ok is True

    fetched = await engine.get_order("wo011")
    assert fetched is not None
    assert fetched.resolution == "Light bulb replaced with LED. Tested OK."


async def test_resolve_sets_timestamp(engine):
    """test_resolve_sets_timestamp -- resolved_at is set on resolution."""
    order = _make_order(order_id="wo012")
    await engine.create_order(order)

    ok = await engine.resolve_order("wo012", "Done.")
    assert ok is True

    fetched = await engine.get_order("wo012")
    assert fetched is not None
    assert fetched.resolved_at is not None
    # Verify it parses as a valid ISO datetime
    parsed = datetime.fromisoformat(fetched.resolved_at)
    assert isinstance(parsed, datetime)


async def test_resolve_nonexistent(engine):
    """test_resolve_nonexistent -- returns False for nonexistent order."""
    ok = await engine.resolve_order("nonexistent_id", "Done.")
    assert ok is False


# ===================================================================
# 3. Queries (5 tests)
# ===================================================================

async def test_get_orders_all(engine):
    """test_get_orders_all -- returns all orders when no filters given."""
    for i in range(3):
        await engine.create_order(
            _make_order(order_id=f"wo10{i}", building_id="b001")
        )

    orders = await engine.get_orders()
    assert len(orders) == 3


async def test_get_orders_by_building(engine):
    """test_get_orders_by_building -- filter by building_id."""
    await engine.create_order(_make_order(order_id="wo201", building_id="b001"))
    await engine.create_order(_make_order(order_id="wo202", building_id="b002"))
    await engine.create_order(_make_order(order_id="wo203", building_id="b001"))

    orders = await engine.get_orders(building_id="b001")
    assert len(orders) == 2
    assert all(o.building_id == "b001" for o in orders)


async def test_get_orders_by_status(engine):
    """test_get_orders_by_status -- filter by status."""
    await engine.create_order(_make_order(order_id="wo301"))
    await engine.create_order(_make_order(order_id="wo302"))
    await engine.assign_order("wo302", "s001")

    open_orders = await engine.get_orders(status="open")
    assert len(open_orders) == 1
    assert open_orders[0].order_id == "wo301"

    assigned_orders = await engine.get_orders(status="assigned")
    assert len(assigned_orders) == 1
    assert assigned_orders[0].order_id == "wo302"


async def test_get_orders_by_assignee(engine):
    """test_get_orders_by_assignee -- filter by assigned_to."""
    await engine.create_order(_make_order(order_id="wo401"))
    await engine.create_order(_make_order(order_id="wo402"))
    await engine.assign_order("wo401", "s001")
    await engine.assign_order("wo402", "s002")

    orders = await engine.get_orders(assigned_to="s001")
    assert len(orders) == 1
    assert orders[0].order_id == "wo401"
    assert orders[0].assigned_to == "s001"


async def test_get_orders_combined_filters(engine):
    """test_get_orders_combined_filters -- building + status + assignee combined."""
    await engine.create_order(_make_order(order_id="wo501", building_id="b001"))
    await engine.create_order(_make_order(order_id="wo502", building_id="b001"))
    await engine.create_order(_make_order(order_id="wo503", building_id="b002"))
    await engine.assign_order("wo501", "s001")
    await engine.assign_order("wo502", "s002")
    await engine.assign_order("wo503", "s001")

    # b001 + assigned + s001
    orders = await engine.get_orders(
        building_id="b001", status="assigned", assigned_to="s001",
    )
    assert len(orders) == 1
    assert orders[0].order_id == "wo501"


# ===================================================================
# 4. SLA (3 tests)
# ===================================================================

async def test_sla_breach_detected(engine):
    """test_sla_breach_detected -- orders past SLA deadline are returned."""
    past_deadline = (datetime.utcnow() - timedelta(hours=2)).isoformat()
    await engine.create_order(
        _make_order(order_id="wo601", sla_deadline=past_deadline)
    )

    breaches = await engine.get_sla_breaches()
    assert len(breaches) == 1
    assert breaches[0].order_id == "wo601"


async def test_no_breach_when_resolved(engine):
    """test_no_breach_when_resolved -- resolved orders not in breach list."""
    past_deadline = (datetime.utcnow() - timedelta(hours=2)).isoformat()
    await engine.create_order(
        _make_order(order_id="wo701", sla_deadline=past_deadline)
    )
    await engine.resolve_order("wo701", "Done.")

    breaches = await engine.get_sla_breaches()
    assert len(breaches) == 0


async def test_no_breach_when_future_deadline(engine):
    """test_no_breach_when_future_deadline -- future SLA not in breach list."""
    future_deadline = (datetime.utcnow() + timedelta(hours=24)).isoformat()
    await engine.create_order(
        _make_order(order_id="wo801", sla_deadline=future_deadline)
    )

    breaches = await engine.get_sla_breaches()
    assert len(breaches) == 0


# ===================================================================
# 5. Stats (3 tests)
# ===================================================================

async def test_basic_stats(engine):
    """test_basic_stats -- correct totals, open count, and breach count."""
    past_deadline = (datetime.utcnow() - timedelta(hours=2)).isoformat()

    # 3 orders in b001: 1 resolved, 1 open, 1 open with SLA breach
    await engine.create_order(
        _make_order(order_id="wo901", building_id="b001", order_type="maintenance")
    )
    await engine.resolve_order("wo901", "Fixed.")

    await engine.create_order(
        _make_order(order_id="wo902", building_id="b001", order_type="cleaning")
    )

    await engine.create_order(
        _make_order(
            order_id="wo903", building_id="b001", order_type="maintenance",
            sla_deadline=past_deadline,
        )
    )

    stats = await engine.get_order_stats("b001", days=30)
    assert isinstance(stats, OrderStats)
    assert stats.total_orders == 3
    assert stats.open_orders == 2  # wo902 + wo903
    assert stats.sla_breach_count == 1  # wo903
    assert stats.avg_resolution_hours >= 0.0


async def test_stats_empty(engine):
    """test_stats_empty -- zero stats when no orders exist."""
    stats = await engine.get_order_stats("b001", days=30)

    assert isinstance(stats, OrderStats)
    assert stats.total_orders == 0
    assert stats.open_orders == 0
    assert stats.avg_resolution_hours == 0.0
    assert stats.sla_breach_count == 0
    assert stats.by_type == {}


async def test_stats_by_type(engine):
    """test_stats_by_type -- by_type breakdown is correct."""
    await engine.create_order(
        _make_order(order_id="woA01", building_id="b001", order_type="maintenance")
    )
    await engine.create_order(
        _make_order(order_id="woA02", building_id="b001", order_type="maintenance")
    )
    await engine.create_order(
        _make_order(order_id="woA03", building_id="b001", order_type="cleaning")
    )
    await engine.create_order(
        _make_order(order_id="woA04", building_id="b001", order_type="inspection")
    )

    stats = await engine.get_order_stats("b001", days=30)
    assert stats.by_type["maintenance"] == 2
    assert stats.by_type["cleaning"] == 1
    assert stats.by_type["inspection"] == 1
    assert stats.total_orders == 4
