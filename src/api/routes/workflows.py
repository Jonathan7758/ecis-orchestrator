"""
工作流 API 路由
"""

import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.api.main import get_temporal_client
from src.core.config import get_config
from src.workflows.cleaning import CleaningWorkflowInput, RobotCleaningWorkflow
from src.workflows.approval import ApprovalWorkflow, ApprovalWorkflowInput

router = APIRouter(prefix="/workflows", tags=["workflows"])


# ============ 请求/响应模型 ============


class StartCleaningRequest(BaseModel):
    """启动清洁工作流请求"""

    floor_id: str
    zone_id: Optional[str] = None
    cleaning_mode: str = "standard"
    robot_id: Optional[str] = None
    priority: int = 3


class StartApprovalRequest(BaseModel):
    """启动审批工作流请求"""

    request_type: str
    title: str
    description: str
    data: Dict[str, Any]
    approvers: List[str]
    timeout_hours: int = 24


class WorkflowResponse(BaseModel):
    """工作流响应"""

    workflow_id: str
    workflow_type: str
    status: str


class WorkflowStatusResponse(BaseModel):
    """工作流状态响应"""

    workflow_id: str
    status: str
    details: Dict[str, Any]


# ============ 路由 ============


@router.post("/cleaning/start", response_model=WorkflowResponse)
async def start_cleaning_workflow(request: StartCleaningRequest):
    """
    启动清洁工作流

    启动一个机器人清洁任务，包括：
    - 检查楼层状态
    - 查找可用机器人
    - 分配清洁任务
    - 等待完成
    """
    client = get_temporal_client()
    config = get_config()

    workflow_id = f"cleaning-{uuid.uuid4().hex[:8]}"

    try:
        input_data = CleaningWorkflowInput(
            floor_id=request.floor_id,
            zone_id=request.zone_id,
            cleaning_mode=request.cleaning_mode,
            robot_id=request.robot_id,
            priority=request.priority,
        )

        handle = await client.start_workflow(
            RobotCleaningWorkflow.run,
            input_data,
            id=workflow_id,
            task_queue=config.temporal.task_queue,
        )

        return WorkflowResponse(
            workflow_id=handle.id,
            workflow_type="cleaning",
            status="started",
        )

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/approval/start", response_model=WorkflowResponse)
async def start_approval_workflow(request: StartApprovalRequest):
    """
    启动审批工作流

    创建一个需要人工审批的流程
    """
    client = get_temporal_client()
    config = get_config()

    workflow_id = f"approval-{uuid.uuid4().hex[:8]}"

    try:
        input_data = ApprovalWorkflowInput(
            request_type=request.request_type,
            title=request.title,
            description=request.description,
            data=request.data,
            approvers=request.approvers,
            timeout_hours=request.timeout_hours,
        )

        handle = await client.start_workflow(
            ApprovalWorkflow.run,
            input_data,
            id=workflow_id,
            task_queue=config.temporal.task_queue,
        )

        return WorkflowResponse(
            workflow_id=handle.id,
            workflow_type="approval",
            status="started",
        )

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{workflow_id}", response_model=WorkflowStatusResponse)
async def get_workflow_status(workflow_id: str):
    """
    获取工作流状态

    通过 Temporal Query 获取工作流的当前状态
    """
    client = get_temporal_client()

    try:
        handle = client.get_workflow_handle(workflow_id)
        desc = await handle.describe()

        # 尝试查询状态
        try:
            status_details = await handle.query("get_status")
        except Exception:
            status_details = {}

        return WorkflowStatusResponse(
            workflow_id=workflow_id,
            status=desc.status.name,
            details=status_details,
        )

    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{workflow_id}/result")
async def get_workflow_result(workflow_id: str):
    """
    获取工作流结果

    等待工作流完成并返回结果
    """
    client = get_temporal_client()

    try:
        handle = client.get_workflow_handle(workflow_id)
        result = await handle.result()
        return {"workflow_id": workflow_id, "result": result}

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{workflow_id}/cancel")
async def cancel_workflow(workflow_id: str):
    """
    取消工作流
    """
    client = get_temporal_client()

    try:
        handle = client.get_workflow_handle(workflow_id)
        await handle.cancel()
        return {"workflow_id": workflow_id, "cancelled": True}

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{workflow_id}/signal/{signal_name}")
async def signal_workflow(
    workflow_id: str,
    signal_name: str,
    args: Optional[List[Any]] = None,
):
    """
    向工作流发送信号

    用于审批工作流的 approve/reject 等操作
    """
    client = get_temporal_client()

    try:
        handle = client.get_workflow_handle(workflow_id)
        await handle.signal(signal_name, *(args or []))
        return {"workflow_id": workflow_id, "signal_sent": signal_name}

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
