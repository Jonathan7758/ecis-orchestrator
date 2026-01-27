"""
定时任务工作流

职责：
- 定时清洁任务编排
- 定时巡检任务编排
- 任务调度管理
"""

from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Dict, List, Optional

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from src.activities.robot import (
        find_available_robot,
        assign_task_to_robot,
        release_robot,
    )
    from src.activities.facility import (
        get_floor_status,
    )
    from src.activities.notification import (
        send_notification,
        send_task_update,
    )


@dataclass
class ScheduledTaskInput:
    """定时任务输入"""
    task_type: str  # cleaning, patrol, inspection
    target_locations: List[str]  # 目标位置列表
    schedule_name: str  # 计划名称
    priority: int = 3
    robot_id: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None


@dataclass
class ScheduledTaskResult:
    """定时任务结果"""
    success: bool
    task_type: str
    locations_completed: List[str]
    locations_failed: List[str]
    robot_id: str
    message: str = ""
    total_duration_minutes: float = 0


@workflow.defn
class ScheduledCleaningWorkflow:
    """定时清洁工作流 - 按计划执行多个区域的清洁"""

    def __init__(self):
        self._status = "initialized"
        self._robot_id: Optional[str] = None
        self._current_location = ""
        self._completed_locations: List[str] = []
        self._failed_locations: List[str] = []
        self._cancelled = False

    @workflow.query
    def get_status(self) -> Dict[str, Any]:
        """获取工作流状态"""
        return {
            "status": self._status,
            "robot_id": self._robot_id,
            "current_location": self._current_location,
            "completed_locations": self._completed_locations,
            "failed_locations": self._failed_locations,
            "progress": len(self._completed_locations),
        }

    @workflow.signal
    def cancel_schedule(self, reason: str) -> None:
        """取消定时任务"""
        self._cancelled = True
        self._status = f"cancelled: {reason}"

    @workflow.signal
    def skip_location(self, location: str) -> None:
        """跳过某个位置"""
        self._failed_locations.append(location)

    @workflow.run
    async def run(self, input: ScheduledTaskInput) -> ScheduledTaskResult:
        """执行定时清洁工作流"""
        retry_policy = RetryPolicy(
            initial_interval=timedelta(seconds=1),
            maximum_interval=timedelta(seconds=30),
            maximum_attempts=3,
        )

        self._status = "starting"
        start_time = workflow.now()

        try:
            # 分配机器人
            self._status = "assigning_robot"

            if input.robot_id:
                self._robot_id = input.robot_id
            else:
                robot_result = await workflow.execute_activity(
                    find_available_robot,
                    args=["cleaning", input.target_locations[0] if input.target_locations else "floor-1"],
                    start_to_close_timeout=timedelta(seconds=30),
                    retry_policy=retry_policy,
                )
                self._robot_id = robot_result["robot_id"]

            # 发送开始通知
            await workflow.execute_activity(
                send_notification,
                args=["system", "scheduled_cleaning_started", {
                    "schedule_name": input.schedule_name,
                    "robot_id": self._robot_id,
                    "locations": input.target_locations,
                }],
                start_to_close_timeout=timedelta(seconds=10),
            )

            # 依次清洁每个位置
            for location in input.target_locations:
                if self._cancelled:
                    break

                self._current_location = location
                self._status = f"cleaning: {location}"

                try:
                    # 检查区域状态
                    floor_status = await workflow.execute_activity(
                        get_floor_status,
                        args=[location.split("/")[0]],
                        start_to_close_timeout=timedelta(seconds=30),
                    )

                    # 如果区域被占用，跳过
                    if floor_status.get("occupied", False):
                        self._failed_locations.append(location)
                        await workflow.execute_activity(
                            send_task_update,
                            args=["system", f"Skipped {location} - area occupied"],
                            start_to_close_timeout=timedelta(seconds=10),
                        )
                        continue

                    # 分配清洁任务
                    await workflow.execute_activity(
                        assign_task_to_robot,
                        args=[self._robot_id, "cleaning", {
                            "location": location,
                            "mode": input.parameters.get("cleaning_mode", "standard") if input.parameters else "standard",
                        }],
                        start_to_close_timeout=timedelta(seconds=30),
                        retry_policy=retry_policy,
                    )

                    # 模拟清洁时间
                    await workflow.sleep(timedelta(seconds=5))

                    self._completed_locations.append(location)

                    # 发送进度更新
                    await workflow.execute_activity(
                        send_task_update,
                        args=["system", f"Completed cleaning {location}"],
                        start_to_close_timeout=timedelta(seconds=10),
                    )

                except Exception as e:
                    self._failed_locations.append(location)

            # 释放机器人
            await workflow.execute_activity(
                release_robot,
                args=[self._robot_id],
                start_to_close_timeout=timedelta(seconds=30),
            )

            self._status = "completed"
            self._current_location = ""

            end_time = workflow.now()
            duration = (end_time - start_time).total_seconds() / 60

            # 发送完成通知
            await workflow.execute_activity(
                send_notification,
                args=["system", "scheduled_cleaning_completed", {
                    "schedule_name": input.schedule_name,
                    "robot_id": self._robot_id,
                    "completed": self._completed_locations,
                    "failed": self._failed_locations,
                }],
                start_to_close_timeout=timedelta(seconds=10),
            )

            return ScheduledTaskResult(
                success=len(self._failed_locations) == 0,
                task_type="cleaning",
                locations_completed=self._completed_locations,
                locations_failed=self._failed_locations,
                robot_id=self._robot_id,
                message=f"Completed {len(self._completed_locations)}/{len(input.target_locations)} locations",
                total_duration_minutes=duration,
            )

        except Exception as e:
            self._status = f"failed: {str(e)}"

            if self._robot_id:
                try:
                    await workflow.execute_activity(
                        release_robot,
                        args=[self._robot_id],
                        start_to_close_timeout=timedelta(seconds=30),
                    )
                except:
                    pass

            return ScheduledTaskResult(
                success=False,
                task_type="cleaning",
                locations_completed=self._completed_locations,
                locations_failed=self._failed_locations + [
                    loc for loc in input.target_locations
                    if loc not in self._completed_locations and loc not in self._failed_locations
                ],
                robot_id=self._robot_id or "",
                message=f"Scheduled cleaning failed: {str(e)}",
            )


@workflow.defn
class ScheduledPatrolWorkflow:
    """定时巡检工作流 - 按计划执行安全巡检"""

    def __init__(self):
        self._status = "initialized"
        self._robot_id: Optional[str] = None
        self._current_checkpoint = ""
        self._checkpoints_visited: List[str] = []
        self._anomalies_detected: List[Dict[str, Any]] = []
        self._cancelled = False

    @workflow.query
    def get_status(self) -> Dict[str, Any]:
        """获取工作流状态"""
        return {
            "status": self._status,
            "robot_id": self._robot_id,
            "current_checkpoint": self._current_checkpoint,
            "checkpoints_visited": self._checkpoints_visited,
            "anomalies_detected": self._anomalies_detected,
        }

    @workflow.signal
    def cancel_patrol(self, reason: str) -> None:
        """取消巡检"""
        self._cancelled = True
        self._status = f"cancelled: {reason}"

    @workflow.signal
    def report_anomaly(self, checkpoint: str, anomaly_type: str, description: str) -> None:
        """报告异常"""
        self._anomalies_detected.append({
            "checkpoint": checkpoint,
            "type": anomaly_type,
            "description": description,
            "time": workflow.now().isoformat(),
        })

    @workflow.run
    async def run(self, input: ScheduledTaskInput) -> ScheduledTaskResult:
        """执行定时巡检工作流"""
        retry_policy = RetryPolicy(
            initial_interval=timedelta(seconds=1),
            maximum_interval=timedelta(seconds=30),
            maximum_attempts=3,
        )

        self._status = "starting"
        start_time = workflow.now()

        try:
            # 分配巡检机器人
            self._status = "assigning_robot"

            if input.robot_id:
                self._robot_id = input.robot_id
            else:
                robot_result = await workflow.execute_activity(
                    find_available_robot,
                    args=["patrol", input.target_locations[0] if input.target_locations else "floor-1"],
                    start_to_close_timeout=timedelta(seconds=30),
                    retry_policy=retry_policy,
                )
                self._robot_id = robot_result["robot_id"]

            # 发送开始通知
            await workflow.execute_activity(
                send_notification,
                args=["security", "patrol_started", {
                    "schedule_name": input.schedule_name,
                    "robot_id": self._robot_id,
                    "checkpoints": input.target_locations,
                }],
                start_to_close_timeout=timedelta(seconds=10),
            )

            # 依次访问每个检查点
            for checkpoint in input.target_locations:
                if self._cancelled:
                    break

                self._current_checkpoint = checkpoint
                self._status = f"patrolling: {checkpoint}"

                try:
                    # 分配巡检任务
                    await workflow.execute_activity(
                        assign_task_to_robot,
                        args=[self._robot_id, "patrol", {
                            "checkpoint": checkpoint,
                            "check_items": input.parameters.get("check_items", ["security", "safety"]) if input.parameters else ["security", "safety"],
                        }],
                        start_to_close_timeout=timedelta(seconds=30),
                        retry_policy=retry_policy,
                    )

                    # 模拟巡检时间
                    await workflow.sleep(timedelta(seconds=3))

                    self._checkpoints_visited.append(checkpoint)

                    # 发送进度更新
                    await workflow.execute_activity(
                        send_task_update,
                        args=["security", f"Checkpoint {checkpoint} cleared"],
                        start_to_close_timeout=timedelta(seconds=10),
                    )

                except Exception as e:
                    # 记录异常
                    self._anomalies_detected.append({
                        "checkpoint": checkpoint,
                        "type": "access_error",
                        "description": str(e),
                        "time": workflow.now().isoformat(),
                    })

            # 释放机器人
            await workflow.execute_activity(
                release_robot,
                args=[self._robot_id],
                start_to_close_timeout=timedelta(seconds=30),
            )

            self._status = "completed"
            self._current_checkpoint = ""

            end_time = workflow.now()
            duration = (end_time - start_time).total_seconds() / 60

            # 发送巡检报告
            await workflow.execute_activity(
                send_notification,
                args=["security", "patrol_completed", {
                    "schedule_name": input.schedule_name,
                    "robot_id": self._robot_id,
                    "checkpoints_visited": self._checkpoints_visited,
                    "anomalies": self._anomalies_detected,
                }],
                start_to_close_timeout=timedelta(seconds=10),
            )

            failed_checkpoints = [
                cp for cp in input.target_locations
                if cp not in self._checkpoints_visited
            ]

            return ScheduledTaskResult(
                success=len(self._anomalies_detected) == 0 and len(failed_checkpoints) == 0,
                task_type="patrol",
                locations_completed=self._checkpoints_visited,
                locations_failed=failed_checkpoints,
                robot_id=self._robot_id,
                message=f"Patrol completed. {len(self._anomalies_detected)} anomalies detected.",
                total_duration_minutes=duration,
            )

        except Exception as e:
            self._status = f"failed: {str(e)}"

            if self._robot_id:
                try:
                    await workflow.execute_activity(
                        release_robot,
                        args=[self._robot_id],
                        start_to_close_timeout=timedelta(seconds=30),
                    )
                except:
                    pass

            return ScheduledTaskResult(
                success=False,
                task_type="patrol",
                locations_completed=self._checkpoints_visited,
                locations_failed=[
                    cp for cp in input.target_locations
                    if cp not in self._checkpoints_visited
                ],
                robot_id=self._robot_id or "",
                message=f"Patrol failed: {str(e)}",
            )
