"""
审批 API 路由
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.api.main import get_temporal_client

router = APIRouter(prefix="/approvals", tags=["approvals"])


# ============ 请求/响应模型 ============


class ApproveRequest(BaseModel):
    """审批通过请求"""

    approver: str
    reason: str = ""
    form_data: Optional[Dict[str, Any]] = None


class RejectRequest(BaseModel):
    """审批拒绝请求"""

    approver: str
    reason: str
    form_data: Optional[Dict[str, Any]] = None


class ApprovalResponse(BaseModel):
    """审批响应"""

    workflow_id: str
    action: str
    success: bool


class ApprovalStatusResponse(BaseModel):
    """审批状态响应"""

    workflow_id: str
    status: str
    approval_id: Optional[str]
    decision: Optional[str]
    decided_by: Optional[str]
    reason: Optional[str]


# ============ 路由 ============


@router.get("/{workflow_id}", response_model=ApprovalStatusResponse)
async def get_approval_status(workflow_id: str):
    """
    获取审批状态

    查询审批工作流的当前状态
    """
    client = get_temporal_client()

    try:
        handle = client.get_workflow_handle(workflow_id)

        # 查询状态
        status = await handle.query("get_status")

        return ApprovalStatusResponse(
            workflow_id=workflow_id,
            status=status.get("status", "unknown"),
            approval_id=status.get("approval_id"),
            decision=status.get("decision"),
            decided_by=status.get("decided_by"),
            reason=status.get("reason"),
        )

    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{workflow_id}/approve", response_model=ApprovalResponse)
async def approve(workflow_id: str, request: ApproveRequest):
    """
    审批通过

    向审批工作流发送 approve 信号
    """
    client = get_temporal_client()

    try:
        handle = client.get_workflow_handle(workflow_id)

        # 发送 approve 信号
        await handle.signal(
            "approve",
            request.approver,
            request.reason,
            request.form_data,
        )

        return ApprovalResponse(
            workflow_id=workflow_id,
            action="approve",
            success=True,
        )

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{workflow_id}/reject", response_model=ApprovalResponse)
async def reject(workflow_id: str, request: RejectRequest):
    """
    审批拒绝

    向审批工作流发送 reject 信号
    """
    client = get_temporal_client()

    try:
        handle = client.get_workflow_handle(workflow_id)

        # 发送 reject 信号
        await handle.signal(
            "reject",
            request.approver,
            request.reason,
            request.form_data,
        )

        return ApprovalResponse(
            workflow_id=workflow_id,
            action="reject",
            success=True,
        )

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{workflow_id}/cancel", response_model=ApprovalResponse)
async def cancel_approval(workflow_id: str, reason: str = ""):
    """
    取消审批

    向审批工作流发送 cancel 信号
    """
    client = get_temporal_client()

    try:
        handle = client.get_workflow_handle(workflow_id)

        # 发送 cancel 信号
        await handle.signal("cancel", reason)

        return ApprovalResponse(
            workflow_id=workflow_id,
            action="cancel",
            success=True,
        )

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
