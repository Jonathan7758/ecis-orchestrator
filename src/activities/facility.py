"""
设施相关 Activity

职责：
- 电梯调度
- 门禁控制
- BMS 控制
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from temporalio import activity


@activity.defn
async def call_elevator(
    from_floor: int,
    to_floor: int,
    robot_id: str,
    robot_size: str = "medium",
) -> Dict[str, Any]:
    """
    为机器人叫电梯

    参数:
        from_floor: 起始楼层
        to_floor: 目标楼层
        robot_id: 机器人 ID
        robot_size: 机器人尺寸

    返回:
        {
            "elevator_id": str,
            "status": str,  # arrived, failed
            "waiting_time_seconds": int
        }
    """
    activity.logger.info(f"Calling elevator: {from_floor} -> {to_floor} for {robot_id}")

    # TODO: 调用 Property Facility API

    return {
        "elevator_id": "elevator-001",
        "status": "arrived",
        "waiting_time_seconds": 30,
    }


@activity.defn
async def open_door(
    door_id: str,
    requester_id: str,
    hold_seconds: int = 30,
) -> Dict[str, Any]:
    """
    打开门禁

    参数:
        door_id: 门禁 ID
        requester_id: 请求者 ID
        hold_seconds: 保持打开时间

    返回:
        {
            "door_id": str,
            "status": str,  # opened, failed
            "hold_until": datetime
        }
    """
    activity.logger.info(f"Opening door: {door_id} for {requester_id}")

    return {
        "door_id": door_id,
        "status": "opened",
        "hold_until": (datetime.now(timezone.utc) + timedelta(seconds=hold_seconds)).isoformat(),
    }


@activity.defn
async def close_door(door_id: str) -> Dict[str, Any]:
    """
    关闭门禁

    参数:
        door_id: 门禁 ID

    返回:
        {
            "door_id": str,
            "status": str,  # closed, failed
        }
    """
    activity.logger.info(f"Closing door: {door_id}")

    return {
        "door_id": door_id,
        "status": "closed",
    }


@activity.defn
async def get_doors_on_route(start_location: str, end_location: str) -> List[str]:
    """
    获取路径上的门禁

    参数:
        start_location: 起点
        end_location: 终点

    返回:
        门禁 ID 列表
    """
    activity.logger.info(f"Getting doors on route: {start_location} -> {end_location}")

    # TODO: 调用路径规划服务
    return ["door-001", "door-002"]


@activity.defn
async def grant_zone_access(
    zone_id: str,
    entity_id: str,
    entity_type: str,
    duration_minutes: int,
) -> Dict[str, Any]:
    """
    授予区域访问权限

    参数:
        zone_id: 区域 ID
        entity_id: 实体 ID（机器人或人员）
        entity_type: 实体类型（robot/human）
        duration_minutes: 有效时长

    返回:
        {
            "access_id": str,
            "granted": bool,
            "expires_at": datetime
        }
    """
    activity.logger.info(f"Granting zone access: {zone_id} to {entity_id}")

    return {
        "access_id": f"access-{zone_id}-{entity_id}",
        "granted": True,
        "expires_at": (
            datetime.now(timezone.utc) + timedelta(minutes=duration_minutes)
        ).isoformat(),
    }


@activity.defn
async def revoke_zone_access(access_id: str) -> Dict[str, Any]:
    """
    撤销区域访问权限

    参数:
        access_id: 访问权限 ID

    返回:
        {
            "access_id": str,
            "revoked": bool
        }
    """
    activity.logger.info(f"Revoking zone access: {access_id}")

    return {
        "access_id": access_id,
        "revoked": True,
    }


@activity.defn
async def get_floor_status(floor_id: str) -> Dict[str, Any]:
    """
    获取楼层状态

    参数:
        floor_id: 楼层 ID

    返回:
        {
            "floor_id": str,
            "occupancy": int,  # 当前人数
            "status": str,  # normal, maintenance, emergency
            "zones": List[Dict]
        }
    """
    activity.logger.info(f"Getting floor status: {floor_id}")

    # TODO: 调用 BMS API

    return {
        "floor_id": floor_id,
        "occupancy": 15,
        "status": "normal",
        "zones": [
            {"zone_id": "zone-a", "name": "大堂", "occupancy": 5},
            {"zone_id": "zone-b", "name": "办公区", "occupancy": 10},
        ],
    }
