"""
工作流相关数据库模型
"""

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import JSON, ForeignKey, String, Text, Integer, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TimestampMixin


class WorkflowRecord(Base, TimestampMixin):
    """工作流记录"""

    __tablename__ = "workflow_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    workflow_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    workflow_type: Mapped[str] = mapped_column(String(50), index=True)
    status: Mapped[str] = mapped_column(String(20), index=True)  # pending, running, completed, failed, cancelled
    
    # 工作流输入输出
    input_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    output_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # 时间信息
    started_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    
    # 关联
    tasks: Mapped[list["TaskRecord"]] = relationship(
        "TaskRecord", back_populates="workflow", cascade="all, delete-orphan"
    )
    
    # 元数据
    metadata_: Mapped[Optional[dict]] = mapped_column("metadata", JSON, nullable=True)


class TaskRecord(Base, TimestampMixin):
    """任务记录"""

    __tablename__ = "task_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    workflow_id: Mapped[Optional[str]] = mapped_column(
        String(100), ForeignKey("workflow_records.workflow_id"), nullable=True, index=True
    )
    task_type: Mapped[str] = mapped_column(String(50), index=True)
    status: Mapped[str] = mapped_column(String(20), index=True)  # pending, running, completed, failed
    
    # 任务信息
    agent_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    agent_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    capability: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    priority: Mapped[int] = mapped_column(Integer, default=3)
    
    # 输入输出
    input_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    output_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # 时间信息
    assigned_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    
    # 关联
    workflow: Mapped[Optional["WorkflowRecord"]] = relationship(
        "WorkflowRecord", back_populates="tasks"
    )
    
    # 元数据
    metadata_: Mapped[Optional[dict]] = mapped_column("metadata", JSON, nullable=True)


class ApprovalRecord(Base, TimestampMixin):
    """审批记录"""

    __tablename__ = "approval_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    approval_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    workflow_id: Mapped[str] = mapped_column(String(100), index=True)
    request_type: Mapped[str] = mapped_column(String(50), index=True)
    
    # 审批信息
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    
    # 审批人
    approvers: Mapped[list[str]] = mapped_column(JSON)  # List of approver IDs
    current_approver: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    # 状态
    status: Mapped[str] = mapped_column(String(20), index=True)  # pending, approved, rejected, cancelled, timeout
    decided_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    decision_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    decided_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    
    # 超时设置
    timeout_hours: Mapped[int] = mapped_column(Integer, default=24)
    deadline: Mapped[Optional[datetime]] = mapped_column(nullable=True)
