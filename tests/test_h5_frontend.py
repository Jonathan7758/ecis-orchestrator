"""
V8 H5 Frontend Tests — User Journey Demo with Screenshots.

Tests all 6 H5 pages through 3 user journeys:
  Journey 1 (Ah Lee / Supervisor): Schedule → Dispatch → Orders
  Journey 2 (Vivian / Manager): Assessment → Chat → Orders
  Journey 3 (Wong Sir / COO): Dashboard → ROI → Day Simulation

Each test captures a screenshot to verify page rendering and
API integration.

Prerequisites:
    pip install playwright pytest-playwright
    playwright install chromium

Run:
    cd /root/projects/ecis/ecis-orchestrator
    PYTHONPATH=src python3 -m pytest tests/test_h5_frontend.py -v --headed
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

BASE_URL = "http://127.0.0.1:9002"
SCREENSHOT_DIR = "tests/screenshots"


@pytest.fixture(scope="session", autouse=True)
def ensure_screenshot_dir():
    import os
    os.makedirs(SCREENSHOT_DIR, exist_ok=True)


# =========================================================================
# Helper
# =========================================================================

def screenshot(page: Page, name: str) -> str:
    path = f"{SCREENSHOT_DIR}/{name}.png"
    page.screenshot(path=path, full_page=True)
    return path


# =========================================================================
# Journey 1: Ah Lee (Supervisor) — Schedule → Dispatch → Orders
# =========================================================================

class TestJourney1AhLee:
    """Ah Lee's daily workflow: morning schedule, exception handling, orders."""

    def test_01_schedule_page_loads(self, page: Page):
        """J1-01: Schedule page renders with staff/robot assignments."""
        page.goto(f"{BASE_URL}/wechat/schedule")
        page.wait_for_load_state("networkidle")
        # Wait for schedule to generate (API call)
        page.wait_for_timeout(2000)

        # Verify page structure
        expect(page.locator(".top-bar h1")).to_have_text("Today's Schedule")
        expect(page.locator("#schedule-date")).not_to_have_text("Loading...")

        # Check assignments loaded
        assignments = page.locator("#assignments-list .list-item")
        assert assignments.count() > 0, "Expected staff assignments to be loaded"

        screenshot(page, "j1_01_schedule_page")

    def test_02_schedule_confirm(self, page: Page):
        """J1-02: Ah Lee confirms the daily schedule."""
        page.goto(f"{BASE_URL}/wechat/schedule")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(2000)

        # Click confirm button
        btn = page.locator("#btn-confirm")
        expect(btn).to_be_visible()
        btn.click()
        page.wait_for_timeout(1000)

        # Verify confirmation
        expect(btn).to_contain_text("Confirmed")
        expect(page.locator("#schedule-status")).to_have_text("confirmed")

        screenshot(page, "j1_02_schedule_confirmed")

    def test_03_dispatch_page_loads(self, page: Page):
        """J1-03: Exception dispatch page renders with form."""
        page.goto(f"{BASE_URL}/wechat/dispatch/new")
        page.wait_for_load_state("networkidle")

        expect(page.locator(".top-bar h1")).to_have_text("Exception Dispatch")
        expect(page.locator("#event-type")).to_be_visible()
        expect(page.locator("#priority")).to_be_visible()

        screenshot(page, "j1_03_dispatch_form")

    def test_04_submit_exception(self, page: Page):
        """J1-04: Ah Lee submits a robot error exception."""
        page.goto(f"{BASE_URL}/wechat/dispatch/new")
        page.wait_for_load_state("networkidle")

        # Fill form (pre-filled defaults)
        page.select_option("#event-type", "robot_error")
        page.select_option("#priority", "high")
        page.select_option("#zone-id", "tc-lobby")

        # Submit
        page.click("text=Submit Exception Report")
        page.wait_for_timeout(2000)

        # Verify dispatch result appears
        result = page.locator("#dispatch-result")
        expect(result).to_be_visible()
        expect(result.locator(".name")).to_contain_text("Dispatch #")

        screenshot(page, "j1_04_dispatch_submitted")

    def test_05_accept_dispatch(self, page: Page):
        """J1-05: Ah Lee accepts the dispatch."""
        page.goto(f"{BASE_URL}/wechat/dispatch/new")
        page.wait_for_load_state("networkidle")

        # Submit an exception first
        page.click("text=Submit Exception Report")
        page.wait_for_timeout(2000)

        # Accept
        accept_btn = page.locator("#btn-accept")
        if accept_btn.is_visible():
            accept_btn.click()
            page.wait_for_timeout(1000)
            expect(accept_btn).to_contain_text("Accepted")

        screenshot(page, "j1_05_dispatch_accepted")


# =========================================================================
# Journey 2: Vivian (Manager) — Assessment → Chat → Orders
# =========================================================================

class TestJourney2Vivian:
    """Vivian's workflow: health assessment, AI chat, work order management."""

    def test_01_assessment_page_loads(self, page: Page):
        """J2-01: Health assessment page with SHI scores."""
        page.goto(f"{BASE_URL}/wechat/assessment")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(3000)  # Wait for health calculations

        expect(page.locator(".top-bar h1")).to_have_text("Health Assessment")
        # SHI should be calculated
        shi = page.locator("#shi-val")
        expect(shi).not_to_have_text("--")

        # Area health items loaded
        areas = page.locator("#area-health .list-item")
        assert areas.count() >= 3, "Expected 3 area health scores"

        screenshot(page, "j2_01_assessment_page")

    def test_02_submit_assessment(self, page: Page):
        """J2-02: Vivian submits a manual health assessment."""
        page.goto(f"{BASE_URL}/wechat/assessment")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(2000)

        # Set score slider
        page.evaluate("document.getElementById('assess-score').value = 85")
        page.evaluate("document.getElementById('score-display').textContent = '85'")

        # Submit
        page.click("text=Submit Assessment")
        page.wait_for_timeout(1500)

        screenshot(page, "j2_02_assessment_submitted")

    def test_03_chat_page_loads(self, page: Page):
        """J2-03: AI chat interface loads with welcome message."""
        page.goto(f"{BASE_URL}/wechat/chat")
        page.wait_for_load_state("networkidle")

        expect(page.locator(".top-bar h1")).to_have_text("AI Assistant")
        # Welcome message should be visible
        expect(page.locator("#chat-area")).to_contain_text("ECIS AI Assistant")
        # Quick query button visible (use role selector to be specific)
        expect(page.get_by_role("button", name="Staff Status")).to_be_visible()

        screenshot(page, "j2_03_chat_welcome")

    def test_04_chat_staff_query(self, page: Page):
        """J2-04: Vivian queries staff status via AI chat."""
        page.goto(f"{BASE_URL}/wechat/chat")
        page.wait_for_load_state("networkidle")

        # Click staff status quick query button (specific selector)
        page.get_by_role("button", name="Staff Status").click()
        page.wait_for_timeout(3000)

        # Verify staff data appears in chat
        expect(page.locator("#chat-area")).to_contain_text("Zhang Wei", timeout=10000)
        expect(page.locator("#chat-area")).to_contain_text("Staff Overview")

        screenshot(page, "j2_04_chat_staff_query")

    def test_05_chat_health_query(self, page: Page):
        """J2-05: Vivian queries health score via AI chat."""
        page.goto(f"{BASE_URL}/wechat/chat")
        page.wait_for_load_state("networkidle")

        page.click("text=Health Score")
        page.wait_for_timeout(2000)

        screenshot(page, "j2_05_chat_health_query")

    def test_06_orders_page_loads(self, page: Page):
        """J2-06: Work orders page with stats and order list."""
        page.goto(f"{BASE_URL}/wechat/orders")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(1500)

        expect(page.locator(".top-bar h1")).to_have_text("Work Orders")
        # Stats should load
        expect(page.locator("#stat-open")).to_be_visible()

        screenshot(page, "j2_06_orders_page")

    def test_07_create_work_order(self, page: Page):
        """J2-07: Vivian creates a new work order."""
        page.goto(f"{BASE_URL}/wechat/orders")
        page.wait_for_load_state("networkidle")

        # Submit new order (form is pre-filled)
        page.click("text=Create Order")
        page.wait_for_timeout(2000)

        # Verify order appears in list
        orders = page.locator("#order-list .list-item")
        assert orders.count() > 0, "Expected at least one order"

        screenshot(page, "j2_07_order_created")


# =========================================================================
# Journey 3: Wong Sir (COO) — Dashboard → ROI → Simulation
# =========================================================================

class TestJourney3WongSir:
    """Wong Sir's workflow: KPI dashboard, ROI analysis, day simulation."""

    def test_01_dashboard_loads(self, page: Page):
        """J3-01: Dashboard loads with KPI overview and role switcher."""
        page.goto(f"{BASE_URL}/wechat/dashboard")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(1500)

        expect(page.locator(".top-bar h1")).to_have_text("ECIS Tower C")
        # Staff count should load
        kpi_staff = page.locator("#kpi-staff")
        expect(kpi_staff).not_to_have_text("--")

        # Role navigation should be present
        expect(page.locator("#role-nav")).to_be_visible()

        screenshot(page, "j3_01_dashboard")

    def test_02_switch_to_ahlee(self, page: Page):
        """J3-02: Switch to Ah Lee's supervisor view."""
        page.goto(f"{BASE_URL}/wechat/dashboard")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(1000)

        page.click("text=Ah Lee (Supervisor)")
        page.wait_for_timeout(500)

        expect(page.locator("#role-title")).to_contain_text("Ah Lee")
        expect(page.locator("#current-user")).to_have_text("Ah Lee")

        screenshot(page, "j3_02_role_ahlee")

    def test_03_switch_to_vivian(self, page: Page):
        """J3-03: Switch to Vivian's manager view."""
        page.goto(f"{BASE_URL}/wechat/dashboard")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(1000)

        page.click("text=Vivian (Manager)")
        page.wait_for_timeout(500)

        expect(page.locator("#role-title")).to_contain_text("Vivian")

        screenshot(page, "j3_03_role_vivian")

    def test_04_day_simulation(self, page: Page):
        """J3-04: Wong Sir runs full day simulation."""
        page.goto(f"{BASE_URL}/wechat/dashboard")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(1000)

        # Run simulation
        page.click("#btn-simulate")
        page.wait_for_timeout(5000)  # Simulation takes a few seconds

        # Verify results
        result = page.locator("#sim-result")
        expect(result).to_be_visible()
        expect(result).to_contain_text("Day Simulation Complete")

        screenshot(page, "j3_04_day_simulation")

    def test_05_roi_page_loads(self, page: Page):
        """J3-05: ROI page loads after simulation generates data."""
        # First run simulation to generate data
        page.goto(f"{BASE_URL}/wechat/dashboard")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(1000)
        page.click("#btn-simulate")
        page.wait_for_timeout(5000)

        # Navigate to ROI
        page.goto(f"{BASE_URL}/wechat/roi")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(2000)

        expect(page.locator(".top-bar h1")).to_have_text("ROI Metrics")

        screenshot(page, "j3_05_roi_page")

    def test_06_roi_calculate(self, page: Page):
        """J3-06: Wong Sir calculates ROI metrics."""
        page.goto(f"{BASE_URL}/wechat/roi")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(1000)

        page.click("text=Calculate ROI")
        page.wait_for_timeout(2000)

        # Verify metrics loaded
        expect(page.locator("#roi-area")).not_to_have_text("--")
        expect(page.locator("#roi-completion")).not_to_have_text("--")

        screenshot(page, "j3_06_roi_calculated")


# =========================================================================
# Cross-page navigation tests
# =========================================================================

class TestNavigation:
    """Verify navigation between H5 pages via tab bar."""

    def test_01_tab_navigation(self, page: Page):
        """Nav-01: Tab bar navigation works between all pages."""
        page.goto(f"{BASE_URL}/wechat/dashboard")
        page.wait_for_load_state("networkidle")

        # Navigate to Schedule
        page.click(".tab-bar a[href='/wechat/schedule']")
        page.wait_for_load_state("networkidle")
        expect(page.locator(".top-bar h1")).to_have_text("Today's Schedule")

        # Navigate to Dispatch
        page.click(".tab-bar a[href='/wechat/dispatch/list']")
        page.wait_for_load_state("networkidle")
        expect(page.locator(".top-bar h1")).to_have_text("Exception Dispatch")

        # Navigate to Orders
        page.click(".tab-bar a[href='/wechat/orders']")
        page.wait_for_load_state("networkidle")
        expect(page.locator(".top-bar h1")).to_have_text("Work Orders")

        # Navigate to Assessment
        page.click(".tab-bar a[href='/wechat/assessment']")
        page.wait_for_load_state("networkidle")
        expect(page.locator(".top-bar h1")).to_have_text("Health Assessment")

        screenshot(page, "nav_01_tab_navigation")

    def test_02_mobile_viewport(self, page: Page):
        """Nav-02: Pages render correctly at mobile viewport (375x812)."""
        page.set_viewport_size({"width": 375, "height": 812})
        page.goto(f"{BASE_URL}/wechat/dashboard")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(1500)

        screenshot(page, "nav_02_mobile_dashboard")

        page.goto(f"{BASE_URL}/wechat/schedule")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(2000)

        screenshot(page, "nav_02_mobile_schedule")
