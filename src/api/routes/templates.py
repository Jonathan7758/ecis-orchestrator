"""
模板 API 路由

提供工作流模板的查询和管理接口
"""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from src.services.template_service import (
    get_template_service,
    TemplateInfo,
    WorkflowTemplate,
    TemplateVariable,
)


router = APIRouter(prefix="/api/v1/templates", tags=["templates"])


class TemplateListResponse(BaseModel):
    """模板列表响应"""
    templates: list[TemplateInfo]
    total: int
    categories: list[str]


class ValidateInputRequest(BaseModel):
    """验证输入请求"""
    input: dict


class ValidateInputResponse(BaseModel):
    """验证输入响应"""
    valid: bool
    errors: list[str]


@router.get("", response_model=TemplateListResponse)
async def list_templates(
    category: Optional[str] = Query(None, description="按分类过滤")
):
    """列出所有工作流模板"""
    service = get_template_service()
    templates = service.list_templates(category)
    categories = service.get_categories()

    return TemplateListResponse(
        templates=templates,
        total=len(templates),
        categories=categories,
    )


@router.get("/categories")
async def list_categories():
    """列出所有模板分类"""
    service = get_template_service()
    return {"categories": service.get_categories()}


@router.get("/{template_id}", response_model=WorkflowTemplate)
async def get_template(template_id: str):
    """获取模板详情"""
    service = get_template_service()
    template = service.get_template(template_id)

    if not template:
        raise HTTPException(status_code=404, detail=f"Template not found: {template_id}")

    return template


@router.get("/{template_id}/variables", response_model=list[TemplateVariable])
async def get_template_variables(template_id: str):
    """获取模板变量列表"""
    service = get_template_service()
    template = service.get_template(template_id)

    if not template:
        raise HTTPException(status_code=404, detail=f"Template not found: {template_id}")

    return template.variables


@router.post("/{template_id}/validate", response_model=ValidateInputResponse)
async def validate_template_input(template_id: str, request: ValidateInputRequest):
    """验证模板输入数据"""
    service = get_template_service()

    valid, errors = service.validate_input(template_id, request.input)

    return ValidateInputResponse(valid=valid, errors=errors)


@router.post("/reload")
async def reload_templates():
    """重新加载所有模板"""
    service = get_template_service()
    count = service.reload_templates()

    return {"message": "Templates reloaded", "count": count}
