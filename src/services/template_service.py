"""
模板服务

提供工作流模板的加载、查询和管理功能
"""

import json
import os
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel


class TemplateVariable(BaseModel):
    """模板变量"""
    name: str
    type: str
    required: bool = False
    default: Optional[Any] = None
    label: str = ""
    description: str = ""
    enum: Optional[list] = None


class TemplateNode(BaseModel):
    """模板节点"""
    id: str
    type: str
    name: str
    position: dict
    config: dict = {}


class TemplateEdge(BaseModel):
    """模板边"""
    id: str
    source: str
    target: str
    label: str = ""


class WorkflowTemplate(BaseModel):
    """工作流模板"""
    template_id: str
    name: str
    version: str
    category: str
    description: str
    priority: str = "P2"
    estimated_duration: str = ""
    involved_systems: list = []
    trigger_condition: str = ""
    variables: list[TemplateVariable] = []
    nodes: list[TemplateNode] = []
    edges: list[TemplateEdge] = []


class TemplateInfo(BaseModel):
    """模板简要信息"""
    template_id: str
    name: str
    version: str
    category: str
    description: str
    priority: str
    variable_count: int
    node_count: int


class TemplateService:
    """模板服务"""

    def __init__(self, templates_dir: str = None):
        if templates_dir is None:
            # 默认模板目录
            self.templates_dir = Path(__file__).parent.parent.parent / "templates"
        else:
            self.templates_dir = Path(templates_dir)

        self._templates: dict[str, WorkflowTemplate] = {}
        self._load_templates()

    def _load_templates(self) -> None:
        """加载所有模板"""
        if not self.templates_dir.exists():
            return

        for category_dir in self.templates_dir.iterdir():
            if category_dir.is_dir() and not category_dir.name.startswith('.'):
                for template_file in category_dir.glob("*.json"):
                    try:
                        self._load_template_file(template_file)
                    except Exception as e:
                        print(f"Failed to load template {template_file}: {e}")

    def _load_template_file(self, file_path: Path) -> None:
        """加载单个模板文件"""
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # 移除 $schema 字段（如果存在）
        data.pop('$schema', None)

        template = WorkflowTemplate(**data)
        self._templates[template.template_id] = template

    def list_templates(self, category: str = None) -> list[TemplateInfo]:
        """列出所有模板"""
        templates = []
        for template in self._templates.values():
            if category and template.category != category:
                continue
            templates.append(TemplateInfo(
                template_id=template.template_id,
                name=template.name,
                version=template.version,
                category=template.category,
                description=template.description,
                priority=template.priority,
                variable_count=len(template.variables),
                node_count=len(template.nodes),
            ))
        return templates

    def get_template(self, template_id: str) -> Optional[WorkflowTemplate]:
        """获取模板详情"""
        return self._templates.get(template_id)

    def get_template_variables(self, template_id: str) -> list[TemplateVariable]:
        """获取模板变量列表"""
        template = self.get_template(template_id)
        if template:
            return template.variables
        return []

    def get_categories(self) -> list[str]:
        """获取所有分类"""
        categories = set()
        for template in self._templates.values():
            categories.add(template.category)
        return sorted(list(categories))

    def reload_templates(self) -> int:
        """重新加载所有模板"""
        self._templates.clear()
        self._load_templates()
        return len(self._templates)

    def validate_input(self, template_id: str, input_data: dict) -> tuple[bool, list[str]]:
        """验证输入数据是否满足模板变量要求"""
        template = self.get_template(template_id)
        if not template:
            return False, [f"Template not found: {template_id}"]

        errors = []
        for var in template.variables:
            if var.required and var.name not in input_data:
                errors.append(f"Missing required variable: {var.name}")

            if var.name in input_data and var.enum:
                if input_data[var.name] not in var.enum:
                    errors.append(f"Invalid value for {var.name}: must be one of {var.enum}")

        return len(errors) == 0, errors


# 全局单例
_template_service: Optional[TemplateService] = None


def get_template_service() -> TemplateService:
    """获取模板服务单例"""
    global _template_service
    if _template_service is None:
        _template_service = TemplateService()
    return _template_service
