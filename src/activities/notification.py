"""
通知相关 Activity

职责：
- 发送通知（运营、App、邮件、短信）
- 创建审批请求
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
import uuid

from temporalio import activity


@activity.defn
async def send_notification(
    message: str,
    channel: str,
    recipients: Optional[List[str]] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    发送通知

    参数:
        message: 通知内容
        channel: 通知渠道 (ops, app, email, sms)
        recipients: 接收人列表
        metadata: 额外数据

    返回:
        {
            "notification_id": str,
            "sent": bool,
            "channel": str,
            "recipients_count": int
        }
    """
    activity.logger.info(f"Sending notification to {channel}: {message[:50]}...")

    # TODO: 调用通知服务
    # - ops: 推送到运营控制台
    # - app: 推送到 Mobile App
    # - email: 发送邮件
    # - sms: 发送短信

    notification_id = f"notif-{uuid.uuid4().hex[:8]}"

    return {
        "notification_id": notification_id,
        "sent": True,
        "channel": channel,
        "recipients_count": len(recipients) if recipients else 0,
    }


@activity.defn
async def create_approval_request(
    request_type: str,
    title: str,
    description: str,
    data: Dict[str, Any],
    approvers: List[str],
    timeout_minutes: int = 240,
) -> Dict[str, Any]:
    """
    创建审批请求

    参数:
        request_type: 请求类型
        title: 标题
        description: 描述
        data: 审批数据
        approvers: 审批人列表
        timeout_minutes: 超时时间

    返回:
        {
            "approval_id": str,
            "status": str,
            "approvers": List[str],
            "expires_at": str
        }
    """
    activity.logger.info(f"Creating approval request: {request_type} - {title}")

    # TODO:
    # 1. 存储到数据库
    # 2. 发送通知给审批人

    approval_id = f"approval-{uuid.uuid4().hex[:8]}"
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=timeout_minutes)

    return {
        "approval_id": approval_id,
        "status": "pending",
        "approvers": approvers,
        "expires_at": expires_at.isoformat(),
    }


@activity.defn
async def get_approval_status(approval_id: str) -> Dict[str, Any]:
    """
    获取审批状态

    参数:
        approval_id: 审批 ID

    返回:
        {
            "approval_id": str,
            "status": str,  # pending, approved, rejected, expired
            "decided_by": Optional[str],
            "decided_at": Optional[str],
            "reason": Optional[str]
        }
    """
    activity.logger.info(f"Getting approval status: {approval_id}")

    # TODO: 从数据库查询

    return {
        "approval_id": approval_id,
        "status": "pending",
        "decided_by": None,
        "decided_at": None,
        "reason": None,
    }


@activity.defn
async def send_approval_reminder(
    approval_id: str,
    approvers: List[str],
    message: str,
) -> Dict[str, Any]:
    """
    发送审批提醒

    参数:
        approval_id: 审批 ID
        approvers: 审批人列表
        message: 提醒消息

    返回:
        {
            "sent": bool,
            "recipients_count": int
        }
    """
    activity.logger.info(f"Sending approval reminder: {approval_id}")

    # TODO: 调用通知服务

    return {
        "sent": True,
        "recipients_count": len(approvers),
    }


@activity.defn
async def cancel_approval_request(
    approval_id: str,
    reason: Optional[str] = None,
) -> Dict[str, Any]:
    """
    取消审批请求

    参数:
        approval_id: 审批 ID
        reason: 取消原因

    返回:
        {
            "approval_id": str,
            "cancelled": bool
        }
    """
    activity.logger.info(f"Cancelling approval request: {approval_id}")

    # TODO: 更新数据库

    return {
        "approval_id": approval_id,
        "cancelled": True,
    }
