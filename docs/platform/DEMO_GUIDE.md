# ECIS 平台 Demo 操作手册

**版本**: 1.0.0
**更新日期**: 2026-01-28
**适用范围**: ECIS MVP 演示

---

## 目录

1. [环境准备](#1-环境准备)
2. [启动服务](#2-启动服务)
3. [Demo 场景演示](#3-demo-场景演示)
4. [API 测试](#4-api-测试)
5. [常见问题](#5-常见问题)

---

## 1. 环境准备

### 1.1 系统要求

| 组件 | 要求 |
|------|------|
| 操作系统 | Linux / macOS / Windows |
| Docker | 24.0+ |
| Docker Compose | 2.20+ |
| Node.js | 18+ (前端) |
| Python | 3.11+ (后端) |
| 内存 | 8GB+ |
| 磁盘 | 20GB+ |

### 1.2 端口要求

| 端口 | 服务 | 说明 |
|------|------|------|
| 3000 | 工作流设计器 | 前端界面 |
| 8200 | 编排器 API | 后端服务 |
| 8233 | Temporal UI | 工作流监控 |
| 7233 | Temporal gRPC | 工作流引擎 |
| 5434 | PostgreSQL | 数据库 |
| 6380 | Redis | 缓存 |

### 1.3 克隆项目

```bash
# 克隆各个仓库
git clone https://github.com/Jonathan7758/ecis-orchestrator.git
git clone https://github.com/Jonathan7758/ecis-workflow-designer.git
git clone https://github.com/Jonathan7758/ecis-protocols.git
git clone https://github.com/Jonathan7758/ecis-human-agent.git
git clone https://github.com/Jonathan7758/mep-ai-agent.git
```

---

## 2. 启动服务

### 2.1 启动后端服务

```bash
# 进入编排器目录
cd ecis-orchestrator

# 启动 Docker 容器 (Temporal, PostgreSQL, Redis)
docker-compose up -d

# 验证容器状态
docker ps
```

预期输出:
```
NAMES              STATUS
ecis-temporal      Up
ecis-temporal-ui   Up
ecis-postgres      Up
ecis-redis         Up
```

### 2.2 启动编排器 API

```bash
# 安装 Python 依赖
cd ecis-orchestrator
python -m venv venv
source venv/bin/activate  # Linux/Mac
pip install -e .

# 启动 Temporal Worker (后台运行)
python -m app.workers.main_worker &

# 启动 API 服务
uvicorn src.api.main:app --host 0.0.0.0 --port 8200
```

### 2.3 验证后端服务

```bash
# 健康检查
curl http://localhost:8200/health

# 预期响应
{"status":"healthy","service":"ecis-orchestrator","version":"0.1.0"}
```

### 2.4 启动前端设计器

```bash
# 进入设计器目录
cd ecis-workflow-designer

# 安装依赖
npm install

# 启动开发服务器
npm run dev
```

预期输出:
```
VITE v7.x.x ready in xxx ms

➜  Local:   http://localhost:3000/
➜  Network: http://x.x.x.x:3000/
```

### 2.5 访问系统

| 服务 | 地址 | 说明 |
|------|------|------|
| 工作流设计器 | http://localhost:3000 | 可视化设计界面 |
| 编排器 API | http://localhost:8200 | REST API |
| API 文档 | http://localhost:8200/docs | Swagger UI |
| Temporal UI | http://localhost:8233 | 工作流监控 |

---

## 3. Demo 场景演示

### 场景1: 创建清洁工作流

#### 步骤1: 打开设计器

1. 访问 http://localhost:3000
2. 确认页面显示三个区域:
   - 左侧: 节点面板
   - 中央: 画布
   - 右侧: 属性面板

#### 步骤2: 从模板创建

1. 点击工具栏「模板」按钮
2. 选择「机器人清洁工作流」模板
3. 工作流自动加载到画布

#### 步骤3: 查看工作流结构

```
开始 → 检查机器人状态 → 电量检查 → 同楼层? → 叫电梯
                              ↓              ↓
                          开门禁 ← ─────────┘
                              ↓
                          执行清洁 → 发送通知 → 结束
```

#### 步骤4: 配置参数

1. 点击「检查机器人状态」节点
2. 在右侧属性面板设置:
   - 机器人ID: `robot-001`
   - 超时: `30` 秒

3. 点击「执行清洁」节点
4. 设置:
   - 能力: `cleaning.floor.standard`
   - 区域ID: `zone-a`
   - 超时: `7200` 秒

#### 步骤5: 验证并保存

1. 点击工具栏「验证」按钮
2. 确认显示「验证通过」
3. 点击「保存」按钮
4. 输入名称: 「日常清洁-5楼A区」

---

### 场景2: 创建配送工作流

#### 步骤1: 新建工作流

1. 点击「新建」按钮
2. 清空画布

#### 步骤2: 添加节点

从左侧面板拖拽以下节点:

| 顺序 | 节点类型 | 名称 |
|------|---------|------|
| 1 | 开始 | 开始 |
| 2 | 任务 | 前往取件点 |
| 3 | 等待 | 等待装载 |
| 4 | 决策 | 跨楼层? |
| 5 | 任务 | 叫电梯 |
| 6 | 任务 | 前往送达点 |
| 7 | 通知 | 通知收件人 |
| 8 | 等待 | 等待取件 |
| 9 | 结束 | 配送完成 |

#### 步骤3: 连接节点

1. 从「开始」拖动连线到「前往取件点」
2. 依次连接后续节点
3. 「决策」节点:
   - 「是」分支 → 「叫电梯」
   - 「否」分支 → 「前往送达点」

#### 步骤4: 配置属性

**前往取件点**:
- 能力: `robot.navigation.goto`
- 目的地: `floor-1/room-101`

**通知收件人**:
- 通道: `sms`
- 消息: `您的包裹已送达，请及时取件`

#### 步骤5: 自动布局

1. 点击工具栏「自动布局」按钮
2. 节点自动排列整齐

---

### 场景3: 使用 API 启动工作流

#### 步骤1: 查看可用模板

```bash
curl http://localhost:8200/api/v1/templates | jq
```

响应:
```json
{
  "templates": [
    {
      "template_id": "robot-cleaning-workflow",
      "name": "机器人清洁工作流",
      "category": "cleaning",
      "priority": "P0"
    },
    ...
  ],
  "total": 5
}
```

#### 步骤2: 查看模板详情

```bash
curl http://localhost:8200/api/v1/templates/robot-cleaning-workflow | jq
```

#### 步骤3: 验证输入参数

```bash
curl -X POST http://localhost:8200/api/v1/templates/robot-cleaning-workflow/validate \
  -H "Content-Type: application/json" \
  -d '{
    "input": {
      "robot_id": "robot-001",
      "target_floor": 5,
      "area_id": "zone-a"
    }
  }'
```

响应:
```json
{"valid": true, "errors": []}
```

#### 步骤4: 查看可用 Agent

```bash
curl http://localhost:8200/api/v1/tasks/agents | jq
```

响应:
```json
[
  {
    "agent_id": "robot-001",
    "agent_type": "robot",
    "capabilities": ["cleaning.floor.standard", "cleaning.floor.deep"],
    "status": "ready"
  },
  ...
]
```

#### 步骤5: 分派任务

```bash
curl -X POST http://localhost:8200/api/v1/tasks/dispatch \
  -H "Content-Type: application/json" \
  -d '{
    "capability": "cleaning.floor.standard",
    "parameters": {
      "floor": "floor-5",
      "zone": "zone-a"
    },
    "priority": 3
  }'
```

响应:
```json
{
  "task_id": "task-xxx",
  "agent_id": "robot-001",
  "status": "assigned"
}
```

---

### 场景4: 监控工作流执行

#### 步骤1: 打开 Temporal UI

访问 http://localhost:8233

#### 步骤2: 查看工作流列表

1. 点击左侧「Workflows」
2. 查看运行中的工作流

#### 步骤3: 查看工作流详情

1. 点击具体工作流
2. 查看执行历史
3. 查看每个步骤的输入输出

#### 步骤4: 查看统计信息

```bash
curl http://localhost:8200/api/v1/tasks/stats/overview | jq
```

响应:
```json
{
  "agents": {
    "total": 5,
    "ready": 3,
    "busy": 2
  },
  "tasks": {
    "total": 10,
    "pending": 2,
    "running": 3,
    "completed": 5
  }
}
```

---

### 场景5: 人工审批流程

#### 步骤1: 创建审批工作流

1. 在设计器中新建工作流
2. 添加「审批」节点
3. 配置审批人: `manager-001`
4. 设置超时: `60` 分钟

#### 步骤2: 通过 API 提交审批

```bash
curl -X POST http://localhost:8200/api/v1/approvals \
  -H "Content-Type: application/json" \
  -d '{
    "request_type": "access_request",
    "title": "机器人进入禁区申请",
    "description": "清洁机器人需要进入5楼服务器机房进行清洁",
    "data": {"floor": 5, "room": "server-room"},
    "approvers": ["manager-001"],
    "timeout_hours": 1
  }'
```

#### 步骤3: 在 Temporal UI 查看

1. 打开 Temporal UI
2. 找到审批工作流
3. 查看等待审批状态

---

## 4. API 测试

### 4.1 健康检查

```bash
# 健康检查
curl http://localhost:8200/health

# 就绪检查
curl http://localhost:8200/ready
```

### 4.2 Agent 管理

```bash
# 列出 Agent
curl http://localhost:8200/api/v1/tasks/agents

# 注册 Agent
curl -X POST http://localhost:8200/api/v1/tasks/agents \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "robot-new",
    "agent_type": "robot",
    "capabilities": ["cleaning.floor.standard"]
  }'

# 更新状态
curl -X PUT "http://localhost:8200/api/v1/tasks/agents/robot-001/status?status=busy"
```

### 4.3 模板管理

```bash
# 列出模板
curl http://localhost:8200/api/v1/templates

# 按分类过滤
curl "http://localhost:8200/api/v1/templates?category=cleaning"

# 获取分类
curl http://localhost:8200/api/v1/templates/categories

# 获取模板详情
curl http://localhost:8200/api/v1/templates/robot-cleaning-workflow

# 获取模板变量
curl http://localhost:8200/api/v1/templates/robot-cleaning-workflow/variables
```

### 4.4 任务分派

```bash
# 查找可用 Agent
curl "http://localhost:8200/api/v1/tasks/agents/available?capability=cleaning.floor.standard"

# 分派任务
curl -X POST http://localhost:8200/api/v1/tasks/dispatch \
  -H "Content-Type: application/json" \
  -d '{
    "capability": "cleaning.floor.standard",
    "parameters": {"floor": "floor-5"},
    "priority": 3
  }'

# 完成任务
curl -X POST "http://localhost:8200/api/v1/tasks/{task_id}/complete?success=true"
```

---

## 5. 常见问题

### Q1: Docker 容器启动失败

**可能原因**: 端口被占用

**解决方案**:
```bash
# 检查端口占用
lsof -i :7233
lsof -i :5434

# 停止冲突服务或修改 docker-compose.yml 中的端口
```

### Q2: Temporal 连接失败

**可能原因**: Temporal 服务未就绪

**解决方案**:
```bash
# 等待 Temporal 启动
docker logs ecis-temporal

# 重启 Temporal
docker-compose restart temporal
```

### Q3: 前端无法连接后端

**可能原因**: CORS 或后端未启动

**解决方案**:
1. 确认后端运行: `curl http://localhost:8200/health`
2. 检查前端配置: `.env` 文件中 `VITE_API_BASE_URL`

### Q4: 工作流验证失败

**常见错误**:
- 缺少开始/结束节点
- 存在孤立节点
- 任务节点未配置能力

**解决方案**:
- 添加开始和结束节点
- 连接所有节点
- 为任务节点选择能力

### Q5: 模板加载失败

**解决方案**:
```bash
# 重新加载模板
curl -X POST http://localhost:8200/api/v1/templates/reload
```

---

## 附录: 快捷键速查

### 工作流设计器

| 快捷键 | 功能 |
|--------|------|
| Ctrl+S | 保存 |
| Ctrl+Z | 撤销 |
| Ctrl+Y | 重做 |
| Delete | 删除选中 |
| Shift+拖动 | 多选 |
| 滚轮 | 缩放 |
| 拖动空白 | 平移 |

### 常用 API

| 端点 | 方法 | 说明 |
|------|------|------|
| /health | GET | 健康检查 |
| /api/v1/templates | GET | 模板列表 |
| /api/v1/tasks/agents | GET | Agent 列表 |
| /api/v1/tasks/dispatch | POST | 分派任务 |
| /api/v1/tasks/stats/overview | GET | 统计信息 |

---

**文档版本**: 1.0.0
**最后更新**: 2026-01-28
