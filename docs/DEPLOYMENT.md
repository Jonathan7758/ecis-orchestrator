# ECIS Orchestrator 部署指南

**版本**: 1.0.0  
**更新日期**: 2026-01-28

---

## 目录

1. [系统要求](#1-系统要求)
2. [快速部署](#2-快速部署)
3. [生产环境部署](#3-生产环境部署)
4. [配置说明](#4-配置说明)
5. [健康检查](#5-健康检查)
6. [故障排除](#6-故障排除)
7. [升级指南](#7-升级指南)

---

## 1. 系统要求

### 1.1 硬件要求

| 环境 | CPU | 内存 | 磁盘 |
|------|-----|------|------|
| 开发 | 2核 | 4GB | 20GB |
| 测试 | 4核 | 8GB | 50GB |
| 生产 | 8核+ | 16GB+ | 100GB+ |

### 1.2 软件要求

| 组件 | 版本 | 说明 |
|------|------|------|
| Docker | 24.0+ | 容器运行时 |
| Docker Compose | 2.20+ | 容器编排 |
| Python | 3.11+ | 后端运行时 |

### 1.3 端口要求

| 端口 | 服务 | 说明 |
|------|------|------|
| 8200 | Orchestrator API | 主服务 |
| 7233 | Temporal gRPC | 工作流引擎 |
| 8233 | Temporal UI | Web 管理界面 |
| 5434 | PostgreSQL | 数据库 |
| 6380 | Redis | 缓存 |

---

## 2. 快速部署

### 2.1 克隆项目

```bash
git clone https://github.com/Jonathan7758/ecis-orchestrator.git
cd ecis-orchestrator
```

### 2.2 启动基础设施

```bash
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

### 2.3 安装 Python 依赖

```bash
# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate  # Windows

# 安装依赖
pip install -e .
```

### 2.4 启动服务

```bash
# 启动 Temporal Worker
python -m app.workers.main_worker &

# 启动 API 服务
uvicorn app.main:app --host 0.0.0.0 --port 8200
```

### 2.5 验证部署

```bash
# 健康检查
curl http://localhost:8200/health

# 预期响应
{"status":"healthy","service":"ecis-orchestrator","version":"0.1.0"}
```

---

## 3. 生产环境部署

### 3.1 使用 Docker Compose (推荐)

```yaml
# docker-compose.prod.yml
version: '3.8'

services:
  orchestrator:
    build: .
    ports:
      - "8200:8200"
    environment:
      - DATABASE_URL=postgresql://ecis:password@postgres:5432/ecis_orchestrator
      - REDIS_URL=redis://redis:6379/0
      - TEMPORAL_HOST=temporal:7233
      - LOG_LEVEL=INFO
    depends_on:
      - temporal
      - postgres
      - redis
    restart: always
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8200/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  worker:
    build: .
    command: python -m app.workers.main_worker
    environment:
      - TEMPORAL_HOST=temporal:7233
      - LOG_LEVEL=INFO
    depends_on:
      - temporal
    restart: always

  temporal:
    image: temporalio/auto-setup:1.22
    ports:
      - "7233:7233"
    environment:
      - DB=postgresql
      - DB_PORT=5432
      - POSTGRES_USER=temporal
      - POSTGRES_PWD=temporal
      - POSTGRES_SEEDS=postgres
    depends_on:
      - postgres

  temporal-ui:
    image: temporalio/ui:2.21
    ports:
      - "8233:8080"
    environment:
      - TEMPORAL_ADDRESS=temporal:7233

  postgres:
    image: postgres:15
    environment:
      - POSTGRES_USER=ecis
      - POSTGRES_PASSWORD=password
      - POSTGRES_DB=ecis_orchestrator
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data

volumes:
  postgres_data:
  redis_data:
```

启动命令:
```bash
docker-compose -f docker-compose.prod.yml up -d
```

### 3.2 使用 Kubernetes

```yaml
# k8s/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ecis-orchestrator
spec:
  replicas: 3
  selector:
    matchLabels:
      app: ecis-orchestrator
  template:
    metadata:
      labels:
        app: ecis-orchestrator
    spec:
      containers:
      - name: orchestrator
        image: ecis-orchestrator:latest
        ports:
        - containerPort: 8200
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: ecis-secrets
              key: database-url
        livenessProbe:
          httpGet:
            path: /health
            port: 8200
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health
            port: 8200
          initialDelaySeconds: 5
          periodSeconds: 5
```

---

## 4. 配置说明

### 4.1 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `DATABASE_URL` | postgresql://... | PostgreSQL 连接串 |
| `REDIS_URL` | redis://localhost:6380 | Redis 连接串 |
| `TEMPORAL_HOST` | localhost:7233 | Temporal 地址 |
| `TEMPORAL_NAMESPACE` | default | Temporal 命名空间 |
| `TEMPORAL_TASK_QUEUE` | ecis-orchestrator | 任务队列名称 |
| `LOG_LEVEL` | INFO | 日志级别 |
| `API_HOST` | 0.0.0.0 | API 监听地址 |
| `API_PORT` | 8200 | API 端口 |
| `FEDERATION_ENABLED` | false | 是否启用联邦 |
| `FEDERATION_GATEWAY_URL` | - | 联邦网关地址 |

### 4.2 配置文件

```yaml
# config/production.yaml
database:
  url: ${DATABASE_URL}
  pool_size: 20
  max_overflow: 10

redis:
  url: ${REDIS_URL}
  max_connections: 50

temporal:
  host: ${TEMPORAL_HOST}
  namespace: ${TEMPORAL_NAMESPACE}
  task_queue: ${TEMPORAL_TASK_QUEUE}

api:
  host: ${API_HOST}
  port: ${API_PORT}
  workers: 4

logging:
  level: ${LOG_LEVEL}
  format: json
```

---

## 5. 健康检查

### 5.1 API 健康检查

```bash
# 基础健康检查
curl http://localhost:8200/health

# 详细状态
curl http://localhost:8200/health/detailed
```

### 5.2 组件状态检查

```bash
# Temporal 连接
curl http://localhost:8200/health/temporal

# 数据库连接
curl http://localhost:8200/health/database

# Redis 连接
curl http://localhost:8200/health/redis
```

### 5.3 监控指标

```bash
# Prometheus 指标
curl http://localhost:8200/metrics
```

---

## 6. 故障排除

### 6.1 常见问题

#### Temporal 连接失败

```bash
# 检查 Temporal 容器状态
docker logs ecis-temporal

# 验证端口可达
telnet localhost 7233
```

#### 数据库连接失败

```bash
# 检查 PostgreSQL 容器
docker logs ecis-postgres

# 验证连接
psql -h localhost -p 5434 -U ecis -d ecis_orchestrator
```

#### Worker 未处理任务

```bash
# 检查 Worker 日志
docker logs ecis-worker

# 查看 Temporal UI
open http://localhost:8233
```

### 6.2 日志查看

```bash
# API 服务日志
docker logs -f ecis-orchestrator

# Worker 日志
docker logs -f ecis-worker

# 全部日志
docker-compose logs -f
```

### 6.3 重启服务

```bash
# 重启单个服务
docker-compose restart orchestrator

# 重启所有服务
docker-compose restart

# 完全重建
docker-compose down && docker-compose up -d
```

---

## 7. 升级指南

### 7.1 滚动升级

```bash
# 拉取最新代码
git pull origin main

# 重建镜像
docker-compose build

# 滚动更新
docker-compose up -d --no-deps orchestrator worker
```

### 7.2 数据库迁移

```bash
# 运行迁移
alembic upgrade head

# 回滚
alembic downgrade -1
```

### 7.3 版本回退

```bash
# 切换到指定版本
git checkout v1.0.0

# 重建并部署
docker-compose build
docker-compose up -d
```

---

## 附录: 快速命令参考

```bash
# 启动全部服务
docker-compose up -d

# 停止全部服务
docker-compose down

# 查看日志
docker-compose logs -f

# 健康检查
curl http://localhost:8200/health

# 查看容器状态
docker ps

# 进入容器
docker exec -it ecis-orchestrator bash

# 查看 Temporal UI
open http://localhost:8233
```

---

**文档版本**: 1.0.0  
**最后更新**: 2026-01-28
