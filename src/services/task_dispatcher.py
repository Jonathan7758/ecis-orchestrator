"""
任务分派服务

职责：
- 任务分派给合适的 Agent
- Agent 能力匹配
- 负载均衡
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid

from src.core.exceptions import NoAvailableAgentError, TaskDispatchError


@dataclass
class AgentInfo:
    """Agent 信息"""

    agent_id: str
    agent_type: str
    capabilities: List[str]
    status: str  # ready, busy, offline
    current_load: int = 0
    max_load: int = 5
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TaskAssignment:
    """任务分配"""

    task_id: str
    agent_id: str
    agent_type: str
    capability: str
    assigned_at: datetime
    status: str  # assigned, accepted, rejected, completed, failed


class TaskDispatcher:
    """任务分派服务"""

    def __init__(self):
        # 内存中的 Agent 注册表（实际应该从 Federation 获取）
        self._agents: Dict[str, AgentInfo] = {}
        self._assignments: Dict[str, TaskAssignment] = {}

    def register_agent(self, agent: AgentInfo) -> None:
        """
        注册 Agent

        参数:
            agent: Agent 信息
        """
        self._agents[agent.agent_id] = agent

    def unregister_agent(self, agent_id: str) -> None:
        """
        注销 Agent

        参数:
            agent_id: Agent ID
        """
        if agent_id in self._agents:
            del self._agents[agent_id]

    def update_agent_status(self, agent_id: str, status: str) -> None:
        """
        更新 Agent 状态

        参数:
            agent_id: Agent ID
            status: 新状态
        """
        if agent_id in self._agents:
            self._agents[agent_id].status = status

    def find_available_agents(
        self,
        capability: str,
        agent_type: Optional[str] = None,
    ) -> List[AgentInfo]:
        """
        查找可用的 Agent

        参数:
            capability: 所需能力
            agent_type: Agent 类型过滤

        返回:
            可用 Agent 列表
        """
        available = []

        for agent in self._agents.values():
            # 检查状态
            if agent.status != "ready":
                continue

            # 检查负载
            if agent.current_load >= agent.max_load:
                continue

            # 检查类型
            if agent_type and agent.agent_type != agent_type:
                continue

            # 检查能力
            if capability not in agent.capabilities:
                # 支持通配符匹配
                capability_parts = capability.split(".")
                matched = False
                for cap in agent.capabilities:
                    cap_parts = cap.split(".")
                    if len(cap_parts) <= len(capability_parts):
                        if all(
                            cp == "*" or cp == capability_parts[i]
                            for i, cp in enumerate(cap_parts)
                        ):
                            matched = True
                            break
                if not matched:
                    continue

            available.append(agent)

        return available

    def select_best_agent(
        self,
        capability: str,
        agent_type: Optional[str] = None,
        prefer_agent_id: Optional[str] = None,
    ) -> AgentInfo:
        """
        选择最佳 Agent

        参数:
            capability: 所需能力
            agent_type: Agent 类型过滤
            prefer_agent_id: 优先选择的 Agent ID

        返回:
            最佳 Agent

        异常:
            NoAvailableAgentError: 没有可用 Agent
        """
        available = self.find_available_agents(capability, agent_type)

        if not available:
            raise NoAvailableAgentError(capability, agent_type)

        # 如果有优先选择的 Agent
        if prefer_agent_id:
            for agent in available:
                if agent.agent_id == prefer_agent_id:
                    return agent

        # 按负载排序，选择负载最低的
        available.sort(key=lambda a: a.current_load)
        return available[0]

    async def dispatch_task(
        self,
        capability: str,
        parameters: Dict[str, Any],
        agent_type: Optional[str] = None,
        prefer_agent_id: Optional[str] = None,
        priority: int = 3,
    ) -> TaskAssignment:
        """
        分派任务

        参数:
            capability: 所需能力
            parameters: 任务参数
            agent_type: Agent 类型
            prefer_agent_id: 优先 Agent ID
            priority: 优先级

        返回:
            任务分配信息
        """
        # 选择 Agent
        agent = self.select_best_agent(capability, agent_type, prefer_agent_id)

        # 创建任务分配
        task_id = f"task-{uuid.uuid4().hex[:8]}"
        assignment = TaskAssignment(
            task_id=task_id,
            agent_id=agent.agent_id,
            agent_type=agent.agent_type,
            capability=capability,
            assigned_at=datetime.now(timezone.utc),
            status="assigned",
        )

        # 更新 Agent 负载
        agent.current_load += 1

        # 记录分配
        self._assignments[task_id] = assignment

        # TODO: 通过 Federation 发送任务给 Agent
        # await self._federation_client.send_task(agent.agent_id, task_id, parameters)

        return assignment

    def complete_task(self, task_id: str, success: bool = True) -> None:
        """
        完成任务

        参数:
            task_id: 任务 ID
            success: 是否成功
        """
        if task_id not in self._assignments:
            return

        assignment = self._assignments[task_id]
        assignment.status = "completed" if success else "failed"

        # 更新 Agent 负载
        if assignment.agent_id in self._agents:
            self._agents[assignment.agent_id].current_load -= 1

    def get_assignment(self, task_id: str) -> Optional[TaskAssignment]:
        """
        获取任务分配

        参数:
            task_id: 任务 ID

        返回:
            任务分配信息
        """
        return self._assignments.get(task_id)

    def get_agent_tasks(self, agent_id: str) -> List[TaskAssignment]:
        """
        获取 Agent 的任务

        参数:
            agent_id: Agent ID

        返回:
            任务列表
        """
        return [
            a for a in self._assignments.values()
            if a.agent_id == agent_id and a.status in ["assigned", "accepted"]
        ]

    def get_stats(self) -> Dict[str, Any]:
        """
        获取统计信息

        返回:
            统计数据
        """
        total_agents = len(self._agents)
        ready_agents = sum(1 for a in self._agents.values() if a.status == "ready")
        busy_agents = sum(1 for a in self._agents.values() if a.status == "busy")
        offline_agents = sum(1 for a in self._agents.values() if a.status == "offline")

        total_tasks = len(self._assignments)
        pending_tasks = sum(1 for a in self._assignments.values() if a.status == "assigned")
        completed_tasks = sum(1 for a in self._assignments.values() if a.status == "completed")
        failed_tasks = sum(1 for a in self._assignments.values() if a.status == "failed")

        return {
            "agents": {
                "total": total_agents,
                "ready": ready_agents,
                "busy": busy_agents,
                "offline": offline_agents,
            },
            "tasks": {
                "total": total_tasks,
                "pending": pending_tasks,
                "completed": completed_tasks,
                "failed": failed_tasks,
            },
        }


# 服务单例
_task_dispatcher: Optional[TaskDispatcher] = None


def get_task_dispatcher() -> TaskDispatcher:
    """获取任务分派服务单例"""
    global _task_dispatcher
    if _task_dispatcher is None:
        _task_dispatcher = TaskDispatcher()

        # 注册一些模拟的 Agent（实际应该从 Federation 获取）
        _task_dispatcher.register_agent(
            AgentInfo(
                agent_id="robot-001",
                agent_type="robot",
                capabilities=[
                    "cleaning.floor.standard",
                    "cleaning.floor.deep",
                    "cleaning.floor.quick",
                    "delivery.*",
                ],
                status="ready",
            )
        )
        _task_dispatcher.register_agent(
            AgentInfo(
                agent_id="robot-002",
                agent_type="robot",
                capabilities=[
                    "cleaning.floor.standard",
                    "patrol.*",
                ],
                status="ready",
            )
        )
        _task_dispatcher.register_agent(
            AgentInfo(
                agent_id="facility-001",
                agent_type="facility",
                capabilities=[
                    "elevator.call",
                    "door.open",
                    "door.close",
                    "access.grant",
                ],
                status="ready",
            )
        )

    return _task_dispatcher
