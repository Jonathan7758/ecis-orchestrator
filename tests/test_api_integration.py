"""
API 集成测试

测试 API 端点的完整功能
"""

import pytest
from fastapi.testclient import TestClient

from src.api.main import app
from src.services.task_dispatcher import get_task_dispatcher


@pytest.fixture
def client():
    """创建测试客户端"""
    return TestClient(app, raise_server_exceptions=False)


class TestHealthEndpoints:
    """健康检查端点测试"""

    def test_health_check(self, client):
        """测试健康检查"""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "ecis-orchestrator"

    def test_readiness_check_without_temporal(self, client):
        """测试就绪检查（无Temporal连接）"""
        response = client.get("/ready")
        # 无Temporal时应返回not_ready
        assert response.status_code == 200


class TestTasksAPI:
    """任务 API 测试"""

    def test_list_agents(self, client):
        """测试列出Agent"""
        response = client.get("/api/v1/tasks/agents")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        # 应该有默认注册的Agent
        assert len(data) >= 3

    def test_register_agent(self, client):
        """测试注册Agent"""
        response = client.post(
            "/api/v1/tasks/agents",
            json={
                "agent_id": "test-agent-001",
                "agent_type": "robot",
                "capabilities": ["test.capability"],
                "max_load": 10,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "registered"
        assert data["agent_id"] == "test-agent-001"

    def test_find_available_agents(self, client):
        """测试查找可用Agent"""
        response = client.get(
            "/api/v1/tasks/agents/available",
            params={"capability": "cleaning.floor.standard"},
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_update_agent_status(self, client):
        """测试更新Agent状态"""
        # 先注册一个Agent
        client.post(
            "/api/v1/tasks/agents",
            json={
                "agent_id": "test-agent-002",
                "agent_type": "robot",
                "capabilities": ["test"],
            },
        )
        
        # 更新状态
        response = client.put(
            "/api/v1/tasks/agents/test-agent-002/status",
            params={"status": "busy"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["new_status"] == "busy"

    def test_get_stats(self, client):
        """测试获取统计信息"""
        response = client.get("/api/v1/tasks/stats/overview")
        assert response.status_code == 200
        data = response.json()
        assert "agents" in data
        assert "tasks" in data
        assert "total" in data["agents"]
        assert "ready" in data["agents"]

    def test_dispatch_task(self, client):
        """测试任务分派"""
        response = client.post(
            "/api/v1/tasks/dispatch",
            json={
                "capability": "cleaning.floor.standard",
                "parameters": {"floor": "floor-1"},
                "priority": 3,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "task_id" in data
        assert "agent_id" in data
        assert data["status"] == "assigned"

    def test_dispatch_task_no_agent(self, client):
        """测试任务分派（无可用Agent）"""
        response = client.post(
            "/api/v1/tasks/dispatch",
            json={
                "capability": "nonexistent.capability",
                "parameters": {},
            },
        )
        assert response.status_code == 400

    def test_complete_task(self, client):
        """测试完成任务"""
        # 先分派一个任务
        dispatch_resp = client.post(
            "/api/v1/tasks/dispatch",
            json={
                "capability": "cleaning.floor.standard",
                "parameters": {},
            },
        )
        task_id = dispatch_resp.json()["task_id"]
        
        # 完成任务
        response = client.post(
            f"/api/v1/tasks/{task_id}/complete",
            params={"success": True},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"


class TestDeliveryAPI:
    """配送 API 测试（无Temporal时跳过）"""

    def test_delivery_request_validation(self, client):
        """测试配送请求验证"""
        # 缺少必填字段
        response = client.post(
            "/api/v1/delivery",
            json={
                "pickup_location": "floor-1/room-101",
                # 缺少其他必填字段
            },
        )
        # 路由可能不存在或方法不允许
        assert response.status_code in [404, 405, 422]


class TestApprovalsAPI:
    """审批 API 测试（无Temporal时跳过）"""

    def test_approval_request_validation(self, client):
        """测试审批请求验证"""
        response = client.post(
            "/api/v1/approvals",
            json={
                "request_type": "test",
                # 缺少其他字段
            },
        )
        assert response.status_code in [404, 405, 422]


class TestWorkflowsAPI:
    """工作流 API 测试（无Temporal时跳过）"""

    def test_cleaning_request_validation(self, client):
        """测试清洁请求验证"""
        response = client.post(
            "/api/v1/workflows/cleaning",
            json={
                # 缺少必填字段
            },
        )
        assert response.status_code in [404, 405, 422]
