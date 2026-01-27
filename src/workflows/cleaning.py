"""
清洁工作流

包含机器人清洁的完整工作流程
"""

from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Dict, Optional

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from src.activities.facility import (
        call_elevator,
        get_doors_on_route,
        get_floor_status,
        grant_zone_access,
        open_door,
    )
    from src.activities.notification import send_notification
    from src.activities.robot import (
        RobotTaskParams,
        assign_task_to_robot,
        find_available_robot,
        get_robot_status,
        wait_for_robot_task_completion,
    )


@dataclass
class CleaningWorkflowInput:
    """清洁工作流输入"""

    floor_id: str
    zone_id: Optional[str] = None
    cleaning_mode: str = "standard"  # standard, deep, quick
    robot_id: Optional[str] = None  # 指定机器人，否则自动选择
    priority: int = 3


@dataclass
class CleaningWorkflowResult:
    """清洁工作流结果"""

    success: bool
    robot_id: str
    floor_id: str
    zone_id: Optional[str]
    duration_minutes: int
    area_cleaned_sqm: float
    message: str


@workflow.defn
class RobotCleaningWorkflow:
    """
    机器人清洁工作流

    流程:
    1. 检查楼层状态
    2. 查找或验证机器人
    3. 准备清洁（开门、电梯等）
    4. 分配任务给机器人
    5. 等待任务完成
    6. 清理（关门等）
    7. 发送通知
    """

    def __init__(self):
        self._status = "pending"
        self._progress = 0
        self._current_step = ""
        self._robot_id: Optional[str] = None
        self._error: Optional[str] = None

    @workflow.query
    def get_status(self) -> Dict[str, Any]:
        """查询工作流状态"""
        return {
            "status": self._status,
            "progress": self._progress,
            "current_step": self._current_step,
            "robot_id": self._robot_id,
            "error": self._error,
        }

    @workflow.signal
    async def cancel_cleaning(self, reason: str = ""):
        """取消清洁信号"""
        self._status = "cancelling"
        self._error = f"Cancelled: {reason}" if reason else "Cancelled by user"

    @workflow.run
    async def run(self, input: CleaningWorkflowInput) -> CleaningWorkflowResult:
        """执行清洁工作流"""
        self._status = "running"

        # 重试策略
        retry_policy = RetryPolicy(
            initial_interval=timedelta(seconds=1),
            maximum_interval=timedelta(minutes=1),
            maximum_attempts=3,
        )

        try:
            # 步骤 1: 检查楼层状态
            self._current_step = "checking_floor_status"
            self._progress = 10
            workflow.logger.info(f"Checking floor status: {input.floor_id}")

            floor_status = await workflow.execute_activity(
                get_floor_status,
                input.floor_id,
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=retry_policy,
            )

            # 检查是否可以清洁
            if floor_status["status"] != "normal":
                return CleaningWorkflowResult(
                    success=False,
                    robot_id="",
                    floor_id=input.floor_id,
                    zone_id=input.zone_id,
                    duration_minutes=0,
                    area_cleaned_sqm=0,
                    message=f"Floor status is {floor_status['status']}, cannot clean",
                )

            # 步骤 2: 获取或查找机器人
            self._current_step = "finding_robot"
            self._progress = 20
            workflow.logger.info("Finding available robot")

            if input.robot_id:
                # 验证指定的机器人
                robot_status = await workflow.execute_activity(
                    get_robot_status,
                    input.robot_id,
                    start_to_close_timeout=timedelta(seconds=30),
                    retry_policy=retry_policy,
                )
                if robot_status["status"] != "ready":
                    return CleaningWorkflowResult(
                        success=False,
                        robot_id=input.robot_id,
                        floor_id=input.floor_id,
                        zone_id=input.zone_id,
                        duration_minutes=0,
                        area_cleaned_sqm=0,
                        message=f"Robot {input.robot_id} is not ready: {robot_status['status']}",
                    )
                self._robot_id = input.robot_id
            else:
                # 自动查找可用机器人
                robot = await workflow.execute_activity(
                    find_available_robot,
                    args=[f"cleaning.floor.{input.cleaning_mode}", int(input.floor_id.split("-")[-1]) if "-" in input.floor_id else 1],
                    start_to_close_timeout=timedelta(seconds=30),
                    retry_policy=retry_policy,
                )
                if not robot:
                    return CleaningWorkflowResult(
                        success=False,
                        robot_id="",
                        floor_id=input.floor_id,
                        zone_id=input.zone_id,
                        duration_minutes=0,
                        area_cleaned_sqm=0,
                        message="No available robot found",
                    )
                self._robot_id = robot["robot_id"]

            # 步骤 3: 准备清洁 - 并行执行
            self._current_step = "preparing"
            self._progress = 30
            workflow.logger.info("Preparing for cleaning")

            # 获取路径上的门禁
            doors = await workflow.execute_activity(
                get_doors_on_route,
                args=["robot-station", input.floor_id],
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=retry_policy,
            )

            # 并行：开门 + 叫电梯 + 授权区域访问
            prepare_tasks = []

            # 开门
            for door_id in doors:
                prepare_tasks.append(
                    workflow.execute_activity(
                        open_door,
                        args=[door_id, self._robot_id, 60],
                        start_to_close_timeout=timedelta(seconds=30),
                        retry_policy=retry_policy,
                    )
                )

            # 叫电梯（如果需要跨楼层）
            floor_num = int(input.floor_id.split("-")[-1]) if "-" in input.floor_id else 1
            if floor_num != 1:
                prepare_tasks.append(
                    workflow.execute_activity(
                        call_elevator,
                        args=[1, floor_num, self._robot_id, "medium"],
                        start_to_close_timeout=timedelta(minutes=5),
                        retry_policy=retry_policy,
                    )
                )

            # 授权区域访问
            zone_to_clean = input.zone_id or f"{input.floor_id}-zone-a"
            prepare_tasks.append(
                workflow.execute_activity(
                    grant_zone_access,
                    args=[zone_to_clean, self._robot_id, "robot", 120],
                    start_to_close_timeout=timedelta(seconds=30),
                    retry_policy=retry_policy,
                )
            )

            # 等待所有准备工作完成
            await asyncio.gather(*prepare_tasks) if prepare_tasks else None

            # 步骤 4: 分配任务给机器人
            self._current_step = "assigning_task"
            self._progress = 50
            workflow.logger.info(f"Assigning cleaning task to robot: {self._robot_id}")

            task_params = RobotTaskParams(
                robot_id=self._robot_id,
                task_type="cleaning",
                parameters={
                    "floor_id": input.floor_id,
                    "zone_id": input.zone_id,
                    "mode": input.cleaning_mode,
                },
                priority=input.priority,
            )

            task_result = await workflow.execute_activity(
                assign_task_to_robot,
                task_params,
                start_to_close_timeout=timedelta(minutes=1),
                retry_policy=retry_policy,
            )

            if task_result["status"] != "assigned":
                return CleaningWorkflowResult(
                    success=False,
                    robot_id=self._robot_id,
                    floor_id=input.floor_id,
                    zone_id=input.zone_id,
                    duration_minutes=0,
                    area_cleaned_sqm=0,
                    message=f"Task assignment failed: {task_result.get('reason', 'Unknown')}",
                )

            task_id = task_result["task_id"]

            # 步骤 5: 等待任务完成
            self._current_step = "cleaning"
            self._progress = 60
            workflow.logger.info(f"Waiting for cleaning task completion: {task_id}")

            completion_result = await workflow.execute_activity(
                wait_for_robot_task_completion,
                args=[task_id, 3600],  # 1小时超时
                start_to_close_timeout=timedelta(hours=2),
                heartbeat_timeout=timedelta(minutes=1),
            )

            if completion_result["status"] != "completed":
                return CleaningWorkflowResult(
                    success=False,
                    robot_id=self._robot_id,
                    floor_id=input.floor_id,
                    zone_id=input.zone_id,
                    duration_minutes=0,
                    area_cleaned_sqm=0,
                    message=f"Cleaning task failed: {completion_result['status']}",
                )

            # 步骤 6: 发送完成通知
            self._current_step = "notifying"
            self._progress = 90
            workflow.logger.info("Sending completion notification")

            await workflow.execute_activity(
                send_notification,
                args=[
                    f"清洁任务完成: {input.floor_id}",
                    "ops",
                    None,
                    {
                        "robot_id": self._robot_id,
                        "floor_id": input.floor_id,
                        "duration": completion_result["result"].get("duration_minutes", 0),
                    },
                ],
                start_to_close_timeout=timedelta(seconds=30),
            )

            # 完成
            self._status = "completed"
            self._progress = 100
            self._current_step = "completed"

            return CleaningWorkflowResult(
                success=True,
                robot_id=self._robot_id,
                floor_id=input.floor_id,
                zone_id=input.zone_id,
                duration_minutes=completion_result["result"].get("duration_minutes", 0),
                area_cleaned_sqm=completion_result["result"].get("area_cleaned_sqm", 0),
                message="Cleaning completed successfully",
            )

        except Exception as e:
            self._status = "failed"
            self._error = str(e)
            workflow.logger.error(f"Cleaning workflow failed: {e}")

            # 发送失败通知
            await workflow.execute_activity(
                send_notification,
                args=[
                    f"清洁任务失败: {input.floor_id} - {str(e)}",
                    "ops",
                    None,
                    {"error": str(e)},
                ],
                start_to_close_timeout=timedelta(seconds=30),
            )

            return CleaningWorkflowResult(
                success=False,
                robot_id=self._robot_id or "",
                floor_id=input.floor_id,
                zone_id=input.zone_id,
                duration_minutes=0,
                area_cleaned_sqm=0,
                message=f"Workflow failed: {str(e)}",
            )


# 需要导入 asyncio 用于 gather
import asyncio
