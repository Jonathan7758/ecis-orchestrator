"""
异常定义模块

职责：
- 定义编排器相关异常
- 提供统一的错误码
"""

from typing import Any, Dict, Optional


class OrchestratorError(Exception):
    """编排器基础异常"""

    def __init__(
        self,
        message: str,
        code: str = "UNKNOWN",
        details: Optional[Dict[str, Any]] = None,
    ):
        self.message = message
        self.code = code
        self.details = details or {}
        super().__init__(message)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "code": self.code,
            "message": self.message,
            "details": self.details,
        }


# ============ 工作流相关异常 ============


class WorkflowError(OrchestratorError):
    """工作流相关异常基类"""

    pass


class WorkflowNotFoundError(WorkflowError):
    """工作流不存在"""

    def __init__(self, workflow_id: str):
        super().__init__(
            f"Workflow not found: {workflow_id}",
            "WORKFLOW_NOT_FOUND",
            {"workflow_id": workflow_id},
        )


class WorkflowStartError(WorkflowError):
    """工作流启动失败"""

    def __init__(self, message: str, workflow_id: Optional[str] = None):
        super().__init__(
            message,
            "WORKFLOW_START_FAILED",
            {"workflow_id": workflow_id} if workflow_id else {},
        )


class WorkflowAlreadyExistsError(WorkflowError):
    """工作流已存在"""

    def __init__(self, workflow_id: str):
        super().__init__(
            f"Workflow already exists: {workflow_id}",
            "WORKFLOW_ALREADY_EXISTS",
            {"workflow_id": workflow_id},
        )


class WorkflowValidationError(WorkflowError):
    """工作流验证失败"""

    def __init__(self, message: str, errors: Optional[list] = None):
        super().__init__(
            message,
            "WORKFLOW_VALIDATION_FAILED",
            {"errors": errors or []},
        )


# ============ 任务相关异常 ============


class TaskError(OrchestratorError):
    """任务相关异常基类"""

    pass


class TaskDispatchError(TaskError):
    """任务分派失败"""

    def __init__(self, message: str, task_id: Optional[str] = None):
        super().__init__(
            message,
            "TASK_DISPATCH_FAILED",
            {"task_id": task_id} if task_id else {},
        )


class TaskTimeoutError(TaskError):
    """任务超时"""

    def __init__(self, task_id: str, timeout_seconds: int):
        super().__init__(
            f"Task timeout: {task_id}",
            "TASK_TIMEOUT",
            {"task_id": task_id, "timeout_seconds": timeout_seconds},
        )


class TaskCancelledError(TaskError):
    """任务被取消"""

    def __init__(self, task_id: str, reason: Optional[str] = None):
        super().__init__(
            f"Task cancelled: {task_id}",
            "TASK_CANCELLED",
            {"task_id": task_id, "reason": reason},
        )


# ============ Agent 相关异常 ============


class AgentError(OrchestratorError):
    """Agent 相关异常基类"""

    pass


class NoAvailableAgentError(AgentError):
    """没有可用 Agent"""

    def __init__(self, capability: str, agent_type: Optional[str] = None):
        super().__init__(
            f"No available agent for capability: {capability}",
            "NO_AVAILABLE_AGENT",
            {"capability": capability, "agent_type": agent_type},
        )


class AgentUnavailableError(AgentError):
    """Agent 不可用"""

    def __init__(self, agent_id: str, reason: Optional[str] = None):
        super().__init__(
            f"Agent unavailable: {agent_id}",
            "AGENT_UNAVAILABLE",
            {"agent_id": agent_id, "reason": reason},
        )


# ============ 审批相关异常 ============


class ApprovalError(OrchestratorError):
    """审批相关异常基类"""

    pass


class ApprovalNotFoundError(ApprovalError):
    """审批不存在"""

    def __init__(self, approval_id: str):
        super().__init__(
            f"Approval not found: {approval_id}",
            "APPROVAL_NOT_FOUND",
            {"approval_id": approval_id},
        )


class ApprovalTimeoutError(ApprovalError):
    """审批超时"""

    def __init__(self, approval_id: str, timeout_hours: int):
        super().__init__(
            f"Approval timeout: {approval_id}",
            "APPROVAL_TIMEOUT",
            {"approval_id": approval_id, "timeout_hours": timeout_hours},
        )


class ApprovalAlreadyProcessedError(ApprovalError):
    """审批已处理"""

    def __init__(self, approval_id: str, status: str):
        super().__init__(
            f"Approval already processed: {approval_id}",
            "APPROVAL_ALREADY_PROCESSED",
            {"approval_id": approval_id, "status": status},
        )


# ============ Federation 相关异常 ============


class FederationError(OrchestratorError):
    """Federation 相关异常基类"""

    pass


class FederationConnectionError(FederationError):
    """Federation 连接失败"""

    def __init__(self, gateway_url: str, reason: Optional[str] = None):
        super().__init__(
            f"Failed to connect to Federation gateway: {gateway_url}",
            "FEDERATION_CONNECTION_FAILED",
            {"gateway_url": gateway_url, "reason": reason},
        )
