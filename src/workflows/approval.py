"""
审批工作流

处理需要人工审批的场景，支持信号驱动的审批响应
"""

import asyncio
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Dict, List, Optional

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from src.activities.notification import (
        cancel_approval_request,
        create_approval_request,
        send_approval_reminder,
        send_notification,
    )


@dataclass
class ApprovalWorkflowInput:
    """审批工作流输入"""

    request_type: str
    title: str
    description: str
    data: Dict[str, Any]
    approvers: List[str]
    timeout_hours: int = 24
    reminder_hours: Optional[List[int]] = None  # 提醒时间点（小时）


@dataclass
class ApprovalWorkflowResult:
    """审批工作流结果"""

    approval_id: str
    status: str  # approved, rejected, timeout, cancelled
    decided_by: Optional[str]
    reason: Optional[str]
    form_data: Optional[Dict[str, Any]]


@workflow.defn
class ApprovalWorkflow:
    """
    人工审批工作流

    支持:
    - 等待人工审批（通过信号）
    - 审批超时自动处理
    - 审批提醒
    - 审批升级
    """

    def __init__(self):
        self._status = "pending"
        self._approval_id: Optional[str] = None
        self._decision: Optional[str] = None
        self._decided_by: Optional[str] = None
        self._reason: Optional[str] = None
        self._form_data: Optional[Dict[str, Any]] = None

    @workflow.signal
    async def approve(
        self,
        approver: str,
        reason: str = "",
        form_data: Optional[Dict[str, Any]] = None,
    ):
        """
        审批通过信号

        参数:
            approver: 审批人
            reason: 审批原因
            form_data: 表单数据
        """
        if self._decision is not None:
            workflow.logger.warning(f"Approval already decided: {self._decision}")
            return

        self._decision = "approved"
        self._decided_by = approver
        self._reason = reason
        self._form_data = form_data
        workflow.logger.info(f"Approved by {approver}")

    @workflow.signal
    async def reject(
        self,
        approver: str,
        reason: str,
        form_data: Optional[Dict[str, Any]] = None,
    ):
        """
        审批拒绝信号

        参数:
            approver: 审批人
            reason: 拒绝原因
            form_data: 表单数据
        """
        if self._decision is not None:
            workflow.logger.warning(f"Approval already decided: {self._decision}")
            return

        self._decision = "rejected"
        self._decided_by = approver
        self._reason = reason
        self._form_data = form_data
        workflow.logger.info(f"Rejected by {approver}: {reason}")

    @workflow.signal
    async def cancel(self, reason: str = ""):
        """取消审批信号"""
        if self._decision is not None:
            workflow.logger.warning(f"Approval already decided: {self._decision}")
            return

        self._decision = "cancelled"
        self._reason = reason
        workflow.logger.info(f"Cancelled: {reason}")

    @workflow.query
    def get_status(self) -> Dict[str, Any]:
        """查询审批状态"""
        return {
            "status": self._status,
            "approval_id": self._approval_id,
            "decision": self._decision,
            "decided_by": self._decided_by,
            "reason": self._reason,
        }

    @workflow.run
    async def run(self, input: ApprovalWorkflowInput) -> ApprovalWorkflowResult:
        """执行审批工作流"""
        self._status = "creating_request"
        workflow.logger.info(f"Starting approval workflow: {input.title}")

        # 1. 创建审批请求
        approval_result = await workflow.execute_activity(
            create_approval_request,
            args=[
                input.request_type,
                input.title,
                input.description,
                input.data,
                input.approvers,
                input.timeout_hours * 60,  # 转换为分钟
            ],
            start_to_close_timeout=timedelta(seconds=60),
        )

        self._approval_id = approval_result["approval_id"]
        workflow.logger.info(f"Created approval request: {self._approval_id}")

        # 2. 通知审批人
        self._status = "notifying"
        await workflow.execute_activity(
            send_notification,
            args=[
                f"新的审批请求: {input.title}",
                "app",
                input.approvers,
                {
                    "approval_id": self._approval_id,
                    "type": input.request_type,
                    "data": input.data,
                },
            ],
            start_to_close_timeout=timedelta(seconds=30),
        )

        # 3. 等待审批（带超时和提醒）
        self._status = "waiting_approval"
        timeout_duration = timedelta(hours=input.timeout_hours)
        reminder_hours = input.reminder_hours or [1, 4, 12]  # 默认提醒时间

        # 设置提醒定时器
        reminder_tasks = []
        for hours in reminder_hours:
            if hours < input.timeout_hours:
                reminder_tasks.append(
                    self._schedule_reminder(
                        hours,
                        input.approvers,
                        f"审批提醒: {input.title} 等待您的处理",
                    )
                )

        # 等待审批决定或超时
        try:
            await workflow.wait_condition(
                lambda: self._decision is not None,
                timeout=timeout_duration,
            )
        except asyncio.TimeoutError:
            # 超时处理
            self._decision = "timeout"
            self._reason = f"Approval timed out after {input.timeout_hours} hours"
            workflow.logger.warning(f"Approval timeout: {self._approval_id}")

        # 4. 处理结果
        self._status = self._decision or "timeout"

        # 发送结果通知
        status_text = {
            "approved": "已通过",
            "rejected": "已拒绝",
            "timeout": "已超时",
            "cancelled": "已取消",
        }.get(self._decision, "未知")

        await workflow.execute_activity(
            send_notification,
            args=[
                f"审批{status_text}: {input.title}",
                "ops",
                None,
                {
                    "approval_id": self._approval_id,
                    "status": self._decision,
                    "decided_by": self._decided_by,
                    "reason": self._reason,
                },
            ],
            start_to_close_timeout=timedelta(seconds=30),
        )

        return ApprovalWorkflowResult(
            approval_id=self._approval_id,
            status=self._decision,
            decided_by=self._decided_by,
            reason=self._reason,
            form_data=self._form_data,
        )

    async def _schedule_reminder(
        self,
        hours: int,
        approvers: List[str],
        message: str,
    ):
        """调度提醒"""
        await asyncio.sleep(hours * 3600)
        if self._decision is None:
            await workflow.execute_activity(
                send_approval_reminder,
                args=[self._approval_id, approvers, message],
                start_to_close_timeout=timedelta(seconds=30),
            )


@workflow.defn
class MultiStageApprovalWorkflow:
    """
    多级审批工作流

    支持多个审批阶段，每个阶段有不同的审批人
    """

    def __init__(self):
        self._status = "pending"
        self._current_stage = 0
        self._stage_results: List[Dict[str, Any]] = []
        self._approval_ids: List[str] = []

    @workflow.signal
    async def stage_approve(
        self,
        stage: int,
        approver: str,
        reason: str = "",
    ):
        """某一阶段审批通过"""
        if stage == self._current_stage and len(self._stage_results) == stage:
            self._stage_results.append({
                "stage": stage,
                "decision": "approved",
                "approver": approver,
                "reason": reason,
            })

    @workflow.signal
    async def stage_reject(
        self,
        stage: int,
        approver: str,
        reason: str,
    ):
        """某一阶段审批拒绝"""
        if stage == self._current_stage and len(self._stage_results) == stage:
            self._stage_results.append({
                "stage": stage,
                "decision": "rejected",
                "approver": approver,
                "reason": reason,
            })

    @workflow.query
    def get_status(self) -> Dict[str, Any]:
        """查询状态"""
        return {
            "status": self._status,
            "current_stage": self._current_stage,
            "total_stages": len(self._approval_ids),
            "stage_results": self._stage_results,
        }

    @workflow.run
    async def run(
        self,
        title: str,
        description: str,
        data: Dict[str, Any],
        stages: List[Dict[str, Any]],  # [{"approvers": [...], "timeout_hours": 24}, ...]
    ) -> Dict[str, Any]:
        """
        执行多级审批

        参数:
            title: 审批标题
            description: 描述
            data: 审批数据
            stages: 审批阶段配置
        """
        self._status = "running"
        total_stages = len(stages)

        for stage_idx, stage_config in enumerate(stages):
            self._current_stage = stage_idx
            workflow.logger.info(f"Starting stage {stage_idx + 1}/{total_stages}")

            # 创建该阶段的审批请求
            approval_result = await workflow.execute_activity(
                create_approval_request,
                args=[
                    f"multi-stage-{stage_idx}",
                    f"{title} (第{stage_idx + 1}级)",
                    description,
                    data,
                    stage_config["approvers"],
                    stage_config.get("timeout_hours", 24) * 60,
                ],
                start_to_close_timeout=timedelta(seconds=60),
            )
            self._approval_ids.append(approval_result["approval_id"])

            # 通知审批人
            await workflow.execute_activity(
                send_notification,
                args=[
                    f"多级审批 ({stage_idx + 1}/{total_stages}): {title}",
                    "app",
                    stage_config["approvers"],
                    {"approval_id": approval_result["approval_id"], "stage": stage_idx},
                ],
                start_to_close_timeout=timedelta(seconds=30),
            )

            # 等待该阶段审批
            timeout_hours = stage_config.get("timeout_hours", 24)
            try:
                await workflow.wait_condition(
                    lambda: len(self._stage_results) > stage_idx,
                    timeout=timedelta(hours=timeout_hours),
                )
            except asyncio.TimeoutError:
                self._stage_results.append({
                    "stage": stage_idx,
                    "decision": "timeout",
                    "approver": None,
                    "reason": f"Stage {stage_idx + 1} timed out",
                })

            # 检查结果
            stage_result = self._stage_results[stage_idx]
            if stage_result["decision"] != "approved":
                self._status = "rejected"
                return {
                    "status": "rejected",
                    "rejected_at_stage": stage_idx,
                    "reason": stage_result.get("reason"),
                    "stage_results": self._stage_results,
                }

        # 所有阶段通过
        self._status = "approved"
        return {
            "status": "approved",
            "stage_results": self._stage_results,
        }
