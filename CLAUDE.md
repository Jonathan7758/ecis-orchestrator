# ECIS Orchestrator - Claude 开发指南

> 此文件由 Claude Code 自动读取，作为项目上下文。

---

## 快速状态 (Quick Status)

| 项目 | 值 |
|------|-----|
| **当前阶段** | Task 7 - 编排器后端 |
| **当前模块** | Week 1 基础设施 ✅ |
| **进度** | 80% (core, activities, workflows, workers, api, services, federation, models 完成) |
| **阻塞问题** | 无 |
| **最后更新** | 2026-01-27 |

### 当前任务上下文

```
已完成内容:
  - 项目结构创建
  - pyproject.toml 依赖配置
  - docker-compose.yaml (Temporal, PostgreSQL, Redis)
  - core 模块 (config, exceptions, database)
  - activities 模块 (robot, facility, notification, llm) - 21个Activity
  - workflows 模块 (cleaning, approval) - 3个Workflow
  - workers 模块 (main_worker)
  - api 模块 (routes/workflows, routes/approvals)
  - services 模块 (workflow_service, task_dispatcher)
  - federation 模块 (federation_client)
  - models 模块 (workflow, agent)
  - Docker 环境启动成功 (Temporal, PostgreSQL, Redis)
  - 52 个单元测试全部通过
  - 2 个端到端测试全部通过 (cleaning, approval workflows)

Git 提交:
  - 7a122f4 feat(orchestrator): initial project setup with Temporal workflows
  - 917939a feat(orchestrator): add e2e tests and fix port conflicts
  - 24405d8 feat(orchestrator): add services, federation, and models modules

待完成:
  - 更多工作流 (delivery, scheduled)
  - 完善 API 端点
  - 集成测试
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
| activities/ | ✅ 已完成 | robot, facility, notification, llm (21个) |
| workflows/ | ✅ 已完成 | cleaning, approval (3个) |
| workers/ | ✅ 已完成 | main_worker |
| api/ | ✅ 已完成 | routes/workflows, routes/approvals |
| services/ | ✅ 已完成 | workflow_service, task_dispatcher |
| federation/ | ✅ 已完成 | federation_client |
| models/ | ✅ 已完成 | workflow, agent |
| tests/ | ✅ 已完成 | 52单元测试 + 2端到端测试 |

状态图例：⬜ 待开发 | 🔄 开发中 | ✅ 已完成 | ⚠️ 需修复

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
pytest tests/test_core.py tests/test_activities_unit.py tests/test_services.py tests/test_models.py tests/test_federation.py -v

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
│   │   ├── robot.py          ✅ (5 activities)
│   │   ├── facility.py       ✅ (7 activities)
│   │   ├── notification.py   ✅ (5 activities)
│   │   └── llm.py            ✅ (4 activities)
│   ├── workflows/
│   │   ├── __init__.py
│   │   ├── cleaning.py       ✅ (RobotCleaningWorkflow)
│   │   └── approval.py       ✅ (ApprovalWorkflow, MultiStageApprovalWorkflow)
│   ├── workers/
│   │   ├── __init__.py
│   │   └── main_worker.py    ✅
│   ├── api/
│   │   ├── __init__.py
│   │   ├── main.py           ✅
│   │   └── routes/
│   │       ├── __init__.py
│   │       ├── workflows.py  ✅
│   │       └── approvals.py  ✅
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

---

## 下一步

1. 添加更多工作流 (delivery, scheduled)
2. 完善 API 端点 (tasks, agents)
3. 添加集成测试
4. 部署文档
