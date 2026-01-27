# ECIS Orchestrator - Claude 开发指南

> 此文件由 Claude Code 自动读取，作为项目上下文。

---

## 快速状态 (Quick Status)

| 项目 | 值 |
|------|-----|
| **当前阶段** | Task 7 - 编排器后端 |
| **当前模块** | Week 1 基础设施 |
| **进度** | 40% (core, activities, workflows, workers, api 完成) |
| **阻塞问题** | 无 |
| **最后更新** | 2026-01-27 |

### 当前任务上下文

```
已完成内容:
  - 项目结构创建
  - pyproject.toml 依赖配置
  - docker-compose.yaml (Temporal, PostgreSQL, Redis)
  - core 模块 (config, exceptions, database)
  - activities 模块 (robot, facility, notification, llm)
  - workflows 模块 (cleaning, approval)
  - workers 模块 (main_worker)
  - api 模块 (routes/workflows, routes/approvals)
  - 24 个单元测试全部通过

待完成:
  - 启动 Docker 环境
  - 集成测试
  - Federation 模块
  - services 模块完善
```

---

## 项目概述

| 项目 | 值 |
|------|-----|
| 项目名称 | ecis-orchestrator |
| 项目路径 | `/root/projects/ecis/ecis-orchestrator` |
| 后端端口 | 8200 |
| Temporal 端口 | 7233 (gRPC), 8233 (Web UI) |

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
| activities/ | ✅ 已完成 | robot, facility, notification, llm |
| workflows/ | ✅ 已完成 | cleaning, approval |
| workers/ | ✅ 已完成 | main_worker |
| api/ | ✅ 已完成 | routes/workflows, routes/approvals |
| services/ | ⬜ 待开发 | 业务服务层 |
| federation/ | ⬜ 待开发 | Federation 集成 |
| models/ | ⬜ 待开发 | 数据库模型 |

状态图例：⬜ 待开发 | 🔄 开发中 | ✅ 已完成 | ⚠️ 需修复

---

## 常用命令

```bash
# 激活虚拟环境
cd /root/projects/ecis/ecis-orchestrator
source venv/bin/activate

# 启动开发环境
docker-compose up -d

# 启动 Temporal Worker
python -m src.workers.main_worker

# 启动 API 服务
uvicorn src.api.main:app --reload --port 8200

# 运行测试
pytest tests/ -v

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
│   │   ├── robot.py          ✅
│   │   ├── facility.py       ✅
│   │   ├── notification.py   ✅
│   │   └── llm.py            ✅
│   ├── workflows/
│   │   ├── __init__.py
│   │   ├── cleaning.py       ✅
│   │   └── approval.py       ✅
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
│   ├── services/             ⬜
│   ├── models/               ⬜
│   └── federation/           ⬜
└── tests/
    ├── __init__.py
    ├── test_core.py          ✅ (11 tests)
    └── test_activities_unit.py ✅ (13 tests)
```

---

## 下一步

1. 启动 Docker 环境 (Temporal, PostgreSQL, Redis)
2. 实现 services 模块
3. 实现 federation 模块
4. 添加集成测试
5. Git 提交
