"""
Federation 模块单元测试
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from src.federation.federation_client import (
    FederationClient,
    FederationConfig,
    RegisteredAgent,
)


class TestFederationConfig:
    """FederationConfig 测试"""

    def test_create_config(self):
        """测试创建配置"""
        config = FederationConfig(
            gateway_url="http://localhost:8100",
            system_id="test-system",
            system_type="property-service",
            display_name="Test System",
        )

        assert config.gateway_url == "http://localhost:8100"
        assert config.system_id == "test-system"
        assert config.system_type == "property-service"
        assert config.display_name == "Test System"

    def test_default_values(self):
        """测试默认值"""
        config = FederationConfig(
            gateway_url="http://localhost:8100",
            system_id="test-system",
        )

        assert config.reconnect_interval == 30
        assert config.heartbeat_interval == 30
        assert config.max_reconnect_attempts == 10


class TestRegisteredAgent:
    """RegisteredAgent 测试"""

    def test_create_registered_agent(self):
        """测试创建已注册 Agent"""
        agent = RegisteredAgent(
            agent_id="robot-001",
            agent_type="robot",
            capabilities=["cleaning", "delivery"],
            token="test-token",
        )

        assert agent.agent_id == "robot-001"
        assert agent.agent_type == "robot"
        assert "cleaning" in agent.capabilities
        assert agent.token == "test-token"
        assert agent.registered_at is not None


class TestFederationClient:
    """FederationClient 测试"""

    def test_client_initialization(self):
        """测试客户端初始化"""
        client = FederationClient(
            gateway_url="http://localhost:8100",
            system_id="test-system",
        )

        assert client.config.gateway_url == "http://localhost:8100"
        assert client.config.system_id == "test-system"
        assert not client.is_connected

    def test_client_properties(self):
        """测试客户端属性"""
        client = FederationClient(
            gateway_url="http://localhost:8100",
            system_id="orchestrator",
        )

        assert client.system_id == "orchestrator"
        assert client.is_connected == False
        assert client.registered_agents == {}
        assert client.last_heartbeat is None

    @pytest.mark.asyncio
    async def test_list_registered_agents_empty(self):
        """测试列出已注册 Agent (空)"""
        client = FederationClient(
            gateway_url="http://localhost:8100",
            system_id="test-system",
        )

        agents = await client.list_registered_agents()
        assert agents == []

    @pytest.mark.asyncio
    async def test_list_registered_agents(self):
        """测试列出已注册 Agent"""
        client = FederationClient(
            gateway_url="http://localhost:8100",
            system_id="test-system",
        )

        # Manually add a registered agent for testing
        client._registered_agents["robot-001"] = RegisteredAgent(
            agent_id="robot-001",
            agent_type="robot",
            capabilities=["cleaning"],
            token="test-token",
        )

        agents = await client.list_registered_agents()
        assert len(agents) == 1
        assert agents[0]["agent_id"] == "robot-001"
        assert agents[0]["agent_type"] == "robot"
        assert "cleaning" in agents[0]["capabilities"]
