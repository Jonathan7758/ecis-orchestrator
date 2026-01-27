"""
Models 模块单元测试
"""

import pytest
from datetime import datetime, timezone

from src.models.base import Base, TimestampMixin, metadata
from src.models.workflow import WorkflowRecord, TaskRecord, ApprovalRecord
from src.models.agent import AgentRecord, AgentEventRecord


class TestBase:
    """Base 模型测试"""

    def test_metadata_has_naming_convention(self):
        """测试元数据命名约定"""
        assert metadata.naming_convention is not None
        assert "ix" in metadata.naming_convention
        assert "uq" in metadata.naming_convention
        assert "fk" in metadata.naming_convention
        assert "pk" in metadata.naming_convention


class TestWorkflowRecord:
    """WorkflowRecord 测试"""

    def test_workflow_record_table_name(self):
        """测试表名"""
        assert WorkflowRecord.__tablename__ == "workflow_records"

    def test_workflow_record_columns(self):
        """测试列定义"""
        columns = [c.name for c in WorkflowRecord.__table__.columns]
        assert "id" in columns
        assert "workflow_id" in columns
        assert "workflow_type" in columns
        assert "status" in columns
        assert "input_data" in columns
        assert "output_data" in columns
        assert "started_at" in columns
        assert "completed_at" in columns
        assert "created_at" in columns
        assert "updated_at" in columns


class TestTaskRecord:
    """TaskRecord 测试"""

    def test_task_record_table_name(self):
        """测试表名"""
        assert TaskRecord.__tablename__ == "task_records"

    def test_task_record_columns(self):
        """测试列定义"""
        columns = [c.name for c in TaskRecord.__table__.columns]
        assert "id" in columns
        assert "task_id" in columns
        assert "workflow_id" in columns
        assert "task_type" in columns
        assert "status" in columns
        assert "agent_id" in columns
        assert "priority" in columns


class TestApprovalRecord:
    """ApprovalRecord 测试"""

    def test_approval_record_table_name(self):
        """测试表名"""
        assert ApprovalRecord.__tablename__ == "approval_records"

    def test_approval_record_columns(self):
        """测试列定义"""
        columns = [c.name for c in ApprovalRecord.__table__.columns]
        assert "id" in columns
        assert "approval_id" in columns
        assert "workflow_id" in columns
        assert "request_type" in columns
        assert "title" in columns
        assert "approvers" in columns
        assert "status" in columns
        assert "decided_by" in columns
        assert "timeout_hours" in columns


class TestAgentRecord:
    """AgentRecord 测试"""

    def test_agent_record_table_name(self):
        """测试表名"""
        assert AgentRecord.__tablename__ == "agent_records"

    def test_agent_record_columns(self):
        """测试列定义"""
        columns = [c.name for c in AgentRecord.__table__.columns]
        assert "id" in columns
        assert "agent_id" in columns
        assert "agent_type" in columns
        assert "name" in columns
        assert "capabilities" in columns
        assert "status" in columns
        assert "current_load" in columns
        assert "max_load" in columns


class TestAgentEventRecord:
    """AgentEventRecord 测试"""

    def test_agent_event_record_table_name(self):
        """测试表名"""
        assert AgentEventRecord.__tablename__ == "agent_event_records"

    def test_agent_event_record_columns(self):
        """测试列定义"""
        columns = [c.name for c in AgentEventRecord.__table__.columns]
        assert "id" in columns
        assert "event_id" in columns
        assert "agent_id" in columns
        assert "event_type" in columns
        assert "data" in columns
        assert "occurred_at" in columns
