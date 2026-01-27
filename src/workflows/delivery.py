"""
配送工作流

职责：
- 物品配送任务编排
- 电梯/门禁协调
- 配送状态跟踪
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
        get_robot_location,
        release_robot,
    )
    from src.activities.facility import (
        call_elevator,
        get_doors_on_route,
        grant_zone_access,
    )
    from src.activities.notification import (
        send_notification,
    )


@dataclass
class DeliveryWorkflowInput:
    """配送工作流输入"""
    pickup_location: str  # 取货位置 (e.g., "floor-1/room-101")
    delivery_location: str  # 送达位置 (e.g., "floor-3/room-305")
    item_description: str  # 物品描述
    recipient_id: str  # 收件人 ID
    sender_id: Optional[str] = None  # 发件人 ID
    robot_id: Optional[str] = None  # 指定机器人
    priority: int = 3  # 优先级 1-5
    require_signature: bool = False  # 是否需要签收
    notes: Optional[str] = None  # 备注


@dataclass
class DeliveryWorkflowResult:
    """配送工作流结果"""
    success: bool
    robot_id: str
    pickup_time: Optional[str] = None
    delivery_time: Optional[str] = None
    signature: Optional[str] = None
    message: str = ""
    total_duration_minutes: float = 0


@workflow.defn
class DeliveryWorkflow:
    """配送工作流"""

    def __init__(self):
        self._status = "initialized"
        self._robot_id: Optional[str] = None
        self._current_phase = ""
        self._pickup_completed = False
        self._delivery_completed = False
        self._cancelled = False

    @workflow.query
    def get_status(self) -> Dict[str, Any]:
        """获取工作流状态"""
        return {
            "status": self._status,
            "robot_id": self._robot_id,
            "current_phase": self._current_phase,
            "pickup_completed": self._pickup_completed,
            "delivery_completed": self._delivery_completed,
        }

    @workflow.signal
    def cancel_delivery(self, reason: str) -> None:
        """取消配送"""
        self._cancelled = True
        self._status = f"cancelled: {reason}"

    @workflow.signal
    def confirm_pickup(self) -> None:
        """确认取货"""
        self._pickup_completed = True

    @workflow.signal
    def confirm_delivery(self, signature: Optional[str] = None) -> None:
        """确认送达"""
        self._delivery_completed = True

    @workflow.run
    async def run(self, input: DeliveryWorkflowInput) -> DeliveryWorkflowResult:
        """执行配送工作流"""
        retry_policy = RetryPolicy(
            initial_interval=timedelta(seconds=1),
            maximum_interval=timedelta(seconds=30),
            maximum_attempts=3,
        )

        self._status = "starting"
        start_time = workflow.now()

        # 解析位置信息
        pickup_floor = input.pickup_location.split("/")[0]
        delivery_floor = input.delivery_location.split("/")[0]

        try:
            # 阶段1: 分配机器人
            self._current_phase = "assigning_robot"
            self._status = "assigning_robot"

            if input.robot_id:
                self._robot_id = input.robot_id
            else:
                robot_result = await workflow.execute_activity(
                    find_available_robot,
                    args=["delivery", pickup_floor],
                    start_to_close_timeout=timedelta(seconds=30),
                    retry_policy=retry_policy,
                )
                self._robot_id = robot_result["robot_id"]

            # 分配任务给机器人
            await workflow.execute_activity(
                assign_task_to_robot,
                args=[self._robot_id, "delivery", {
                    "pickup": input.pickup_location,
                    "delivery": input.delivery_location,
                    "item": input.item_description,
                }],
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=retry_policy,
            )

            # 发送通知
            await workflow.execute_activity(
                send_notification,
                args=[input.sender_id or "system", "delivery_started", {
                    "robot_id": self._robot_id,
                    "pickup": input.pickup_location,
                    "delivery": input.delivery_location,
                }],
                start_to_close_timeout=timedelta(seconds=10),
            )

            if self._cancelled:
                return DeliveryWorkflowResult(
                    success=False,
                    robot_id=self._robot_id,
                    message="Delivery cancelled before pickup",
                )

            # 阶段2: 前往取货点
            self._current_phase = "going_to_pickup"
            self._status = "going_to_pickup"

            # 获取路线上的门
            await workflow.execute_activity(
                get_doors_on_route,
                args=["robot_home", input.pickup_location],
                start_to_close_timeout=timedelta(seconds=30),
            )

            # 获取机器人当前位置
            robot_location = await workflow.execute_activity(
                get_robot_location,
                args=[self._robot_id],
                start_to_close_timeout=timedelta(seconds=10),
            )

            current_floor = robot_location.get("floor", "floor-1")
            if current_floor != pickup_floor:
                await workflow.execute_activity(
                    call_elevator,
                    args=[current_floor, pickup_floor, self._robot_id],
                    start_to_close_timeout=timedelta(seconds=120),
                    retry_policy=retry_policy,
                )

            # 阶段3: 取货
            self._current_phase = "picking_up"
            self._status = "at_pickup_waiting"

            # 通知发件人机器人已到达
            if input.sender_id:
                await workflow.execute_activity(
                    send_notification,
                    args=[input.sender_id, "robot_arrived_pickup", {
                        "robot_id": self._robot_id,
                        "location": input.pickup_location,
                    }],
                    start_to_close_timeout=timedelta(seconds=10),
                )

            # 等待取货确认（最多等待10分钟）
            try:
                await workflow.wait_condition(
                    lambda: self._pickup_completed or self._cancelled,
                    timeout=timedelta(minutes=10),
                )
            except TimeoutError:
                # 自动确认取货（模拟场景）
                self._pickup_completed = True

            if self._cancelled:
                await workflow.execute_activity(
                    release_robot,
                    args=[self._robot_id],
                    start_to_close_timeout=timedelta(seconds=30),
                )
                return DeliveryWorkflowResult(
                    success=False,
                    robot_id=self._robot_id,
                    message="Delivery cancelled at pickup",
                )

            pickup_time = workflow.now().isoformat()

            # 阶段4: 前往送达点
            self._current_phase = "going_to_delivery"
            self._status = "going_to_delivery"

            # 如果需要跨楼层
            if pickup_floor != delivery_floor:
                await workflow.execute_activity(
                    call_elevator,
                    args=[pickup_floor, delivery_floor, self._robot_id],
                    start_to_close_timeout=timedelta(seconds=120),
                    retry_policy=retry_policy,
                )

            # 获取送达点门禁权限
            await workflow.execute_activity(
                grant_zone_access,
                args=[self._robot_id, delivery_floor, 30],  # 30分钟权限
                start_to_close_timeout=timedelta(seconds=30),
            )

            # 阶段5: 送达
            self._current_phase = "delivering"
            self._status = "at_delivery_waiting"

            # 通知收件人
            await workflow.execute_activity(
                send_notification,
                args=[input.recipient_id, "robot_arrived_delivery", {
                    "robot_id": self._robot_id,
                    "location": input.delivery_location,
                    "item": input.item_description,
                }],
                start_to_close_timeout=timedelta(seconds=10),
            )

            # 等待送达确认
            signature = None
            try:
                await workflow.wait_condition(
                    lambda: self._delivery_completed or self._cancelled,
                    timeout=timedelta(minutes=15),
                )
            except TimeoutError:
                # 超时自动完成
                self._delivery_completed = True

            if self._cancelled:
                return DeliveryWorkflowResult(
                    success=False,
                    robot_id=self._robot_id,
                    pickup_time=pickup_time,
                    message="Delivery cancelled at destination",
                )

            delivery_time = workflow.now().isoformat()

            # 阶段6: 完成并返回
            self._current_phase = "completing"
            self._status = "completed"

            # 释放机器人
            await workflow.execute_activity(
                release_robot,
                args=[self._robot_id],
                start_to_close_timeout=timedelta(seconds=30),
            )

            # 发送完成通知
            await workflow.execute_activity(
                send_notification,
                args=[input.recipient_id, "delivery_completed", {
                    "robot_id": self._robot_id,
                    "item": input.item_description,
                }],
                start_to_close_timeout=timedelta(seconds=10),
            )

            end_time = workflow.now()
            duration = (end_time - start_time).total_seconds() / 60

            return DeliveryWorkflowResult(
                success=True,
                robot_id=self._robot_id,
                pickup_time=pickup_time,
                delivery_time=delivery_time,
                signature=signature,
                message="Delivery completed successfully",
                total_duration_minutes=duration,
            )

        except Exception as e:
            self._status = f"failed: {str(e)}"

            # 尝试释放机器人
            if self._robot_id:
                try:
                    await workflow.execute_activity(
                        release_robot,
                        args=[self._robot_id],
                        start_to_close_timeout=timedelta(seconds=30),
                    )
                except:
                    pass

            return DeliveryWorkflowResult(
                success=False,
                robot_id=self._robot_id or "",
                message=f"Delivery failed: {str(e)}",
            )
