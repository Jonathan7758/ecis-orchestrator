"""
Agent 相关数据库模型
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, String, Integer, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, TimestampMixin


class AgentRecord(Base, TimestampMixin):
    """Agent 记录"""

    __tablename__ = "agent_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    agent_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    agent_type: Mapped[str] = mapped_column(String(50), index=True)
    name: Mapped[str] = mapped_column(String(200))
    
    # 能力
    capabilities: Mapped[list[str]] = mapped_column(JSON)
    
    # 状态
    status: Mapped[str] = mapped_column(String(20), index=True)  # online, offline, busy, maintenance
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # 负载信息
    current_load: Mapped[int] = mapped_column(Integer, default=0)
    max_load: Mapped[int] = mapped_column(Integer, default=5)
    
    # 连接信息
    endpoint: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    federation_token: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    last_heartbeat: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    
    # 元数据
    metadata_: Mapped[Optional[dict]] = mapped_column("metadata", JSON, nullable=True)


class AgentEventRecord(Base, TimestampMixin):
    """Agent 事件记录"""

    __tablename__ = "agent_event_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    agent_id: Mapped[str] = mapped_column(String(100), index=True)
    event_type: Mapped[str] = mapped_column(String(50), index=True)
    
    # 事件数据
    data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    
    # 时间
    occurred_at: Mapped[datetime] = mapped_column(index=True)
