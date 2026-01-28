# ECIS 场景模板库

> 版本: 1.0.0 | 更新日期: 2026-01-28

---

## 概述

本目录包含 ECIS 平台 MVP 阶段的 5 个核心场景模板，用于快速创建常见的工作流。

## 模板列表

| 类别 | 模板ID | 名称 | 优先级 |
|------|--------|------|--------|
| cleaning | robot-cleaning-workflow | 机器人清洁工作流 | P0 |
| delivery | robot-delivery-workflow | 机器人配送工作流 | P1 |
| maintenance | emergency-charging-workflow | 紧急充电工作流 | P0 |
| service | visitor-welcome-workflow | 访客迎宾工作流 | P1 |
| security | patrol-inspection-workflow | 巡逻检查工作流 | P2 |

## 目录结构

```
templates/
├── README.md
├── cleaning/
│   └── robot-cleaning-workflow.json
├── delivery/
│   └── robot-delivery-workflow.json
├── maintenance/
│   └── emergency-charging-workflow.json
├── service/
│   └── visitor-welcome-workflow.json
└── security/
    └── patrol-inspection-workflow.json
```

## 使用方式

### 1. API 调用

```bash
# 列出所有模板
GET /api/v1/templates

# 获取单个模板
GET /api/v1/templates/{template_id}

# 基于模板启动工作流
POST /api/v1/workflows/start
{
  "template_id": "robot-cleaning-workflow",
  "input": {
    "robot_id": "robot-001",
    "target_floor": 5,
    "area_id": "zone-a"
  }
}
```

### 2. 可视化设计器

1. 打开工作流设计器
2. 点击「从模板创建」
3. 选择所需模板
4. 填写变量参数
5. 根据需要调整节点
6. 保存并发布

## 模板格式

每个模板包含以下字段：

```json
{
  "template_id": "唯一标识",
  "name": "模板名称",
  "version": "版本号",
  "category": "分类",
  "description": "描述",
  "priority": "优先级 P0/P1/P2",
  "variables": [...],
  "nodes": [...],
  "edges": [...]
}
```

## 变量类型

| 类型 | 说明 | 示例 |
|------|------|------|
| string | 字符串 | "robot-001" |
| number | 数字 | 5 |
| boolean | 布尔值 | true |
| array | 数组 | ["a", "b"] |
| object | 对象 | {"key": "value"} |

## 节点类型

| 类型 | 说明 |
|------|------|
| start | 开始节点 |
| end | 结束节点 |
| task | 任务节点 |
| decision | 决策节点 |
| wait | 等待节点 |
| approval | 审批节点 |
| parallel | 并行节点 |
| subprocess | 子流程节点 |
| notification | 通知节点 |

## 自定义模板

1. 复制现有模板文件
2. 修改 template_id 和 name
3. 根据需要调整节点和边
4. 保存到对应分类目录

---

**文档版本**: 1.0.0
