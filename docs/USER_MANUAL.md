# ECIS Orchestrator 用户使用手册

**版本**: 1.0.0
**适用人群**: 物业管理人员、楼宇运维人员、系统管理员
**更新日期**: 2026-01-27

---

## 目录

1. [快速入门](#1-快速入门)
2. [清洁任务管理](#2-清洁任务管理)
3. [物品配送服务](#3-物品配送服务)
4. [审批流程处理](#4-审批流程处理)
5. [定时任务管理](#5-定时任务管理)
6. [机器人管理](#6-机器人管理)
7. [监控与报表](#7-监控与报表)
8. [常见问题](#8-常见问题)

---

## 1. 快速入门

### 1.1 系统访问

**Web管理界面**: http://your-server:8200/docs

**API基础地址**: http://your-server:8200/api/v1

### 1.2 功能概览

ECIS Orchestrator 提供以下核心功能：

| 功能 | 说明 | 使用场景 |
|------|------|----------|
| 清洁任务 | 安排机器人执行清洁工作 | 日常清洁、应急清洁 |
| 物品配送 | 机器人送货上门服务 | 文件递送、物品传递 |
| 审批流程 | 需要审批的操作请求 | 访问申请、特殊作业 |
| 定时任务 | 计划性的重复任务 | 定时清洁、定时巡检 |

### 1.3 操作流程

```
1. 提交任务请求
       ↓
2. 系统自动分配机器人
       ↓
3. 机器人执行任务
       ↓
4. 任务完成通知
```

---

## 2. 清洁任务管理

### 2.1 创建清洁任务

**步骤**：

1. 打开 API 文档界面 (http://your-server:8200/docs)
2. 找到 `POST /api/v1/workflows/cleaning`
3. 填写任务参数：

| 参数 | 说明 | 示例 |
|------|------|------|
| floor_id | 楼层编号 | floor-3 |
| zone_id | 区域编号（可选） | zone-a |
| cleaning_mode | 清洁模式 | standard |
| priority | 优先级 (1最高-5最低) | 3 |

**清洁模式说明**：

| 模式 | 说明 | 预计时长 |
|------|------|----------|
| quick | 快速清洁，仅清扫主要区域 | 15-20分钟 |
| standard | 标准清洁，完整清扫 | 30-45分钟 |
| deep | 深度清洁，含消毒 | 60-90分钟 |

**示例请求**：
```json
{
  "floor_id": "floor-3",
  "zone_id": "zone-a",
  "cleaning_mode": "standard",
  "priority": 3
}
```

### 2.2 查看任务状态

**状态说明**：

| 状态 | 含义 |
|------|------|
| assigning | 正在分配机器人 |
| preparing | 准备中（呼叫电梯等） |
| cleaning | 清洁进行中 |
| completed | 任务完成 |
| failed | 任务失败 |

**查询方式**：
```
GET /api/v1/workflows/{workflow_id}
```

### 2.3 取消任务

如需取消正在进行的清洁任务：
```
POST /api/v1/workflows/{workflow_id}/cancel
```

**注意**：已开始执行的任务取消后，机器人将返回充电站。

---

## 3. 物品配送服务

### 3.1 发起配送请求

**必填信息**：

| 字段 | 说明 | 示例 |
|------|------|------|
| pickup_location | 取货地点 | floor-1/room-101 |
| delivery_location | 送达地点 | floor-3/room-305 |
| item_description | 物品描述 | 文件包裹 |
| recipient_id | 收件人ID | user-zhang |

**可选信息**：

| 字段 | 说明 | 默认值 |
|------|------|--------|
| sender_id | 发件人ID | - |
| priority | 优先级 | 3 |
| require_signature | 是否需签收 | false |
| notes | 备注信息 | - |

**示例请求**：
```json
{
  "pickup_location": "floor-1/room-101",
  "delivery_location": "floor-3/room-305",
  "item_description": "合同文件",
  "recipient_id": "user-zhang",
  "sender_id": "user-li",
  "priority": 2,
  "notes": "请轻拿轻放"
}
```

### 3.2 配送流程

```
1. 系统分配机器人
       ↓
2. 机器人前往取货点
       ↓
3. 发件人放置物品，点击"确认取货"
       ↓
4. 机器人前往送达点
       ↓
5. 收件人取走物品，点击"确认收货"
       ↓
6. 配送完成
```

### 3.3 确认取货

当机器人到达取货点后，发件人需要：

1. 将物品放入机器人储物舱
2. 调用确认接口：
```
POST /api/v1/delivery/{workflow_id}/confirm-pickup
```

### 3.4 确认收货

当机器人到达送达点后，收件人需要：

1. 从机器人储物舱取出物品
2. 调用确认接口：
```
POST /api/v1/delivery/{workflow_id}/confirm-delivery
```

### 3.5 取消配送

如需取消配送：
```
POST /api/v1/delivery/{workflow_id}/cancel?reason=用户取消
```

**注意事项**：
- 已取货的配送取消后，物品将退回发件人
- 系统会自动通知相关人员

---

## 4. 审批流程处理

### 4.1 创建审批请求

**适用场景**：
- 访问特殊区域申请
- 高优先级任务申请
- 设备使用申请

**请求参数**：

| 字段 | 说明 | 示例 |
|------|------|------|
| request_type | 请求类型 | access_request |
| title | 申请标题 | 访问3楼机房 |
| description | 详细说明 | 设备维护需要 |
| approvers | 审批人列表 | ["manager-001"] |
| timeout_hours | 超时时间(小时) | 24 |

### 4.2 审批操作

**批准申请**：
```
POST /api/v1/approvals/{workflow_id}/approve
{
  "approver_id": "manager-001",
  "reason": "批准访问"
}
```

**拒绝申请**：
```
POST /api/v1/approvals/{workflow_id}/reject
{
  "approver_id": "manager-001",
  "reason": "时间不合适"
}
```

### 4.3 审批状态

| 状态 | 说明 |
|------|------|
| pending | 等待审批 |
| approved | 已批准 |
| rejected | 已拒绝 |
| timeout | 超时未处理 |
| cancelled | 已取消 |

---

## 5. 定时任务管理

### 5.1 定时清洁

适用于每日/每周固定时间的清洁任务。

**配置示例**：
```json
{
  "task_type": "cleaning",
  "schedule_name": "每日大堂清洁",
  "target_locations": [
    "floor-1/lobby",
    "floor-1/corridor",
    "floor-2/lobby"
  ],
  "parameters": {
    "cleaning_mode": "standard"
  },
  "priority": 3
}
```

### 5.2 定时巡检

适用于安全巡逻任务。

**配置示例**：
```json
{
  "task_type": "patrol",
  "schedule_name": "夜间安全巡检",
  "target_locations": [
    "floor-1/entrance",
    "floor-1/parking",
    "floor-2/server-room",
    "floor-3/office"
  ],
  "parameters": {
    "check_items": ["security", "fire_safety"]
  }
}
```

### 5.3 跳过区域

如果某区域临时不需要清洁/巡检：
```
POST /api/v1/scheduled/{workflow_id}/skip
{
  "location": "floor-2/meeting-room"
}
```

---

## 6. 机器人管理

### 6.1 查看机器人列表

```
GET /api/v1/tasks/agents
```

**返回示例**：
```json
[
  {
    "agent_id": "robot-001",
    "agent_type": "robot",
    "capabilities": ["cleaning.floor.standard", "delivery"],
    "status": "ready",
    "current_load": 0,
    "max_load": 5
  }
]
```

### 6.2 机器人状态说明

| 状态 | 说明 | 可分配任务 |
|------|------|------------|
| ready | 空闲待命 | 是 |
| busy | 执行任务中 | 否 |
| charging | 充电中 | 否 |
| offline | 离线 | 否 |
| maintenance | 维护中 | 否 |

### 6.3 查看机器人能力

| 能力标识 | 说明 |
|----------|------|
| cleaning.floor.standard | 标准地面清洁 |
| cleaning.floor.deep | 深度地面清洁 |
| cleaning.floor.quick | 快速地面清洁 |
| delivery.* | 配送服务 |
| patrol.* | 巡检服务 |

### 6.4 修改机器人状态

（仅管理员）
```
PUT /api/v1/tasks/agents/{agent_id}/status?status=maintenance
```

---

## 7. 监控与报表

### 7.1 系统概览

```
GET /api/v1/tasks/stats/overview
```

**返回数据**：
```json
{
  "agents": {
    "total": 3,
    "ready": 2,
    "busy": 1,
    "offline": 0
  },
  "tasks": {
    "total": 150,
    "pending": 5,
    "completed": 140,
    "failed": 5
  }
}
```

### 7.2 Temporal 监控

访问 Temporal Web UI：http://your-server:8233

可查看：
- 正在运行的工作流
- 历史工作流记录
- 工作流执行详情
- Activity 调用日志

### 7.3 健康检查

```
GET /health
```

返回 `{"status": "healthy"}` 表示系统正常。

---

## 8. 常见问题

### Q1: 任务一直显示"分配中"怎么办？

**可能原因**：
- 所有机器人都在忙
- 没有具备所需能力的机器人

**解决方案**：
1. 检查机器人状态
2. 等待机器人完成当前任务
3. 联系管理员添加机器人

### Q2: 配送机器人到了但没收到通知？

**可能原因**：
- 通知服务配置问题
- 用户ID配置错误

**解决方案**：
1. 确认 recipient_id 正确
2. 联系管理员检查通知配置

### Q3: 如何查看任务失败原因？

**方法**：
1. 查询工作流状态
2. 查看 error_message 字段
3. 在 Temporal UI 查看详细日志

### Q4: 紧急任务如何加急？

**方法**：
设置 priority 为 1（最高优先级）：
```json
{
  "floor_id": "floor-1",
  "cleaning_mode": "quick",
  "priority": 1
}
```

### Q5: 如何联系技术支持？

- 系统管理员：admin@company.com
- 技术支持：support@company.com
- 紧急热线：400-xxx-xxxx

---

## 附录

### A. 错误码说明

| 错误码 | 说明 | 处理建议 |
|--------|------|----------|
| WORKFLOW_NOT_FOUND | 工作流不存在 | 检查ID是否正确 |
| NO_AVAILABLE_AGENT | 无可用机器人 | 稍后重试 |
| TASK_TIMEOUT | 任务超时 | 联系管理员 |
| APPROVAL_TIMEOUT | 审批超时 | 重新提交 |

### B. 楼层/区域编码规则

| 格式 | 示例 | 说明 |
|------|------|------|
| floor-{n} | floor-1 | 楼层 |
| floor-{n}/zone-{x} | floor-1/zone-a | 楼层区域 |
| floor-{n}/room-{id} | floor-1/room-101 | 具体房间 |

### C. 快捷操作汇总

| 操作 | API | 方法 |
|------|-----|------|
| 创建清洁任务 | /api/v1/workflows/cleaning | POST |
| 创建配送任务 | /api/v1/delivery | POST |
| 确认取货 | /api/v1/delivery/{id}/confirm-pickup | POST |
| 确认收货 | /api/v1/delivery/{id}/confirm-delivery | POST |
| 查看机器人 | /api/v1/tasks/agents | GET |
| 系统状态 | /api/v1/tasks/stats/overview | GET |

---

**文档版本**: 1.0.0
**最后更新**: 2026-01-27
