# ECIS Orchestrator - Claude 开发指南

> 此文件由 Claude Code 自动读取，作为项目上下文。

---

## 快速状态 (Quick Status)

| 项目 | 值 |
|------|-----|
| **当前阶段** | Task 7 - 编排器后端 |
| **当前模块** | Week 1 基础设施 ✅ |
| **进度** | 100% (所有核心模块完成) |
| **阻塞问题** | 无 |
| **最后更新** | 2026-01-27 |

### 当前任务上下文

```
已完成内容:
  - 项目结构创建
  - pyproject.toml 依赖配置
  - docker-compose.yaml (Temporal, PostgreSQL, Redis)
  - core 模块 (config, exceptions, database)
  - activities 模块 (robot, facility, notification, llm) - 23个Activity
  - workflows 模块 (cleaning, approval, delivery, scheduled) - 6个Workflow
  - workers 模块 (main_worker)
  - api 模块 (routes/workflows, approvals, delivery, tasks)
  - services 模块 (workflow_service, task_dispatcher)
  - federation 模块 (federation_client)
  - models 模块 (workflow, agent)
  - Docker 环境启动成功 (Temporal, PostgreSQL, Redis)
  - 52 个单元测试全部通过
  - 2 个端到端测试通过 (需要Docker环境运行)

Git 提交:
  - 7a122f4 feat(orchestrator): initial project setup with Temporal workflows
  - 917939a feat(orchestrator): add e2e tests and fix port conflicts
  - 13e629f feat(orchestrator): add services, federation, and models modules
  - 14576c7 feat(orchestrator): add delivery and scheduled workflows with API routes

待完成:
  - 集成测试完善
  - 部署文档
```

---

## 项目概述

| 项目 | 值 |
|------|-----|
| 项目名称 | ecis-orchestrator |
| 项目路径 | `/root/projects/ecis/ecis-orchestrator` |
| 后端端口 | 8200 |
| Temporal 端口 | 7233 (gRPC), 8233 (Web UI) |
| PostgreSQL 端口 | 5434 |
| Redis 端口 | 6380 |

## 技术栈

| 组件 | 技术 | 说明 |
|------|------|------|
| 语言 | Python 3.11+ | 后端开发 |
| 工作流引擎 | Temporal | 核心编排 |
| Web 框架 | FastAPI | API 服务 |
| 数据库 | PostgreSQL | 业务数据 |
| 缓存 | Redis | 状态缓存 |
| LLM | Claude API | 智能决策 |

---

## 模块状态

| 模块 | 状态 | 说明 |
|------|------|------|
| core/ | ✅ 已完成 | 配置、数据库、异常 |
| activities/ | ✅ 已完成 | robot(6), facility(7), notification(6), llm(4) = 23个 |
| workflows/ | ✅ 已完成 | cleaning, approval, delivery, scheduled = 6个 |
| workers/ | ✅ 已完成 | main_worker |
| api/ | ✅ 已完成 | routes/workflows, approvals, delivery, tasks |
| services/ | ✅ 已完成 | workflow_service, task_dispatcher |
| federation/ | ✅ 已完成 | federation_client |
| models/ | ✅ 已完成 | workflow, agent |
| tests/ | ✅ 已完成 | 52单元测试 + 2端到端测试 |

状态图例：⬜ 待开发 | 🔄 开发中 | ✅ 已完成 | ⚠️ 需修复

---

## 工作流列表

| 工作流 | 说明 | 信号 |
|--------|------|------|
| RobotCleaningWorkflow | 机器人清洁任务 | - |
| ApprovalWorkflow | 单级审批 | approve, reject, cancel |
| MultiStageApprovalWorkflow | 多级审批 | approve, reject |
| DeliveryWorkflow | 物品配送 | confirm_pickup, confirm_delivery, cancel_delivery |
| ScheduledCleaningWorkflow | 定时清洁 | cancel_schedule, skip_location |
| ScheduledPatrolWorkflow | 定时巡检 | cancel_patrol, report_anomaly |

---

## API 端点

### Workflows
- POST /api/v1/workflows/cleaning - 启动清洁工作流
- GET /api/v1/workflows/{id} - 获取工作流状态
- POST /api/v1/workflows/{id}/cancel - 取消工作流

### Approvals
- POST /api/v1/approvals - 创建审批
- GET /api/v1/approvals/{id} - 获取审批状态
- POST /api/v1/approvals/{id}/approve - 批准
- POST /api/v1/approvals/{id}/reject - 拒绝

### Delivery
- POST /api/v1/delivery - 启动配送
- GET /api/v1/delivery/{id} - 获取配送状态
- POST /api/v1/delivery/{id}/confirm-pickup - 确认取货
- POST /api/v1/delivery/{id}/confirm-delivery - 确认送达
- POST /api/v1/delivery/{id}/cancel - 取消配送

### Tasks
- GET /api/v1/tasks/agents - 列出所有Agent
- POST /api/v1/tasks/agents - 注册Agent
- POST /api/v1/tasks/dispatch - 分派任务
- GET /api/v1/tasks/{id} - 获取任务状态
- GET /api/v1/tasks/stats/overview - 统计信息

---

## 常用命令

```bash
# 激活虚拟环境
cd /root/projects/ecis/ecis-orchestrator
source venv/bin/activate

# 启动开发环境
docker compose up -d

# 启动 Temporal Worker
python -m src.workers.main_worker

# 启动 API 服务
uvicorn src.api.main:app --reload --port 8200

# 运行单元测试
pytest tests/ -v --ignore=tests/test_e2e.py

# 运行端到端测试（需要先启动Worker）
python tests/test_e2e.py

# 访问 Temporal Web UI
open http://localhost:8233
```

---

## 文件清单

```
ecis-orchestrator/
├── pyproject.toml
├── docker-compose.yaml
├── init-db.sql
├── temporal-config/
│   └── development.yaml
├── src/
│   ├── __init__.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py         ✅
│   │   ├── database.py       ✅
│   │   └── exceptions.py     ✅
│   ├── activities/
│   │   ├── __init__.py
│   │   ├── robot.py          ✅ (6 activities)
│   │   ├── facility.py       ✅ (7 activities)
│   │   ├── notification.py   ✅ (6 activities)
│   │   └── llm.py            ✅ (4 activities)
│   ├── workflows/
│   │   ├── __init__.py
│   │   ├── cleaning.py       ✅ (RobotCleaningWorkflow)
│   │   ├── approval.py       ✅ (ApprovalWorkflow, MultiStageApprovalWorkflow)
│   │   ├── delivery.py       ✅ (DeliveryWorkflow)
│   │   └── scheduled.py      ✅ (ScheduledCleaningWorkflow, ScheduledPatrolWorkflow)
│   ├── workers/
│   │   ├── __init__.py
│   │   └── main_worker.py    ✅
│   ├── api/
│   │   ├── __init__.py
│   │   ├── main.py           ✅
│   │   └── routes/
│   │       ├── __init__.py
│   │       ├── workflows.py  ✅
│   │       ├── approvals.py  ✅
│   │       ├── delivery.py   ✅
│   │       └── tasks.py      ✅
│   ├── services/
│   │   ├── __init__.py       ✅
│   │   ├── workflow_service.py ✅
│   │   └── task_dispatcher.py  ✅
│   ├── federation/
│   │   ├── __init__.py       ✅
│   │   └── federation_client.py ✅
│   └── models/
│       ├── __init__.py       ✅
│       ├── base.py           ✅
│       ├── workflow.py       ✅
│       └── agent.py          ✅
└── tests/
    ├── __init__.py
    ├── test_core.py          ✅ (11 tests)
    ├── test_activities_unit.py ✅ (13 tests)
    ├── test_services.py      ✅ (10 tests)
    ├── test_models.py        ✅ (11 tests)
    ├── test_federation.py    ✅ (7 tests)
    └── test_e2e.py           ✅ (2 e2e tests)
```
