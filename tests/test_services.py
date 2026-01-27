"""
Services 模块单元测试
"""

import pytest
from datetime import datetime, timezone

from src.services.task_dispatcher import (
    TaskDispatcher,
    AgentInfo,
    TaskAssignment,
    get_task_dispatcher,
)


class TestAgentInfo:
    """AgentInfo 测试"""

    def test_create_agent_info(self):
        """测试创建 AgentInfo"""
        agent = AgentInfo(
            agent_id="test-agent-001",
            agent_type="robot",
            capabilities=["cleaning.floor", "delivery"],
            status="ready",
            current_load=0,
            max_load=5,
        )

        assert agent.agent_id == "test-agent-001"
        assert agent.agent_type == "robot"
        assert "cleaning.floor" in agent.capabilities
        assert agent.status == "ready"
        assert agent.current_load == 0
        assert agent.max_load == 5


class TestTaskDispatcher:
    """TaskDispatcher 测试"""

    def setup_method(self):
        """测试前设置"""
        self.dispatcher = TaskDispatcher()

    def test_register_agent(self):
        """测试注册 Agent"""
        agent = AgentInfo(
            agent_id="agent-001",
            agent_type="robot",
            capabilities=["cleaning.floor.standard"],
            status="ready",
        )

        self.dispatcher.register_agent(agent)
        assert "agent-001" in self.dispatcher._agents

    def test_unregister_agent(self):
        """测试注销 Agent"""
        agent = AgentInfo(
            agent_id="agent-002",
            agent_type="robot",
            capabilities=["cleaning.floor.standard"],
            status="ready",
        )

        self.dispatcher.register_agent(agent)
        self.dispatcher.unregister_agent("agent-002")
        assert "agent-002" not in self.dispatcher._agents

    def test_update_agent_status(self):
        """测试更新 Agent 状态"""
        agent = AgentInfo(
            agent_id="agent-003",
            agent_type="robot",
            capabilities=["cleaning.floor.standard"],
            status="ready",
        )

        self.dispatcher.register_agent(agent)
        self.dispatcher.update_agent_status("agent-003", "busy")
        assert self.dispatcher._agents["agent-003"].status == "busy"

    def test_find_available_agents(self):
        """测试查找可用 Agent"""
        agent1 = AgentInfo(
            agent_id="agent-004",
            agent_type="robot",
            capabilities=["cleaning.floor.standard"],
            status="ready",
        )
        agent2 = AgentInfo(
            agent_id="agent-005",
            agent_type="robot",
            capabilities=["delivery"],
            status="ready",
        )
        agent3 = AgentInfo(
            agent_id="agent-006",
            agent_type="robot",
            capabilities=["cleaning.floor.standard"],
            status="busy",  # Not available
        )

        self.dispatcher.register_agent(agent1)
        self.dispatcher.register_agent(agent2)
        self.dispatcher.register_agent(agent3)

        available = self.dispatcher.find_available_agents("cleaning.floor.standard")
        assert len(available) == 1
        assert available[0].agent_id == "agent-004"

    def test_find_available_agents_with_wildcard(self):
        """测试通配符能力匹配"""
        agent = AgentInfo(
            agent_id="agent-007",
            agent_type="robot",
            capabilities=["cleaning.*"],
            status="ready",
        )

        self.dispatcher.register_agent(agent)

        available = self.dispatcher.find_available_agents("cleaning.floor.standard")
        assert len(available) == 1

    def test_select_best_agent_load_balancing(self):
        """测试负载均衡选择"""
        agent1 = AgentInfo(
            agent_id="agent-008",
            agent_type="robot",
            capabilities=["cleaning.floor.standard"],
            status="ready",
            current_load=3,
        )
        agent2 = AgentInfo(
            agent_id="agent-009",
            agent_type="robot",
            capabilities=["cleaning.floor.standard"],
            status="ready",
            current_load=1,  # Lower load
        )

        self.dispatcher.register_agent(agent1)
        self.dispatcher.register_agent(agent2)

        selected = self.dispatcher.select_best_agent("cleaning.floor.standard")
        assert selected.agent_id == "agent-009"  # Should select lower load

    def test_get_stats(self):
        """测试获取统计信息"""
        agent1 = AgentInfo(
            agent_id="agent-010",
            agent_type="robot",
            capabilities=["cleaning"],
            status="ready",
        )
        agent2 = AgentInfo(
            agent_id="agent-011",
            agent_type="robot",
            capabilities=["cleaning"],
            status="busy",
        )

        self.dispatcher.register_agent(agent1)
        self.dispatcher.register_agent(agent2)

        stats = self.dispatcher.get_stats()
        assert stats["agents"]["total"] == 2
        assert stats["agents"]["ready"] == 1
        assert stats["agents"]["busy"] == 1


class TestTaskDispatcherSingleton:
    """TaskDispatcher 单例测试"""

    def test_get_task_dispatcher_returns_same_instance(self):
        """测试单例返回相同实例"""
        dispatcher1 = get_task_dispatcher()
        dispatcher2 = get_task_dispatcher()
        assert dispatcher1 is dispatcher2

    def test_singleton_has_default_agents(self):
        """测试单例有默认 Agent"""
        dispatcher = get_task_dispatcher()
        assert "robot-001" in dispatcher._agents
        assert "robot-002" in dispatcher._agents
        assert "facility-001" in dispatcher._agents
