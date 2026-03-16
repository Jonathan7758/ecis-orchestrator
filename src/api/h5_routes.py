"""
ECIS V8 H5 Frontend Routes — WeChat Work embedded pages.

Provides 6 H5 pages for the three user journeys:
  - Ah Lee (Supervisor): schedule, dispatch
  - Vivian (Manager): assessment, orders, chat
  - Wong Sir (COO): dashboard, roi

All pages are Jinja2 templates served via FastAPI and communicate
with the V8 backend API endpoints via fetch().
"""

from __future__ import annotations

import os
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

# Template directory next to this file
_TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "templates")
templates = Jinja2Templates(directory=_TEMPLATE_DIR)

router = APIRouter(prefix="/wechat", tags=["H5 Pages"])


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Main dashboard — Wong Sir (COO) entry point."""
    return templates.TemplateResponse("dashboard.html", {
        "request": request, "title": "ECIS Tower C Dashboard",
    })


@router.get("/schedule", response_class=HTMLResponse)
async def schedule(request: Request):
    """Schedule view — Ah Lee (Supervisor) daily schedule."""
    return templates.TemplateResponse("schedule.html", {
        "request": request, "title": "Today's Schedule",
    })


@router.get("/dispatch/{path:path}", response_class=HTMLResponse)
async def dispatch(request: Request, path: str = ""):
    """Exception dispatch — Ah Lee handles exceptions."""
    return templates.TemplateResponse("dispatch.html", {
        "request": request, "title": "Exception Dispatch",
    })


@router.get("/assessment", response_class=HTMLResponse)
async def assessment(request: Request):
    """Health assessment — Vivian submits and reviews SHI."""
    return templates.TemplateResponse("assessment.html", {
        "request": request, "title": "Health Assessment",
    })


@router.get("/orders", response_class=HTMLResponse)
async def orders(request: Request):
    """Work orders — Vivian monitors order lifecycle."""
    return templates.TemplateResponse("orders.html", {
        "request": request, "title": "Work Orders",
    })


@router.get("/chat", response_class=HTMLResponse)
async def chat(request: Request):
    """AI conversation — Vivian's intelligent assistant."""
    return templates.TemplateResponse("chat.html", {
        "request": request, "title": "AI Assistant",
    })


@router.get("/roi", response_class=HTMLResponse)
async def roi(request: Request):
    """ROI metrics — Wong Sir views cost analysis."""
    return templates.TemplateResponse("roi.html", {
        "request": request, "title": "ROI Metrics",
    })
