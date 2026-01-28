"""
模板服务测试
"""

import pytest
from fastapi.testclient import TestClient

import sys
sys.path.insert(0, '/root/projects/ecis/ecis-orchestrator')

from src.api.main import app
from src.services.template_service import TemplateService, get_template_service


@pytest.fixture
def client():
    """创建测试客户端"""
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def template_service():
    """创建模板服务实例"""
    return get_template_service()


class TestTemplateService:
    """模板服务单元测试"""

    def test_load_templates(self, template_service):
        """测试加载模板"""
        templates = template_service.list_templates()
        assert len(templates) == 5

    def test_list_templates_by_category(self, template_service):
        """测试按分类过滤"""
        cleaning = template_service.list_templates(category="cleaning")
        assert len(cleaning) == 1
        assert cleaning[0].template_id == "robot-cleaning-workflow"

    def test_get_template(self, template_service):
        """测试获取模板详情"""
        template = template_service.get_template("robot-cleaning-workflow")
        assert template is not None
        assert template.name == "机器人清洁工作流"
        assert template.category == "cleaning"
        assert len(template.nodes) > 0
        assert len(template.edges) > 0

    def test_get_nonexistent_template(self, template_service):
        """测试获取不存在的模板"""
        template = template_service.get_template("nonexistent")
        assert template is None

    def test_get_categories(self, template_service):
        """测试获取分类列表"""
        categories = template_service.get_categories()
        assert "cleaning" in categories
        assert "delivery" in categories
        assert "maintenance" in categories
        assert "service" in categories
        assert "security" in categories

    def test_get_template_variables(self, template_service):
        """测试获取模板变量"""
        variables = template_service.get_template_variables("robot-cleaning-workflow")
        assert len(variables) > 0

        var_names = [v.name for v in variables]
        assert "robot_id" in var_names
        assert "target_floor" in var_names
        assert "area_id" in var_names

    def test_validate_input_valid(self, template_service):
        """测试验证有效输入"""
        valid, errors = template_service.validate_input(
            "robot-cleaning-workflow",
            {
                "robot_id": "robot-001",
                "target_floor": 5,
                "area_id": "zone-a",
            }
        )
        assert valid is True
        assert len(errors) == 0

    def test_validate_input_missing_required(self, template_service):
        """测试验证缺少必填字段"""
        valid, errors = template_service.validate_input(
            "robot-cleaning-workflow",
            {
                "robot_id": "robot-001",
                # 缺少 target_floor 和 area_id
            }
        )
        assert valid is False
        assert len(errors) > 0

    def test_validate_input_invalid_enum(self, template_service):
        """测试验证无效枚举值"""
        valid, errors = template_service.validate_input(
            "robot-cleaning-workflow",
            {
                "robot_id": "robot-001",
                "target_floor": 5,
                "area_id": "zone-a",
                "cleaning_type": "invalid_type",  # 无效值
            }
        )
        assert valid is False
        assert any("cleaning_type" in e for e in errors)


class TestTemplateAPI:
    """模板 API 集成测试"""

    def test_list_templates(self, client):
        """测试列出模板"""
        response = client.get("/api/v1/templates")
        assert response.status_code == 200

        data = response.json()
        assert "templates" in data
        assert "total" in data
        assert "categories" in data
        assert data["total"] == 5

    def test_list_templates_by_category(self, client):
        """测试按分类过滤"""
        response = client.get("/api/v1/templates?category=cleaning")
        assert response.status_code == 200

        data = response.json()
        assert data["total"] == 1
        assert data["templates"][0]["category"] == "cleaning"

    def test_get_categories(self, client):
        """测试获取分类"""
        response = client.get("/api/v1/templates/categories")
        assert response.status_code == 200

        data = response.json()
        assert "categories" in data
        assert len(data["categories"]) == 5

    def test_get_template(self, client):
        """测试获取模板详情"""
        response = client.get("/api/v1/templates/robot-cleaning-workflow")
        assert response.status_code == 200

        data = response.json()
        assert data["template_id"] == "robot-cleaning-workflow"
        assert data["name"] == "机器人清洁工作流"
        assert "nodes" in data
        assert "edges" in data
        assert "variables" in data

    def test_get_nonexistent_template(self, client):
        """测试获取不存在的模板"""
        response = client.get("/api/v1/templates/nonexistent")
        assert response.status_code == 404

    def test_get_template_variables(self, client):
        """测试获取模板变量"""
        response = client.get("/api/v1/templates/robot-cleaning-workflow/variables")
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0

    def test_validate_template_input(self, client):
        """测试验证模板输入"""
        response = client.post(
            "/api/v1/templates/robot-cleaning-workflow/validate",
            json={
                "input": {
                    "robot_id": "robot-001",
                    "target_floor": 5,
                    "area_id": "zone-a",
                }
            }
        )
        assert response.status_code == 200

        data = response.json()
        assert data["valid"] is True
        assert len(data["errors"]) == 0

    def test_validate_template_input_invalid(self, client):
        """测试验证无效输入"""
        response = client.post(
            "/api/v1/templates/robot-cleaning-workflow/validate",
            json={
                "input": {
                    "robot_id": "robot-001",
                    # 缺少必填字段
                }
            }
        )
        assert response.status_code == 200

        data = response.json()
        assert data["valid"] is False
        assert len(data["errors"]) > 0

    def test_reload_templates(self, client):
        """测试重新加载模板"""
        response = client.post("/api/v1/templates/reload")
        assert response.status_code == 200

        data = response.json()
        assert data["count"] == 5
