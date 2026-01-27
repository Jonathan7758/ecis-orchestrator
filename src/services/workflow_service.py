"""
工作流管理服务

职责：
- 工作流定义管理
- 工作流实例管理
- 与 Temporal 交互
"""

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from temporalio.client import Client, WorkflowExecutionStatus

from src.core.config import get_config
from src.core.exceptions import WorkflowNotFoundError, WorkflowStartError
from src.workflows.approval import ApprovalWorkflow, ApprovalWorkflowInput
from src.workflows.cleaning import CleaningWorkflowInput, RobotCleaningWorkflow


@dataclass
class WorkflowInfo:
    """工作流信息"""

    workflow_id: str
    workflow_type: str
    status: str
    start_time: Optional[datetime]
    close_time: Optional[datetime]
    execution_time: Optional[str]


@dataclass
class WorkflowListResult:
    """工作流列表结果"""

    workflows: List[WorkflowInfo]
    total: int
    next_page_token: Optional[str]


class WorkflowService:
    """工作流管理服务"""

    def __init__(self, client: Client):
        self._client = client
        self._config = get_config()
        self._task_queue = self._config.temporal.task_queue

        # 工作流类型映射
        self._workflow_types = {
            "cleaning": RobotCleaningWorkflow,
            "approval": ApprovalWorkflow,
        }

    async def start_cleaning_workflow(
        self,
        floor_id: str,
        zone_id: Optional[str] = None,
        cleaning_mode: str = "standard",
        robot_id: Optional[str] = None,
        priority: int = 3,
        workflow_id: Optional[str] = None,
    ) -> str:
        """
        启动清洁工作流

        参数:
            floor_id: 楼层 ID
            zone_id: 区域 ID
            cleaning_mode: 清洁模式
            robot_id: 指定机器人 ID
            priority: 优先级
            workflow_id: 工作流 ID (可选)

        返回:
            工作流 ID
        """
        if workflow_id is None:
            workflow_id = f"cleaning-{uuid.uuid4().hex[:8]}"

        input_data = CleaningWorkflowInput(
            floor_id=floor_id,
            zone_id=zone_id,
            cleaning_mode=cleaning_mode,
            robot_id=robot_id,
            priority=priority,
        )

        try:
            handle = await self._client.start_workflow(
                RobotCleaningWorkflow.run,
                input_data,
                id=workflow_id,
                task_queue=self._task_queue,
            )
            return handle.id
        except Exception as e:
            raise WorkflowStartError(str(e), workflow_id)

    async def start_approval_workflow(
        self,
        request_type: str,
        title: str,
        description: str,
        data: Dict[str, Any],
        approvers: List[str],
        timeout_hours: int = 24,
        workflow_id: Optional[str] = None,
    ) -> str:
        """
        启动审批工作流

        参数:
            request_type: 请求类型
            title: 标题
            description: 描述
            data: 审批数据
            approvers: 审批人列表
            timeout_hours: 超时时间
            workflow_id: 工作流 ID (可选)

        返回:
            工作流 ID
        """
        if workflow_id is None:
            workflow_id = f"approval-{uuid.uuid4().hex[:8]}"

        input_data = ApprovalWorkflowInput(
            request_type=request_type,
            title=title,
            description=description,
            data=data,
            approvers=approvers,
            timeout_hours=timeout_hours,
        )

        try:
            handle = await self._client.start_workflow(
                ApprovalWorkflow.run,
                input_data,
                id=workflow_id,
                task_queue=self._task_queue,
            )
            return handle.id
        except Exception as e:
            raise WorkflowStartError(str(e), workflow_id)

    async def get_workflow_status(self, workflow_id: str) -> WorkflowInfo:
        """
        获取工作流状态

        参数:
            workflow_id: 工作流 ID

        返回:
            工作流信息
        """
        try:
            handle = self._client.get_workflow_handle(workflow_id)
            desc = await handle.describe()

            # 确定工作流类型
            workflow_type = "unknown"
            if workflow_id.startswith("cleaning-"):
                workflow_type = "cleaning"
            elif workflow_id.startswith("approval-"):
                workflow_type = "approval"

            return WorkflowInfo(
                workflow_id=workflow_id,
                workflow_type=workflow_type,
                status=desc.status.name,
                start_time=desc.start_time,
                close_time=desc.close_time,
                execution_time=desc.execution_time.isoformat() if desc.execution_time else None,
            )
        except Exception as e:
            raise WorkflowNotFoundError(workflow_id)

    async def query_workflow(self, workflow_id: str, query_name: str = "get_status") -> Dict[str, Any]:
        """
        查询工作流状态

        参数:
            workflow_id: 工作流 ID
            query_name: 查询名称

        返回:
            查询结果
        """
        try:
            handle = self._client.get_workflow_handle(workflow_id)
            result = await handle.query(query_name)
            return result
        except Exception as e:
            raise WorkflowNotFoundError(workflow_id)

    async def get_workflow_result(self, workflow_id: str) -> Any:
        """
        获取工作流结果

        参数:
            workflow_id: 工作流 ID

        返回:
            工作流结果
        """
        try:
            handle = self._client.get_workflow_handle(workflow_id)
            return await handle.result()
        except Exception as e:
            raise WorkflowNotFoundError(workflow_id)

    async def cancel_workflow(self, workflow_id: str) -> bool:
        """
        取消工作流

        参数:
            workflow_id: 工作流 ID

        返回:
            是否成功
        """
        try:
            handle = self._client.get_workflow_handle(workflow_id)
            await handle.cancel()
            return True
        except Exception as e:
            raise WorkflowNotFoundError(workflow_id)

    async def signal_workflow(
        self,
        workflow_id: str,
        signal_name: str,
        *args,
    ) -> bool:
        """
        发送信号给工作流

        参数:
            workflow_id: 工作流 ID
            signal_name: 信号名称
            args: 信号参数

        返回:
            是否成功
        """
        try:
            handle = self._client.get_workflow_handle(workflow_id)

            # 根据信号名称确定信号方法
            if signal_name == "approve":
                await handle.signal(ApprovalWorkflow.approve, args=list(args))
            elif signal_name == "reject":
                await handle.signal(ApprovalWorkflow.reject, args=list(args))
            elif signal_name == "cancel":
                await handle.signal(ApprovalWorkflow.cancel, args=list(args))
            else:
                # 通用信号发送
                await handle.signal(signal_name, *args)

            return True
        except Exception as e:
            raise WorkflowNotFoundError(workflow_id)

    async def list_workflows(
        self,
        workflow_type: Optional[str] = None,
        status: Optional[str] = None,
        page_size: int = 50,
        next_page_token: Optional[str] = None,
    ) -> WorkflowListResult:
        """
        列出工作流

        参数:
            workflow_type: 工作流类型过滤
            status: 状态过滤
            page_size: 页大小
            next_page_token: 分页令牌

        返回:
            工作流列表结果
        """
        # 构建查询
        query_parts = []

        if workflow_type:
            query_parts.append(f'WorkflowId STARTS_WITH "{workflow_type}-"')

        if status:
            query_parts.append(f'ExecutionStatus = "{status}"')

        query = " AND ".join(query_parts) if query_parts else None

        workflows = []
        async for workflow in self._client.list_workflows(query=query):
            workflow_id = workflow.id

            # 确定工作流类型
            wf_type = "unknown"
            if workflow_id.startswith("cleaning-"):
                wf_type = "cleaning"
            elif workflow_id.startswith("approval-"):
                wf_type = "approval"

            workflows.append(
                WorkflowInfo(
                    workflow_id=workflow_id,
                    workflow_type=wf_type,
                    status=workflow.status.name if workflow.status else "UNKNOWN",
                    start_time=workflow.start_time,
                    close_time=workflow.close_time,
                    execution_time=None,
                )
            )

            if len(workflows) >= page_size:
                break

        return WorkflowListResult(
            workflows=workflows,
            total=len(workflows),
            next_page_token=None,  # Temporal SDK 处理分页方式不同
        )


# 服务单例
_workflow_service: Optional[WorkflowService] = None


async def get_workflow_service() -> WorkflowService:
    """获取工作流服务单例"""
    global _workflow_service
    if _workflow_service is None:
        config = get_config()
        client = await Client.connect(config.temporal.address)
        _workflow_service = WorkflowService(client)
    return _workflow_service
