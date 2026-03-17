# ECIS 平台 — Claude Code 开发指南 v3

> 版本: 3.0 | 日期: 2026-02-24
> 基于: ECIS架构v6（七层架构 + 知识层）
> 适用仓库: ecis-service-robot, ecis-orchestrator, ecis-federation, ecis-protocols

---

## 快速状态 (Quick Status)

| 项目 | 值 |
|------|-----|
| **当前阶段** | 阶段一优化迭代（88%→95%+） |
| **MVP状态** | ✅ 已完成（511测试通过） |
| **当前目标** | Tower C生产部署（20机器人/10用户） |
| **迭代内容** | A类补缺口 + B类前瞻性设计 + C类接口预留 |
| **开发者数量** | 2人（5周开发周期） |
| **最后更新** | 2026-03-03 |

---

## 项目概述

ECIS（企业群体智能系统）编排平台，实现人机协同的物业管理智能化。

### 技术栈

```
后端: Python 3.11+ / FastAPI / Temporal / Claude API
前端: React 18 / TypeScript / TailwindCSS 3.4 / React Flow
数据: PostgreSQL 15+ / Redis 7+ / TimescaleDB（决策日志）
部署: Docker Compose（阶段一）→ K8s（阶段二）
监控: Prometheus / Grafana / Loki
```

### 仓库清单

| 仓库 | 说明 | 开发端口 |
|------|------|---------|
| ecis-protocols | 共享协议和数据模型 | — |
| ecis-service-robot | 服务机器人子系统（MVP已完成） | 8100 |
| ecis-orchestrator | 统一编排平台 | 8300(API), 3000(前端) |
| ecis-federation | 联邦网关 | 8200 |
| ecis-human-agent | 人员管理 | 8400 |
| ecis-property-facility | 设施管理 | 8500 |

---

## 七层架构速查

```
L5 前端层    → T1-T4, O1-O4, E1-E3, P1-P3（三端+移动端）
L4 API网关   → G1-G7(原有) + G8知识API + G9规则API + WebSocket/SSE端点
L3 Agent层   → A1运行时 + A2清洁调度 + A3对话 + A4采集 + A5决策校验(新)
L2.5 知识层  → K1场景知识库 + K2治理规则库 + K3决策日志库（新增层）
L2 数据平台  → D1采集引擎(增强) + D2存储(增强) + D3查询API
L1 MCP服务   → M1空间 + M2任务 + M3高仙(增强) + M4科沃斯(增强)
L0 基础设施  → F1数据模型(扩展) + F2工具 + F3配置(扩展) + F4认证 + F5事件总线抽象(新)
```

---

## 当前迭代模块清单

### P0 优先级（Tower C上线前必须完成）

| 编号 | 模块 | 工程量 | 影响仓库 | 状态 |
|------|------|--------|---------|------|
| A1 | 实时事件通道（WebSocket） | 3-4天 | ecis-service-robot | ✅ 已完成 |
| A2 | LLM决策校验层 | 2-3天 | ecis-service-robot | ✅ 已完成 |
| A3 | 场景知识库K1 | 3-4天 | ecis-service-robot, ecis-protocols | ⬜ 待开发 |
| B1 | 决策上下文日志K3 | 2-3天 | ecis-service-robot, ecis-protocols | ⬜ 待开发 |

### P1 优先级（Tower C运营首月内完成）

| 编号 | 模块 | 工程量 | 影响仓库 | 状态 |
|------|------|--------|---------|------|
| A4 | 移动端弱网离线支持 | 3-4天 | ecis-service-robot | ⬜ 待开发 |
| B2 | 事件Schema扩展 | 1天 | ecis-protocols | ⬜ 待开发 |
| B4 | 治理规则框架K2 | 2-3天 | ecis-service-robot, ecis-protocols | ⬜ 待开发 |
| B5 | Human Agent决策边界 | 1-2天 | ecis-human-agent | ⬜ 待开发 |
| C3 | 事件总线抽象层F5 | 1天 | ecis-federation | ⬜ 待开发 |

### P2 优先级（Tower C运营稳定后）

| 编号 | 模块 | 工程量 | 影响仓库 | 状态 |
|------|------|--------|---------|------|
| B3 | 能力模型A2A兼容 | 0.5天 | ecis-protocols | ⬜ 待开发 |
| C1 | 对话式入口预留 | 0.5天 | ecis-orchestrator | ⬜ 待开发 |
| C2 | 联邦客户端预留 | 0.5天 | 各子系统 | ⬜ 待开发 |

---

## 开发规范

### 目录结构约定

```
ecis-{subsystem}/
├── CLAUDE.md                # 本文件（每个仓库一份）
├── README.md
├── docker-compose.yml
├── pyproject.toml
├── src/
│   ├── __init__.py
│   ├── agents/              # L3: Agent实现
│   ├── adapters/            # L1: 外部API适配器
│   ├── knowledge/           # L2.5: 知识层客户端（新增）
│   ├── validation/          # L3: 决策校验（新增）
│   ├── services/            # 业务服务
│   ├── api/                 # L4: FastAPI路由
│   ├── models/              # L0: 数据模型
│   ├── event_bus/           # L0: 事件总线
│   └── config/              # L0: 配置管理
├── tests/
│   ├── unit/                # 单元测试
│   ├── integration/         # 集成测试
│   └── e2e/                 # 端到端测试
├── migrations/              # 数据库迁移
└── docs/                    # 模块文档
```

### 代码规范

```python
# 1. 所有模型使用Pydantic v2
from pydantic import BaseModel, Field

# 2. 异步优先
async def create_task(task: TaskCreate) -> Task: ...

# 3. Protocol定义接口（非ABC）
from typing import Protocol
class DecisionValidatorInterface(Protocol):
    async def validate(self, decision: dict, context: DecisionContext) -> ValidationResult: ...

# 4. 依赖注入
from fastapi import Depends
def get_knowledge_client() -> ScenarioKBClient:
    return ScenarioKBClient(settings.knowledge_db_url)

# 5. 结构化日志
import structlog
logger = structlog.get_logger()
logger.info("decision_validated", agent_id=agent_id, valid=result.valid)
```

### 测试规范

```python
# 1. 命名: test_{模块}_{场景}_{预期结果}
def test_decision_validator_invalid_robot_id_returns_error(): ...

# 2. 使用pytest + pytest-asyncio
@pytest.mark.asyncio
async def test_realtime_client_reconnect_on_disconnect(): ...

# 3. Fixture层级: conftest.py按目录组织
# tests/conftest.py          → 全局fixture（db, redis）
# tests/unit/conftest.py     → 单元测试fixture（mock clients）
# tests/integration/conftest.py → 集成测试fixture（真实服务）

# 4. 覆盖率目标: ≥80%，核心路径100%
```

---

## 常用命令

```bash
# 环境启动
docker-compose up -d                       # 启动所有依赖服务
uvicorn src.api.main:app --reload --port 8100  # 启动API

# 测试
pytest tests/unit/ -v                      # 单元测试
pytest tests/integration/ -v               # 集成测试
pytest tests/ -v --cov=src --cov-report=term-missing  # 带覆盖率

# 数据库
alembic upgrade head                       # 执行迁移
alembic revision --autogenerate -m "desc"  # 生成迁移

# 代码质量
ruff check src/                            # lint
ruff format src/                           # format
mypy src/                                  # 类型检查
```

---

## 关键接口速查

### 数据模型（ecis-protocols）

```python
# 核心模型位置: ecis-protocols/src/models/

# 决策相关（v1.3新增）
DecisionContext      # 决策输入上下文
DecisionOutcome      # 决策效果记录  
DecisionRecord       # Context + Decision + Outcome 三元组

# 知识层相关（v1.3新增）
ScenarioKnowledge    # 场景知识条目
PromptTemplate       # Prompt模板
GovernanceRule       # 治理规则

# 事件扩展（v1.3新增）
EventV2              # 增加 source_node_id, causal_chain 等跨节点字段

# 自主性标记（v1.3新增）
AutonomyLevel        # L0-L4 自主性层级
TaskAutonomyConfig   # 任务自主性配置
```

### MCP Server接口

```python
# M3/M4 新增实时通道
RobotMCPRealtimeInterface:
  connect_realtime(robot_id) -> WebSocketConnection
  subscribe_events(robot_id, event_types) -> Subscription

# 原有接口保持不变
RobotMCPInterface:
  get_robot_status(robot_id) -> RobotStatus
  send_task(robot_id, task) -> TaskResult
  list_robots() -> List[Robot]
```

### 决策管道接口

```python
# A5 DecisionValidator
DecisionValidatorInterface:
  validate(decision, context) -> ValidationResult

# K1 场景知识库
ScenarioKBInterface:
  get_applicable_knowledge(scenario_category, conditions) -> List[ScenarioKnowledge]
  get_prompt_template(agent_type, scenario) -> PromptTemplate
  record_knowledge_usage(knowledge_id, decision_id) -> None

# K2 治理规则库  
GovernanceRuleInterface:
  get_active_rules(scope, context) -> List[GovernanceRule]
  evaluate_rules(rules, decision) -> RuleEvaluationResult

# K3 决策日志
DecisionLogInterface:
  log_decision(record: DecisionRecord) -> str
  update_outcome(decision_id, outcome: DecisionOutcome) -> None
  query_decisions(filters) -> List[DecisionRecord]
```

---

## 模块开发会话模式

每个Claude Code会话应专注于单个模块。推荐会话流程：

### 会话开始

```
1. 阅读本CLAUDE.md了解全局上下文
2. 阅读目标模块的规格书（docs/目录下对应文件）
3. 检查依赖模块的接口定义（ecis-protocols）
4. 确认当前模块状态（上表中的状态列）
```

### 开发流程

```
1. 先写接口定义（Protocol类）
2. 写测试（pytest，先写失败用例）
3. 实现功能代码
4. 运行测试确认通过
5. 更新本CLAUDE.md中的模块状态
```

### 会话结束

```
1. 确认所有测试通过
2. 更新CLAUDE.md模块状态（⬜→🔧→✅）
3. 记录关键决策到 docs/DECISIONS.md
4. 如有遗留问题记录到 docs/TODO.md
```

---

## 依赖关系图（开发顺序）

```
ecis-protocols（先行）
  ├── F1数据模型扩展 ← 所有模块依赖
  ├── B2事件Schema扩展
  └── B3能力模型扩展

ecis-service-robot（核心）
  ├── A1实时事件通道 ← 依赖M3/M4适配器改造
  ├── A2决策校验层   ← 依赖F1数据模型
  ├── A3场景知识库K1 ← 依赖F1数据模型
  ├── B1决策日志K3   ← 依赖F1数据模型 + A2
  ├── B4治理规则K2   ← 依赖F1数据模型
  └── A4弱网离线     ← 独立（前端改造）

ecis-federation
  └── C3事件总线抽象 ← 独立

ecis-human-agent
  └── B5决策边界     ← 依赖F1数据模型
```

**推荐开发顺序**:

```
Sprint 1 (Week 1-2): ecis-protocols扩展 → A1实时通道 → A2决策校验
Sprint 2 (Week 2-3): A3场景知识库 → B1决策日志 → B4治理规则
Sprint 3 (Week 3-4): A4弱网离线 → C3事件总线 → B5决策边界
Sprint 4 (Week 4-5): 集成测试 → 性能优化 → Tower C部署
```

---

## 环境配置

### 开发环境（远程云服务器）

```yaml
# docker-compose.dev.yml
services:
  postgres:
    image: timescale/timescaledb:latest-pg15
    ports: ["5432:5432"]
    environment:
      POSTGRES_DB: ecis_dev
      POSTGRES_PASSWORD: dev_password
    volumes:
      - pgdata:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]

  temporal:
    image: temporalio/auto-setup:latest
    ports: ["7233:7233", "8233:8233"]
    depends_on: [postgres]

# 环境变量
# .env.development
DATABASE_URL=postgresql://postgres:dev_password@localhost:5432/ecis_dev
REDIS_URL=redis://localhost:6379
TEMPORAL_HOST=localhost:7233
CLAUDE_API_KEY=sk-ant-xxx
LOG_LEVEL=DEBUG
```

### 远程开发连接

```bash
# 本地电脑通过SSH连接云端服务器
ssh -L 8100:localhost:8100 -L 3000:localhost:3000 -L 8233:localhost:8233 user@cloud-server

# Claude Code在云端服务器上运行
# 本地浏览器访问:
#   http://localhost:8100/docs    → API文档
#   http://localhost:3000         → 前端
#   http://localhost:8233         → Temporal Web UI
```

---

## 故障排查

| 问题 | 排查步骤 |
|------|---------|
| MCP Server连接失败 | 检查机器人API VPN连接 → 检查M3/M4适配器日志 |
| LLM决策异常 | 查看K3决策日志 → 检查A5校验结果 → 检查K1知识库 |
| 实时推送延迟 | 检查WebSocket连接状态 → 检查Redis Streams积压 |
| 移动端离线同步失败 | 检查IndexedDB → 检查SyncManager日志 → 检查P3通知队列 |
| Temporal工作流卡住 | Temporal Web UI查看 → 检查Worker日志 → 检查Activity超时 |

---

*最后更新: 2026-02-24*
*下次更新: 每个Sprint结束时更新模块状态*
