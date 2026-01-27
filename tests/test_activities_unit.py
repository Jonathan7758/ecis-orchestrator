"""
Activities 模块测试
"""

import pytest

from src.activities.robot import (
    RobotTaskParams,
    get_robot_status,
    assign_task_to_robot,
    find_available_robot,
    get_robot_location,
)
from src.activities.facility import (
    call_elevator,
    open_door,
    get_doors_on_route,
    grant_zone_access,
    get_floor_status,
)
from src.activities.notification import (
    send_notification,
    create_approval_request,
)
from src.activities.llm import (
    analyze_task_request,
    analyze_exception,
)


class TestRobotActivities:
    """机器人 Activity 测试"""

    @pytest.mark.asyncio
    async def test_get_robot_status(self):
        """测试获取机器人状态"""
        result = await get_robot_status("robot-001")

        assert result["robot_id"] == "robot-001"
        assert result["status"] == "ready"
        assert "battery_level" in result
        assert "current_floor" in result

    @pytest.mark.asyncio
    async def test_assign_task_to_robot(self):
        """测试分配任务给机器人"""
        params = RobotTaskParams(
            robot_id="robot-001",
            task_type="cleaning",
            parameters={"floor": 1, "zone": "lobby"},
            priority=3,
        )

        result = await assign_task_to_robot(params)

        assert "task_id" in result
        assert result["status"] == "assigned"

    @pytest.mark.asyncio
    async def test_find_available_robot(self):
        """测试查找可用机器人"""
        result = await find_available_robot(
            capability="cleaning.floor.standard",
            preferred_floor=3,
        )

        assert result is not None
        assert "robot_id" in result
        assert result["status"] == "ready"

    @pytest.mark.asyncio
    async def test_get_robot_location(self):
        """测试获取机器人位置"""
        result = await get_robot_location("robot-001")

        assert result["robot_id"] == "robot-001"
        assert "floor" in result
        assert "zone" in result
        assert "coordinates" in result


class TestFacilityActivities:
    """设施 Activity 测试"""

    @pytest.mark.asyncio
    async def test_call_elevator(self):
        """测试呼叫电梯"""
        result = await call_elevator(
            from_floor=1,
            to_floor=5,
            robot_id="robot-001",
            robot_size="medium",
        )

        assert "elevator_id" in result
        assert result["status"] == "arrived"
        assert "waiting_time_seconds" in result

    @pytest.mark.asyncio
    async def test_open_door(self):
        """测试开门"""
        result = await open_door(
            door_id="door-001",
            requester_id="robot-001",
            hold_seconds=30,
        )

        assert result["door_id"] == "door-001"
        assert result["status"] == "opened"
        assert "hold_until" in result

    @pytest.mark.asyncio
    async def test_get_doors_on_route(self):
        """测试获取路径上的门禁"""
        result = await get_doors_on_route(
            start_location="lobby",
            end_location="floor-5",
        )

        assert isinstance(result, list)
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_grant_zone_access(self):
        """测试授权区域访问"""
        result = await grant_zone_access(
            zone_id="zone-a",
            entity_id="robot-001",
            entity_type="robot",
            duration_minutes=30,
        )

        assert "access_id" in result
        assert result["granted"] is True
        assert "expires_at" in result

    @pytest.mark.asyncio
    async def test_get_floor_status(self):
        """测试获取楼层状态"""
        result = await get_floor_status("floor-3")

        assert result["floor_id"] == "floor-3"
        assert "occupancy" in result
        assert result["status"] == "normal"
        assert "zones" in result


class TestNotificationActivities:
    """通知 Activity 测试"""

    @pytest.mark.asyncio
    async def test_send_notification(self):
        """测试发送通知"""
        result = await send_notification(
            message="Test notification",
            channel="ops",
            recipients=["user-001"],
            metadata={"key": "value"},
        )

        assert "notification_id" in result
        assert result["sent"] is True
        assert result["channel"] == "ops"
        assert result["recipients_count"] == 1

    @pytest.mark.asyncio
    async def test_create_approval_request(self):
        """测试创建审批请求"""
        result = await create_approval_request(
            request_type="cleaning_task",
            title="清洁任务审批",
            description="需要清洁 5 楼",
            data={"floor": 5},
            approvers=["manager-001"],
            timeout_minutes=60,
        )

        assert "approval_id" in result
        assert result["status"] == "pending"
        assert "manager-001" in result["approvers"]
        assert "expires_at" in result


class TestLLMActivities:
    """LLM Activity 测试"""

    @pytest.mark.asyncio
    async def test_analyze_task_request(self):
        """测试分析任务请求"""
        result = await analyze_task_request(
            natural_language_request="请清洁 5 楼大厅",
            available_capabilities=[
                "cleaning.floor.standard",
                "cleaning.floor.deep",
            ],
        )

        assert result["understood"] is True
        assert "task_type" in result
        assert "capability" in result
        assert "confidence" in result
        assert result["confidence"] > 0.5

    @pytest.mark.asyncio
    async def test_analyze_exception(self):
        """测试分析异常"""
        result = await analyze_exception(
            error_message="Elevator not responding",
            context={"robot_id": "robot-001", "target_floor": 5},
        )

        assert "analysis" in result
        assert "suggested_action" in result
        assert "can_auto_resolve" in result
