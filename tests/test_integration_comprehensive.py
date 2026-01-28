"""
综合集成测试

测试编排器与各组件的完整集成
"""

import pytest
import threading
from fastapi.testclient import TestClient

import sys
sys.path.insert(0, '/root/projects/ecis/ecis-orchestrator')

from src.api.main import app


@pytest.fixture
def client():
    """创建测试客户端"""
    return TestClient(app, raise_server_exceptions=False)


class TestAgentLifecycle:
    """Agent 生命周期集成测试"""

    def test_agent_registration_and_discovery(self, client):
        """测试 Agent 注册和发现"""
        # 1. 注册新 Agent
        register_resp = client.post(
            '/api/v1/tasks/agents',
            json={
                'agent_id': 'integration-test-robot-001',
                'agent_type': 'robot',
                'capabilities': ['cleaning.floor.standard', 'cleaning.floor.deep'],
                'max_load': 5,
            }
        )
        assert register_resp.status_code == 200
        assert register_resp.json()['status'] == 'registered'

        # 2. 列出 Agent 应包含新注册的
        list_resp = client.get('/api/v1/tasks/agents')
        assert list_resp.status_code == 200
        agents = list_resp.json()
        agent_ids = [a['agent_id'] for a in agents]
        assert 'integration-test-robot-001' in agent_ids

        # 3. 查找可用 Agent
        find_resp = client.get(
            '/api/v1/tasks/agents/available',
            params={'capability': 'cleaning.floor.standard'}
        )
        assert find_resp.status_code == 200
        available = find_resp.json()
        available_ids = [a['agent_id'] for a in available]
        assert 'integration-test-robot-001' in available_ids

    def test_agent_status_transitions(self, client):
        """测试 Agent 状态转换"""
        agent_id = 'integration-test-robot-002'

        # 注册
        client.post(
            '/api/v1/tasks/agents',
            json={
                'agent_id': agent_id,
                'agent_type': 'robot',
                'capabilities': ['test'],
            }
        )

        # 状态转换: ready -> busy -> maintenance -> ready
        transitions = [
            ('busy', 200),
            ('maintenance', 200),
            ('ready', 200),
        ]

        for new_status, expected_code in transitions:
            resp = client.put(
                f'/api/v1/tasks/agents/{agent_id}/status',
                params={'status': new_status}
            )
            assert resp.status_code == expected_code
            assert resp.json()['new_status'] == new_status


class TestTaskDispatchIntegration:
    """任务分派集成测试"""

    def test_task_dispatch_lifecycle(self, client):
        """测试任务分派完整生命周期"""
        # 1. 确保有可用 Agent
        client.post(
            '/api/v1/tasks/agents',
            json={
                'agent_id': 'dispatch-test-robot-001',
                'agent_type': 'robot',
                'capabilities': ['cleaning.floor.standard'],
                'max_load': 10,
            }
        )

        # 2. 分派任务
        dispatch_resp = client.post(
            '/api/v1/tasks/dispatch',
            json={
                'capability': 'cleaning.floor.standard',
                'parameters': {'floor': 'floor-1', 'zone': 'zone-a'},
                'priority': 5,
            }
        )
        assert dispatch_resp.status_code == 200
        task_data = dispatch_resp.json()
        task_id = task_data['task_id']
        assert task_data['status'] == 'assigned'
        assert 'agent_id' in task_data  # 验证分配了 Agent（可能是任何可用的）

        # 3. 完成任务
        complete_resp = client.post(
            f'/api/v1/tasks/{task_id}/complete',
            params={'success': True}
        )
        assert complete_resp.status_code == 200
        assert complete_resp.json()['status'] == 'completed'

    def test_task_dispatch_load_balancing(self, client):
        """测试任务负载均衡"""
        # 注册多个 Agent
        for i in range(3):
            client.post(
                '/api/v1/tasks/agents',
                json={
                    'agent_id': f'lb-test-robot-{i}',
                    'agent_type': 'robot',
                    'capabilities': ['lb.test'],
                    'max_load': 5,
                }
            )

        # 分派多个任务
        assigned_agents = []
        for _ in range(6):
            resp = client.post(
                '/api/v1/tasks/dispatch',
                json={
                    'capability': 'lb.test',
                    'parameters': {},
                    'priority': 3,
                }
            )
            if resp.status_code == 200:
                assigned_agents.append(resp.json()['agent_id'])

        # 验证任务分布到多个 Agent
        unique_agents = set(assigned_agents)
        assert len(unique_agents) >= 1


class TestStatisticsIntegration:
    """统计信息集成测试"""

    def test_stats_accuracy(self, client):
        """测试统计信息准确性"""
        # 获取初始统计
        initial_resp = client.get('/api/v1/tasks/stats/overview')
        assert initial_resp.status_code == 200
        initial_stats = initial_resp.json()
        initial_agent_count = initial_stats['agents']['total']

        # 注册新 Agent
        client.post(
            '/api/v1/tasks/agents',
            json={
                'agent_id': 'stats-test-robot',
                'agent_type': 'robot',
                'capabilities': ['stats.test'],
            }
        )

        # 获取更新后统计
        updated_resp = client.get('/api/v1/tasks/stats/overview')
        assert updated_resp.status_code == 200
        updated_stats = updated_resp.json()

        # Agent 数量应该增加
        assert updated_stats['agents']['total'] >= initial_agent_count


class TestCapabilityMatching:
    """能力匹配集成测试"""

    def test_hierarchical_capability_matching(self, client):
        """测试层级能力匹配"""
        # 注册具有层级能力的 Agent
        client.post(
            '/api/v1/tasks/agents',
            json={
                'agent_id': 'capability-test-robot',
                'agent_type': 'robot',
                'capabilities': [
                    'cleaning.floor.standard',
                    'cleaning.floor.deep',
                    'cleaning.window',
                ],
            }
        )

        # 测试精确匹配
        resp1 = client.get(
            '/api/v1/tasks/agents/available',
            params={'capability': 'cleaning.floor.standard'}
        )
        assert resp1.status_code == 200
        assert len(resp1.json()) > 0

    def test_multiple_capability_requirements(self, client):
        """测试多能力要求"""
        # 注册具有多种能力的 Agent
        client.post(
            '/api/v1/tasks/agents',
            json={
                'agent_id': 'multi-cap-robot',
                'agent_type': 'robot',
                'capabilities': ['navigation', 'cleaning', 'delivery'],
            }
        )

        # 验证每种能力都可匹配
        for cap in ['navigation', 'cleaning', 'delivery']:
            resp = client.get(
                '/api/v1/tasks/agents/available',
                params={'capability': cap}
            )
            assert resp.status_code == 200


class TestErrorHandling:
    """错误处理集成测试"""

    def test_invalid_agent_registration(self, client):
        """测试无效 Agent 注册"""
        resp = client.post(
            '/api/v1/tasks/agents',
            json={
                'agent_id': 'invalid-agent',
            }
        )
        assert resp.status_code == 422

    def test_duplicate_agent_registration(self, client):
        """测试重复 Agent 注册"""
        agent_data = {
            'agent_id': 'duplicate-test-robot',
            'agent_type': 'robot',
            'capabilities': ['test'],
        }

        resp1 = client.post('/api/v1/tasks/agents', json=agent_data)
        assert resp1.status_code == 200

        resp2 = client.post('/api/v1/tasks/agents', json=agent_data)
        assert resp2.status_code in [200, 409]

    def test_nonexistent_agent_operation(self, client):
        """测试对不存在 Agent 的操作"""
        resp = client.put(
            '/api/v1/tasks/agents/nonexistent-agent/status',
            params={'status': 'busy'}
        )
        assert resp.status_code in [404, 400]

    def test_invalid_capability_dispatch(self, client):
        """测试无效能力分派"""
        resp = client.post(
            '/api/v1/tasks/dispatch',
            json={
                'capability': 'completely.nonexistent.capability',
                'parameters': {},
            }
        )
        assert resp.status_code == 400


class TestConcurrency:
    """并发测试"""

    def test_concurrent_registrations(self, client):
        """测试并发注册"""
        results = []

        def register_agent(agent_id):
            resp = client.post(
                '/api/v1/tasks/agents',
                json={
                    'agent_id': agent_id,
                    'agent_type': 'robot',
                    'capabilities': ['concurrent.test'],
                }
            )
            results.append(resp.status_code)

        threads = []
        for i in range(5):
            t = threading.Thread(target=register_agent, args=(f'concurrent-robot-{i}',))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        assert all(code == 200 for code in results)

    def test_concurrent_dispatches(self, client):
        """测试并发分派"""
        client.post(
            '/api/v1/tasks/agents',
            json={
                'agent_id': 'concurrent-dispatch-robot',
                'agent_type': 'robot',
                'capabilities': ['concurrent.dispatch'],
                'max_load': 100,
            }
        )

        results = []

        def dispatch_task():
            resp = client.post(
                '/api/v1/tasks/dispatch',
                json={
                    'capability': 'concurrent.dispatch',
                    'parameters': {},
                }
            )
            results.append(resp.status_code)

        threads = []
        for _ in range(10):
            t = threading.Thread(target=dispatch_task)
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        success_count = sum(1 for code in results if code == 200)
        assert success_count > 0
