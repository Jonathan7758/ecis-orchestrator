# ECIS Orchestrator Demo 操作指南

## 目录
1. [环境准备](#1-环境准备)
2. [启动服务](#2-启动服务)
3. [Demo 场景演示](#3-demo-场景演示)
4. [API 测试](#4-api-测试)
5. [常见问题](#5-常见问题)

---

## 1. 环境准备

### 1.1 系统要求
- Linux/macOS (推荐 Ubuntu 22.04+)
- Python 3.11+
- Docker & Docker Compose
- 4GB+ 内存

### 1.2 克隆项目
```bash
cd /root/projects/ecis
git clone <repository-url> ecis-orchestrator
cd ecis-orchestrator
```

### 1.3 创建虚拟环境
```bash
python3 -m venv venv
source venv/bin/activate
pip install -e .
```

### 1.4 启动基础设施
```bash
# 启动 Temporal, PostgreSQL, Redis
docker compose up -d

# 等待服务就绪 (约30秒)
sleep 30

# 检查服务状态
docker compose ps
```

预期输出:
```
NAME                    STATUS
orchestrator-temporal   Up
orchestrator-postgresql Up
orchestrator-redis      Up
```

---

## 2. 启动服务

### 2.1 启动 Temporal Worker
打开终端1:
```bash
cd /root/projects/ecis/ecis-orchestrator
source venv/bin/activate
python -m src.workers.main_worker
```

预期输出:
```
2026-01-27 10:00:00 - INFO - Connecting to Temporal: localhost:7233
2026-01-27 10:00:00 - INFO - Starting worker on queue: ecis-orchestrator-queue
2026-01-27 10:00:00 - INFO - Worker started, waiting for tasks...
2026-01-27 10:00:00 - INFO - Registered 6 workflows and 23 activities
```

### 2.2 启动 API 服务
打开终端2:
```bash
cd /root/projects/ecis/ecis-orchestrator
source venv/bin/activate
uvicorn src.api.main:app --reload --port 8200
```

预期输出:
```
INFO:     Uvicorn running on http://0.0.0.0:8200
INFO:     Connecting to Temporal: localhost:7233
INFO:     Connected to Temporal
```

### 2.3 验证服务
```bash
# 健康检查
curl http://localhost:8200/health

# 预期返回
{"status":"healthy","service":"ecis-orchestrator","version":"0.1.0"}
```

---

## 3. Demo 场景演示

### 场景1: 机器人清洁任务

#### 3.1.1 启动清洁工作流
```bash
curl -X POST http://localhost:8200/api/v1/workflows/cleaning \
  -H "Content-Type: application/json" \
  -d '{
    "floor_id": "floor-3",
    "zone_id": "zone-a",
    "cleaning_mode": "standard",
    "priority": 3
  }'
```

返回:
```json
{
  "workflow_id": "cleaning-abc12345",
  "status": "started",
  "message": "Cleaning workflow started"
}
```

#### 3.1.2 查询工作流状态
```bash
curl http://localhost:8200/api/v1/workflows/cleaning-abc12345
```

返回:
```json
{
  "status": "cleaning",
  "robot_id": "robot-001",
  "current_zone": "zone-a",
  "progress": 45
}
```

#### 3.1.3 在 Temporal Web UI 查看
打开浏览器访问: http://localhost:8233

可以看到:
- 工作流执行历史
- Activity 调用详情
- 实时状态更新

---

### 场景2: 物品配送任务

#### 3.2.1 启动配送
```bash
curl -X POST http://localhost:8200/api/v1/delivery \
  -H "Content-Type: application/json" \
  -d '{
    "pickup_location": "floor-1/room-101",
    "delivery_location": "floor-3/room-305",
    "item_description": "文件包裹",
    "recipient_id": "user-zhang",
    "sender_id": "user-li",
    "priority": 2
  }'
```

返回:
```json
{
  "workflow_id": "delivery-xyz78901",
  "status": "started",
  "message": "Delivery workflow started"
}
```

#### 3.2.2 查询配送状态
```bash
curl http://localhost:8200/api/v1/delivery/delivery-xyz78901
```

返回:
```json
{
  "status": "going_to_pickup",
  "robot_id": "robot-001",
  "current_phase": "going_to_pickup",
  "pickup_completed": false,
  "delivery_completed": false
}
```

#### 3.2.3 确认取货
```bash
curl -X POST http://localhost:8200/api/v1/delivery/delivery-xyz78901/confirm-pickup
```

#### 3.2.4 确认送达
```bash
curl -X POST http://localhost:8200/api/v1/delivery/delivery-xyz78901/confirm-delivery
```

---

### 场景3: 审批流程

#### 3.3.1 创建审批请求
```bash
curl -X POST http://localhost:8200/api/v1/approvals \
  -H "Content-Type: application/json" \
  -d '{
    "request_type": "access_request",
    "title": "访问3楼机房",
    "description": "需要进入3楼机房进行设备维护",
    "data": {"floor": 3, "room": "server-room"},
    "approvers": ["manager-001"],
    "timeout_hours": 24
  }'
```

#### 3.3.2 批准请求
```bash
curl -X POST http://localhost:8200/api/v1/approvals/approval-abc123/approve \
  -H "Content-Type: application/json" \
  -d '{
    "approver_id": "manager-001",
    "reason": "批准访问"
  }'
```

---

### 场景4: 任务分派

#### 3.4.1 查看可用 Agent
```bash
curl http://localhost:8200/api/v1/tasks/agents
```

返回:
```json
[
  {
    "agent_id": "robot-001",
    "agent_type": "robot",
    "capabilities": ["cleaning.floor.standard", "delivery.*"],
    "status": "ready",
    "current_load": 0,
    "max_load": 5
  }
]
```

#### 3.4.2 分派任务
```bash
curl -X POST http://localhost:8200/api/v1/tasks/dispatch \
  -H "Content-Type: application/json" \
  -d '{
    "capability": "cleaning.floor.standard",
    "parameters": {"floor": "floor-1", "zone": "lobby"},
    "priority": 2
  }'
```

#### 3.4.3 查看统计
```bash
curl http://localhost:8200/api/v1/tasks/stats/overview
```

返回:
```json
{
  "agents": {"total": 3, "ready": 2, "busy": 1, "offline": 0},
  "tasks": {"total": 5, "pending": 1, "completed": 4, "failed": 0}
}
```

---

## 4. API 测试

### 4.1 使用 Swagger UI
打开浏览器访问: http://localhost:8200/docs

可以看到所有 API 端点的交互式文档。

### 4.2 运行自动化测试
```bash
# 运行所有单元测试
pytest tests/ -v --ignore=tests/test_e2e.py

# 运行端到端测试 (需要Worker运行)
python tests/test_e2e.py
```

---

## 5. 常见问题

### Q1: Temporal 连接失败
```
Error: Failed to connect to Temporal
```

**解决方案:**
```bash
# 检查 Temporal 容器
docker compose ps
docker compose logs temporal

# 重启服务
docker compose restart temporal
```

### Q2: Worker 注册失败
```
Error: No workers are polling the task queue
```

**解决方案:**
确保 Worker 正在运行:
```bash
python -m src.workers.main_worker
```

### Q3: 端口冲突
```
Error: Address already in use
```

**解决方案:**
```bash
# 查找占用端口的进程
lsof -i :8200
lsof -i :7233

# 终止进程或修改端口配置
```

### Q4: 数据库连接失败
**解决方案:**
```bash
# 检查 PostgreSQL
docker compose logs postgresql

# 重新创建数据库
docker compose down -v
docker compose up -d
```

---

## 附录: 服务端口

| 服务 | 端口 | 说明 |
|------|------|------|
| API Server | 8200 | REST API |
| Temporal gRPC | 7233 | Temporal 服务 |
| Temporal Web | 8233 | Web UI |
| PostgreSQL | 5434 | 数据库 |
| Redis | 6380 | 缓存 |
