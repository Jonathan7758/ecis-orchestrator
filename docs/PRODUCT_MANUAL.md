# ECIS Orchestrator 产品功能手册

**版本**: 1.0.0
**更新日期**: 2026-01-27
**文档状态**: 正式版

---

## 目录

1. [产品概述](#1-产品概述)
2. [系统架构](#2-系统架构)
3. [核心功能](#3-核心功能)
4. [工作流详解](#4-工作流详解)
5. [API 接口规范](#5-api-接口规范)
6. [数据模型](#6-数据模型)
7. [集成指南](#7-集成指南)
8. [性能指标](#8-性能指标)

---

## 1. 产品概述

### 1.1 产品定位

ECIS Orchestrator 是企业级智能楼宇机器人任务编排系统的核心组件，负责协调和管理各类服务机器人的任务执行。

### 1.2 核心价值

| 价值点 | 说明 |
|--------|------|
| **任务自动化** | 自动分配和调度机器人任务 |
| **流程可靠性** | 基于 Temporal 的持久化工作流 |
| **智能决策** | 集成 LLM 进行任务分析和异常处理 |
| **灵活扩展** | 支持自定义工作流和 Activity |

### 1.3 适用场景

- 商业楼宇的清洁管理
- 物品配送服务
- 安全巡检巡逻
- 访客接待引导
- 设备设施联动

---

## 2. 系统架构

### 2.1 整体架构图

```
┌─────────────────────────────────────────────────────────────┐
│                      ECIS Platform                          │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │   Web UI    │  │  Mobile App │  │  Third-party System │ │
│  └──────┬──────┘  └──────┬──────┘  └──────────┬──────────┘ │
│         │                │                     │            │
│         └────────────────┼─────────────────────┘            │
│                          │                                  │
│                          ▼                                  │
│  ┌───────────────────────────────────────────────────────┐ │
│  │              ECIS Orchestrator (本系统)                │ │
│  │  ┌─────────┐  ┌──────────┐  ┌─────────┐  ┌─────────┐ │ │
│  │  │ FastAPI │  │ Temporal │  │ Workers │  │Services │ │ │
│  │  │   API   │  │  Engine  │  │         │  │         │ │ │
│  │  └────┬────┘  └────┬─────┘  └────┬────┘  └────┬────┘ │ │
│  └───────┼────────────┼─────────────┼────────────┼──────┘ │
│          │            │             │            │         │
│          ▼            ▼             ▼            ▼         │
│  ┌───────────────────────────────────────────────────────┐ │
│  │                   基础设施层                          │ │
│  │  ┌──────────┐  ┌───────────┐  ┌────────────────────┐ │ │
│  │  │PostgreSQL│  │   Redis   │  │ Federation Gateway │ │ │
│  │  └──────────┘  └───────────┘  └────────────────────┘ │ │
│  └───────────────────────────────────────────────────────┘ │
│                          │                                  │
│                          ▼                                  │
│  ┌───────────────────────────────────────────────────────┐ │
│  │                    设备层                              │ │
│  │  ┌─────────┐  ┌──────────┐  ┌─────────┐  ┌─────────┐ │ │
│  │  │清洁机器人│  │配送机器人│  │  电梯   │  │门禁系统│  │ │
│  │  └─────────┘  └──────────┘  └─────────┘  └─────────┘ │ │
│  └───────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 技术栈

| 层级 | 技术选型 | 说明 |
|------|----------|------|
| API 层 | FastAPI | 高性能异步 REST API |
| 工作流引擎 | Temporal | 持久化工作流编排 |
| 数据存储 | PostgreSQL | 业务数据持久化 |
| 缓存 | Redis | 状态缓存和消息队列 |
| 通信 | Federation Protocol | 多系统互联 |

### 2.3 模块说明

| 模块 | 功能 |
|------|------|
| **core** | 配置管理、异常处理、数据库连接 |
| **activities** | Temporal Activity 实现 (机器人、设施、通知、LLM) |
| **workflows** | Temporal Workflow 定义 (清洁、审批、配送、定时任务) |
| **services** | 业务服务层 (工作流服务、任务分派) |
| **api** | REST API 路由和处理 |
| **federation** | Federation Gateway 客户端 |
| **models** | SQLAlchemy 数据库模型 |

---

## 3. 核心功能

### 3.1 功能矩阵

| 功能模块 | 子功能 | 状态 |
|----------|--------|------|
| **工作流管理** | 清洁工作流 | ✅ |
| | 审批工作流 | ✅ |
| | 配送工作流 | ✅ |
| | 定时任务工作流 | ✅ |
| **任务分派** | Agent 注册/注销 | ✅ |
| | 能力匹配 | ✅ |
| | 负载均衡 | ✅ |
| **设施控制** | 电梯调度 | ✅ |
| | 门禁控制 | ✅ |
| | 区域授权 | ✅ |
| **通知服务** | 任务通知 | ✅ |
| | 审批通知 | ✅ |
| | 状态更新 | ✅ |
| **智能分析** | 任务分析 | ✅ |
| | 异常分析 | ✅ |
| | 摘要生成 | ✅ |

### 3.2 Activity 清单

#### 3.2.1 机器人 Activities (6个)
| Activity | 功能 |
|----------|------|
| `get_robot_status` | 获取机器人状态 |
| `assign_task_to_robot` | 分配任务给机器人 |
| `wait_for_robot_task_completion` | 等待任务完成 |
| `get_robot_location` | 获取机器人位置 |
| `find_available_robot` | 查找可用机器人 |
| `release_robot` | 释放机器人 |

#### 3.2.2 设施 Activities (7个)
| Activity | 功能 |
|----------|------|
| `call_elevator` | 呼叫电梯 |
| `open_door` | 开门 |
| `close_door` | 关门 |
| `get_doors_on_route` | 获取路线上的门 |
| `grant_zone_access` | 授予区域访问权限 |
| `revoke_zone_access` | 撤销区域访问权限 |
| `get_floor_status` | 获取楼层状态 |

#### 3.2.3 通知 Activities (6个)
| Activity | 功能 |
|----------|------|
| `send_notification` | 发送通知 |
| `send_task_update` | 发送任务更新 |
| `create_approval_request` | 创建审批请求 |
| `get_approval_status` | 获取审批状态 |
| `send_approval_reminder` | 发送审批提醒 |
| `cancel_approval_request` | 取消审批请求 |

#### 3.2.4 LLM Activities (4个)
| Activity | 功能 |
|----------|------|
| `analyze_task_request` | 分析任务请求 |
| `analyze_exception` | 分析异常情况 |
| `generate_task_summary` | 生成任务摘要 |
| `extract_workflow_parameters` | 提取工作流参数 |

---

## 4. 工作流详解

### 4.1 清洁工作流 (RobotCleaningWorkflow)

**用途**: 协调机器人完成区域清洁任务

**流程图**:
```
开始 → 查找机器人 → 分配任务 → 准备阶段(电梯/门禁) → 执行清洁 → 完成通知 → 结束
                                    ↓
                              [并行执行]
                           ┌────┴────┐
                        呼叫电梯  获取门禁
```

**输入参数**:
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| floor_id | string | 是 | 楼层ID |
| zone_id | string | 否 | 区域ID |
| cleaning_mode | string | 否 | 清洁模式 (standard/deep/quick) |
| robot_id | string | 否 | 指定机器人ID |
| priority | int | 否 | 优先级 (1-5) |

**输出结果**:
| 字段 | 类型 | 说明 |
|------|------|------|
| success | bool | 是否成功 |
| robot_id | string | 执行机器人ID |
| duration_minutes | float | 执行时长(分钟) |
| area_cleaned_sqm | float | 清洁面积(平方米) |
| message | string | 结果消息 |

### 4.2 审批工作流 (ApprovalWorkflow)

**用途**: 处理需要人工审批的请求

**流程图**:
```
开始 → 创建审批 → 发送通知 → 等待审批 ──┬── 批准 → 执行后续 → 结束
                              │    └── 拒绝 → 通知拒绝 → 结束
                              └── 超时 → 通知超时 → 结束
```

**信号**:
| 信号 | 参数 | 说明 |
|------|------|------|
| approve | approver_id, reason, data | 批准审批 |
| reject | approver_id, reason | 拒绝审批 |
| cancel | reason | 取消审批 |

**查询**:
| 查询 | 返回 | 说明 |
|------|------|------|
| get_status | dict | 获取当前审批状态 |

### 4.3 配送工作流 (DeliveryWorkflow)

**用途**: 协调机器人完成物品配送

**流程图**:
```
开始 → 分配机器人 → 前往取货点 → 等待取货确认 → 前往送达点 → 等待送达确认 → 结束
                                    ↑                         ↑
                              [confirm_pickup]          [confirm_delivery]
```

**信号**:
| 信号 | 说明 |
|------|------|
| confirm_pickup | 确认取货 |
| confirm_delivery | 确认送达 |
| cancel_delivery | 取消配送 |

### 4.4 定时清洁工作流 (ScheduledCleaningWorkflow)

**用途**: 按计划执行多区域清洁

**特点**:
- 支持多个目标区域
- 自动检查区域占用状态
- 支持跳过特定区域

### 4.5 定时巡检工作流 (ScheduledPatrolWorkflow)

**用途**: 执行安全巡检任务

**特点**:
- 按检查点顺序巡检
- 支持异常上报
- 生成巡检报告

---

## 5. API 接口规范

### 5.1 接口概览

| 模块 | 基础路径 | 说明 |
|------|----------|------|
| 工作流 | /api/v1/workflows | 工作流管理 |
| 审批 | /api/v1/approvals | 审批管理 |
| 配送 | /api/v1/delivery | 配送管理 |
| 任务 | /api/v1/tasks | 任务分派 |

### 5.2 工作流接口

#### POST /api/v1/workflows/cleaning
启动清洁工作流

**请求体**:
```json
{
  "floor_id": "floor-3",
  "zone_id": "zone-a",
  "cleaning_mode": "standard",
  "priority": 3
}
```

**响应**:
```json
{
  "workflow_id": "cleaning-abc12345",
  "status": "started",
  "message": "Cleaning workflow started"
}
```

#### GET /api/v1/workflows/{workflow_id}
获取工作流状态

#### POST /api/v1/workflows/{workflow_id}/cancel
取消工作流

### 5.3 配送接口

#### POST /api/v1/delivery
启动配送

**请求体**:
```json
{
  "pickup_location": "floor-1/room-101",
  "delivery_location": "floor-3/room-305",
  "item_description": "文件包裹",
  "recipient_id": "user-001",
  "priority": 2
}
```

#### POST /api/v1/delivery/{workflow_id}/confirm-pickup
确认取货

#### POST /api/v1/delivery/{workflow_id}/confirm-delivery
确认送达

### 5.4 任务分派接口

#### GET /api/v1/tasks/agents
列出所有Agent

#### POST /api/v1/tasks/dispatch
分派任务

**请求体**:
```json
{
  "capability": "cleaning.floor.standard",
  "parameters": {"floor": "floor-1"},
  "priority": 3
}
```

#### GET /api/v1/tasks/stats/overview
获取统计信息

---

## 6. 数据模型

### 6.1 工作流记录 (WorkflowRecord)

| 字段 | 类型 | 说明 |
|------|------|------|
| id | int | 主键 |
| workflow_id | string | 工作流ID |
| workflow_type | string | 工作流类型 |
| status | string | 状态 |
| input_data | json | 输入参数 |
| output_data | json | 输出结果 |
| started_at | datetime | 开始时间 |
| completed_at | datetime | 完成时间 |

### 6.2 任务记录 (TaskRecord)

| 字段 | 类型 | 说明 |
|------|------|------|
| id | int | 主键 |
| task_id | string | 任务ID |
| workflow_id | string | 关联工作流ID |
| task_type | string | 任务类型 |
| agent_id | string | 执行Agent |
| status | string | 状态 |
| priority | int | 优先级 |

### 6.3 Agent记录 (AgentRecord)

| 字段 | 类型 | 说明 |
|------|------|------|
| id | int | 主键 |
| agent_id | string | Agent ID |
| agent_type | string | Agent类型 |
| capabilities | json | 能力列表 |
| status | string | 状态 |
| current_load | int | 当前负载 |
| max_load | int | 最大负载 |

---

## 7. 集成指南

### 7.1 与机器人系统集成

```python
# 注册机器人到编排器
curl -X POST http://orchestrator:8200/api/v1/tasks/agents \
  -d '{
    "agent_id": "robot-001",
    "agent_type": "robot",
    "capabilities": ["cleaning.floor.standard", "delivery"]
  }'
```

### 7.2 与楼宇系统集成

通过 Federation Gateway 实现与电梯、门禁等系统的联动。

### 7.3 与通知系统集成

配置 Notification Activity 连接企业通知系统。

---

## 8. 性能指标

### 8.1 系统容量

| 指标 | 值 |
|------|-----|
| 并发工作流 | 1000+ |
| 每秒任务分派 | 100+ |
| API 响应时间 | < 100ms |
| 工作流启动延迟 | < 500ms |

### 8.2 可靠性

| 指标 | 值 |
|------|-----|
| 工作流持久化 | 100% |
| 自动重试 | 3次 |
| 故障恢复 | 自动 |

---

## 版本历史

| 版本 | 日期 | 说明 |
|------|------|------|
| 1.0.0 | 2026-01-27 | 初始版本 |
