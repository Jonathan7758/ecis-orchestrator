"""
Core 模块测试
"""

import pytest

from src.core.config import Config, get_config, reset_config
from src.core.exceptions import (
    OrchestratorError,
    WorkflowNotFoundError,
    TaskDispatchError,
    NoAvailableAgentError,
    ApprovalTimeoutError,
)


class TestConfig:
    """配置测试"""

    def setup_method(self):
        """每个测试前重置配置"""
        reset_config()

    def test_get_config_singleton(self):
        """测试配置单例"""
        config1 = get_config()
        config2 = get_config()
        assert config1 is config2

    def test_temporal_config_defaults(self):
        """测试 Temporal 默认配置"""
        config = get_config()
        assert config.temporal.host == "localhost"
        assert config.temporal.port == 7233
        assert config.temporal.address == "localhost:7233"
        assert config.temporal.task_queue == "ecis-orchestrator-queue"

    def test_database_config_defaults(self):
        """测试数据库默认配置"""
        config = get_config()
        assert "postgresql" in config.database.url
        assert config.database.pool_size == 10

    def test_redis_config_defaults(self):
        """测试 Redis 默认配置"""
        config = get_config()
        assert config.redis.url == "redis://localhost:6380"

    def test_app_config_defaults(self):
        """测试应用默认配置"""
        config = get_config()
        assert config.app.port == 8200
        assert config.app.debug is True


class TestExceptions:
    """异常测试"""

    def test_orchestrator_error_basic(self):
        """测试基础异常"""
        error = OrchestratorError("Test error", "TEST_CODE")
        assert error.message == "Test error"
        assert error.code == "TEST_CODE"
        assert error.details == {}

    def test_orchestrator_error_to_dict(self):
        """测试异常转字典"""
        error = OrchestratorError("Test", "CODE", {"key": "value"})
        d = error.to_dict()
        assert d["code"] == "CODE"
        assert d["message"] == "Test"
        assert d["details"]["key"] == "value"

    def test_workflow_not_found_error(self):
        """测试工作流不存在异常"""
        error = WorkflowNotFoundError("wf-123")
        assert "wf-123" in error.message
        assert error.code == "WORKFLOW_NOT_FOUND"
        assert error.details["workflow_id"] == "wf-123"

    def test_task_dispatch_error(self):
        """测试任务分派异常"""
        error = TaskDispatchError("Failed to dispatch", "task-456")
        assert error.code == "TASK_DISPATCH_FAILED"
        assert error.details["task_id"] == "task-456"

    def test_no_available_agent_error(self):
        """测试无可用 Agent 异常"""
        error = NoAvailableAgentError("cleaning.floor.standard", "robot")
        assert "cleaning.floor.standard" in error.message
        assert error.code == "NO_AVAILABLE_AGENT"
        assert error.details["capability"] == "cleaning.floor.standard"
        assert error.details["agent_type"] == "robot"

    def test_approval_timeout_error(self):
        """测试审批超时异常"""
        error = ApprovalTimeoutError("ar-789", 24)
        assert "ar-789" in error.message
        assert error.code == "APPROVAL_TIMEOUT"
        assert error.details["timeout_hours"] == 24
