"""
配送 API 路由
"""

import uuid
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from temporalio.client import Client

from src.core.config import get_config
from src.workflows.delivery import DeliveryWorkflow, DeliveryWorkflowInput

router = APIRouter(prefix="/delivery", tags=["delivery"])


class StartDeliveryRequest(BaseModel):
    """启动配送请求"""
    pickup_location: str
    delivery_location: str
    item_description: str
    recipient_id: str
    sender_id: Optional[str] = None
    robot_id: Optional[str] = None
    priority: int = 3
    require_signature: bool = False
    notes: Optional[str] = None


class DeliveryResponse(BaseModel):
    """配送响应"""
    workflow_id: str
    status: str
    message: str


@router.post("", response_model=DeliveryResponse)
async def start_delivery(request: StartDeliveryRequest) -> DeliveryResponse:
    """
    启动配送工作流
    """
    config = get_config()
    client = await Client.connect(config.temporal.address)

    workflow_id = f"delivery-{uuid.uuid4().hex[:8]}"

    input_data = DeliveryWorkflowInput(
        pickup_location=request.pickup_location,
        delivery_location=request.delivery_location,
        item_description=request.item_description,
        recipient_id=request.recipient_id,
        sender_id=request.sender_id,
        robot_id=request.robot_id,
        priority=request.priority,
        require_signature=request.require_signature,
        notes=request.notes,
    )

    try:
        handle = await client.start_workflow(
            DeliveryWorkflow.run,
            input_data,
            id=workflow_id,
            task_queue=config.temporal.task_queue,
        )
        return DeliveryResponse(
            workflow_id=handle.id,
            status="started",
            message="Delivery workflow started",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{workflow_id}")
async def get_delivery_status(workflow_id: str) -> Dict[str, Any]:
    """
    获取配送状态
    """
    config = get_config()
    client = await Client.connect(config.temporal.address)

    try:
        handle = client.get_workflow_handle(workflow_id)
        status = await handle.query("get_status")
        return status
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Delivery not found: {workflow_id}")


@router.post("/{workflow_id}/confirm-pickup")
async def confirm_pickup(workflow_id: str) -> Dict[str, str]:
    """
    确认取货
    """
    config = get_config()
    client = await Client.connect(config.temporal.address)

    try:
        handle = client.get_workflow_handle(workflow_id)
        await handle.signal(DeliveryWorkflow.confirm_pickup)
        return {"status": "confirmed", "message": "Pickup confirmed"}
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Delivery not found: {workflow_id}")


@router.post("/{workflow_id}/confirm-delivery")
async def confirm_delivery(workflow_id: str, signature: Optional[str] = None) -> Dict[str, str]:
    """
    确认送达
    """
    config = get_config()
    client = await Client.connect(config.temporal.address)

    try:
        handle = client.get_workflow_handle(workflow_id)
        await handle.signal(DeliveryWorkflow.confirm_delivery, args=[signature])
        return {"status": "confirmed", "message": "Delivery confirmed"}
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Delivery not found: {workflow_id}")


@router.post("/{workflow_id}/cancel")
async def cancel_delivery(workflow_id: str, reason: str = "User cancelled") -> Dict[str, str]:
    """
    取消配送
    """
    config = get_config()
    client = await Client.connect(config.temporal.address)

    try:
        handle = client.get_workflow_handle(workflow_id)
        await handle.signal(DeliveryWorkflow.cancel_delivery, args=[reason])
        return {"status": "cancelled", "message": f"Delivery cancelled: {reason}"}
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Delivery not found: {workflow_id}")
