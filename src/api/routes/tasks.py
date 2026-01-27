"""
任务 API 路由
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.services.task_dispatcher import (
    TaskDispatcher,
    AgentInfo,
    get_task_dispatcher,
)

router = APIRouter(prefix="/tasks", tags=["tasks"])


class AgentRegisterRequest(BaseModel):
    """Agent 注册请求"""
    agent_id: str
    agent_type: str
    capabilities: List[str]
    max_load: int = 5
    metadata: Optional[Dict[str, Any]] = None


class DispatchTaskRequest(BaseModel):
    """任务分派请求"""
    capability: str
    parameters: Dict[str, Any]
    agent_type: Optional[str] = None
    prefer_agent_id: Optional[str] = None
    priority: int = 3


class TaskResponse(BaseModel):
    """任务响应"""
    task_id: str
    agent_id: str
    status: str


@router.get("/agents")
async def list_agents() -> List[Dict[str, Any]]:
    """
    列出所有 Agent
    """
    dispatcher = get_task_dispatcher()
    return [
        {
            "agent_id": agent.agent_id,
            "agent_type": agent.agent_type,
            "capabilities": agent.capabilities,
            "status": agent.status,
            "current_load": agent.current_load,
            "max_load": agent.max_load,
        }
        for agent in dispatcher._agents.values()
    ]


@router.post("/agents")
async def register_agent(request: AgentRegisterRequest) -> Dict[str, str]:
    """
    注册 Agent
    """
    dispatcher = get_task_dispatcher()
    
    agent = AgentInfo(
        agent_id=request.agent_id,
        agent_type=request.agent_type,
        capabilities=request.capabilities,
        status="ready",
        max_load=request.max_load,
        metadata=request.metadata or {},
    )
    
    dispatcher.register_agent(agent)
    return {"status": "registered", "agent_id": request.agent_id}


@router.delete("/agents/{agent_id}")
async def unregister_agent(agent_id: str) -> Dict[str, str]:
    """
    注销 Agent
    """
    dispatcher = get_task_dispatcher()
    dispatcher.unregister_agent(agent_id)
    return {"status": "unregistered", "agent_id": agent_id}


@router.put("/agents/{agent_id}/status")
async def update_agent_status(agent_id: str, status: str) -> Dict[str, str]:
    """
    更新 Agent 状态
    """
    dispatcher = get_task_dispatcher()
    
    if agent_id not in dispatcher._agents:
        raise HTTPException(status_code=404, detail=f"Agent not found: {agent_id}")
    
    dispatcher.update_agent_status(agent_id, status)
    return {"status": "updated", "agent_id": agent_id, "new_status": status}


@router.get("/agents/available")
async def find_available_agents(
    capability: str,
    agent_type: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    查找可用 Agent
    """
    dispatcher = get_task_dispatcher()
    available = dispatcher.find_available_agents(capability, agent_type)
    
    return [
        {
            "agent_id": agent.agent_id,
            "agent_type": agent.agent_type,
            "capabilities": agent.capabilities,
            "current_load": agent.current_load,
            "max_load": agent.max_load,
        }
        for agent in available
    ]


@router.post("/dispatch", response_model=TaskResponse)
async def dispatch_task(request: DispatchTaskRequest) -> TaskResponse:
    """
    分派任务
    """
    dispatcher = get_task_dispatcher()
    
    try:
        assignment = await dispatcher.dispatch_task(
            capability=request.capability,
            parameters=request.parameters,
            agent_type=request.agent_type,
            prefer_agent_id=request.prefer_agent_id,
            priority=request.priority,
        )
        return TaskResponse(
            task_id=assignment.task_id,
            agent_id=assignment.agent_id,
            status=assignment.status,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{task_id}")
async def get_task(task_id: str) -> Dict[str, Any]:
    """
    获取任务信息
    """
    dispatcher = get_task_dispatcher()
    assignment = dispatcher.get_assignment(task_id)
    
    if not assignment:
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")
    
    return {
        "task_id": assignment.task_id,
        "agent_id": assignment.agent_id,
        "agent_type": assignment.agent_type,
        "capability": assignment.capability,
        "status": assignment.status,
        "assigned_at": assignment.assigned_at.isoformat(),
    }


@router.post("/{task_id}/complete")
async def complete_task(task_id: str, success: bool = True) -> Dict[str, str]:
    """
    完成任务
    """
    dispatcher = get_task_dispatcher()
    
    if not dispatcher.get_assignment(task_id):
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")
    
    dispatcher.complete_task(task_id, success)
    return {
        "status": "completed" if success else "failed",
        "task_id": task_id,
    }


@router.get("/stats/overview")
async def get_stats() -> Dict[str, Any]:
    """
    获取统计信息
    """
    dispatcher = get_task_dispatcher()
    return dispatcher.get_stats()
