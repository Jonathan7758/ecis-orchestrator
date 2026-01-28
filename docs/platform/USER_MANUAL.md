# ECIS 平台用户使用手册

**版本**: 1.0.0
**更新日期**: 2026-01-28
**适用版本**: ECIS MVP

---

## 目录

1. [平台概述](#1-平台概述)
2. [系统架构](#2-系统架构)
3. [可视化工作流设计器](#3-可视化工作流设计器)
4. [场景模板库](#4-场景模板库)
5. [API 接口参考](#5-api-接口参考)
6. [Agent 管理](#6-agent-管理)
7. [工作流监控](#7-工作流监控)
8. [最佳实践](#8-最佳实践)
9. [故障排除](#9-故障排除)

---

## 1. 平台概述

### 1.1 什么是 ECIS

ECIS (Enterprise Collective Intelligence System) 是一个企业级多智能体协作平台，用于协调机器人、设施系统和人员之间的任务执行。

### 1.2 核心能力

| 能力 | 说明 |
|------|------|
| **多Agent协作** | 机器人、设施、人员无缝协作 |
| **可视化设计** | 拖拽式工作流编辑器 |
| **场景模板** | 5个开箱即用的业务场景 |
| **任务编排** | Temporal 驱动的可靠执行 |
| **实时监控** | 工作流状态实时追踪 |

### 1.3 适用场景

- 商业楼宇智能化运维
- 机器人清洁任务调度
- 物品配送自动化
- 访客接待服务
- 安防巡逻管理

### 1.4 系统组件

| 组件 | 说明 | 端口 |
|------|------|------|
| 工作流设计器 | React 可视化编辑器 | 3000 |
| 编排器 | FastAPI 后端服务 | 8200 |
| Temporal | 工作流引擎 | 7233 |
| Temporal UI | 监控界面 | 8233 |

---

## 2. 系统架构

### 2.1 整体架构

```
┌─────────────────────────────────────────────────────────────────┐
│                        用户层 (User Layer)                        │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  │
│  │  工作流设计器    │  │   移动端 App    │  │   管理后台      │  │
│  │  (React Flow)   │  │   (Flutter)    │  │   (Admin)       │  │
│  └────────┬────────┘  └────────┬────────┘  └────────┬────────┘  │
│           │                    │                    │           │
├───────────┴────────────────────┴────────────────────┴───────────┤
│                       API 网关 (API Gateway)                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │                    编排器 (Orchestrator)                      │ │
│  │  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────┐ │ │
│  │  │ Workflows │  │ Activities│  │ Templates │  │ Dispatcher│ │ │
│  │  └───────────┘  └───────────┘  └───────────┘  └───────────┘ │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                              │                                    │
├──────────────────────────────┴────────────────────────────────────┤
│                    Temporal 工作流引擎                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  │
│  │  Service Robot  │  │ Property Facility│  │  Human Agent   │  │
│  │  (机器人系统)    │  │  (设施系统)      │  │  (人机协作)     │  │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘  │
│                         Agent 层                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 Agent 类型

| 类型 | 系统 | 能力示例 |
|------|------|---------|
| 机器人 | ecis-service-robot | 清洁、配送、巡逻、导航 |
| 设施 | ecis-property-facility | 电梯、门禁、照明、空调 |
| 人员 | ecis-human-agent | 审批、确认、人工介入 |

### 2.3 工作流引擎

ECIS 使用 Temporal 作为工作流引擎，提供:

- **可靠执行**: 自动重试和故障恢复
- **长时间运行**: 支持跨天/跨周的工作流
- **可观察性**: 完整的执行历史和状态追踪
- **可扩展性**: 水平扩展 Worker 处理能力

---

## 3. 可视化工作流设计器

### 3.1 界面布局

```
┌──────────────────────────────────────────────────────────────────┐
│                           工具栏                                  │
│  [新建] [保存] [验证] [发布] [撤销] [重做] [自动布局] [模板]       │
├──────────┬───────────────────────────────────────────┬───────────┤
│          │                                           │           │
│  节点    │                                           │  属性     │
│  面板    │                                           │  面板     │
│          │                                           │           │
│ [开始]   │              画  布  区  域               │ 节点名称  │
│ [结束]   │                                           │ ────────  │
│ [任务]   │                                           │ 能力选择  │
│ [决策]   │                                           │ ────────  │
│ [等待]   │                                           │ 参数配置  │
│ [审批]   │                                           │ ────────  │
│ [并行]   │                                           │ 超时设置  │
│ [子流程] │                                           │           │
│ [通知]   │                                           │           │
│          │                                           │           │
│          ├───────────────────────────────────────────┤           │
│          │              迷你地图                      │           │
└──────────┴───────────────────────────────────────────┴───────────┘
```

### 3.2 节点类型

#### 流程控制节点

| 节点 | 图标 | 说明 | 连接点 |
|------|------|------|--------|
| 开始 | ⚪ | 工作流起点 | 1个输出 |
| 结束 | ⬛ | 工作流终点 | 1个输入 |
| 决策 | ◇ | 条件分支 | 1入2出 |
| 并行 | ═ | 并行执行 | 1入多出 |
| 子流程 | ▢ | 嵌套工作流 | 1入1出 |

#### 操作节点

| 节点 | 图标 | 说明 | 配置项 |
|------|------|------|--------|
| 任务 | ▣ | 执行Agent能力 | 能力、参数、超时、重试 |
| 等待 | ⏳ | 等待条件/信号 | 超时时间、等待条件 |
| 审批 | ✓ | 人工审批 | 审批人、超时、自动拒绝 |
| 通知 | ✉ | 发送通知 | 通道、收件人、消息 |

### 3.3 基本操作

#### 添加节点

1. 在左侧节点面板找到需要的节点
2. 拖拽节点到画布
3. 释放鼠标完成添加

#### 连接节点

1. 将鼠标移到节点边缘的连接点
2. 按住并拖动到目标节点的连接点
3. 释放完成连接

#### 配置节点

1. 点击节点选中
2. 在右侧属性面板编辑
3. 属性自动保存

#### 删除节点/连线

1. 选中要删除的元素
2. 按 `Delete` 键
3. 或右键选择「删除」

### 3.4 画布操作

| 操作 | 方式 |
|------|------|
| 缩放 | 滚轮滚动 |
| 平移 | 拖动画布空白区域 |
| 多选 | Shift + 拖动框选 |
| 全选 | Ctrl + A |
| 适应视图 | 双击画布空白 |

### 3.5 工作流验证

点击「验证」按钮检查工作流:

**验证规则**:
- ✅ 必须有且仅有一个开始节点
- ✅ 必须有至少一个结束节点
- ✅ 所有节点必须连接
- ✅ 不能有孤立节点
- ✅ 任务节点必须配置能力
- ✅ 决策节点必须有条件表达式

**验证结果**:
- 通过: 绿色提示「验证通过」
- 失败: 红色提示具体错误

### 3.6 保存与发布

#### 保存草稿

1. 点击「保存」按钮
2. 输入工作流名称和描述
3. 点击确认保存

#### 发布工作流

1. 确保验证通过
2. 点击「发布」按钮
3. 确认发布

**注意**: 发布后的工作流可被调用执行

---

## 4. 场景模板库

### 4.1 模板概览

| 模板ID | 名称 | 分类 | 优先级 |
|--------|------|------|--------|
| robot-cleaning-workflow | 机器人清洁工作流 | cleaning | P0 |
| robot-delivery-workflow | 机器人配送工作流 | delivery | P1 |
| emergency-charging-workflow | 紧急充电工作流 | maintenance | P0 |
| visitor-welcome-workflow | 访客迎宾工作流 | service | P1 |
| patrol-inspection-workflow | 巡逻检查工作流 | security | P2 |

### 4.2 机器人清洁工作流

**场景**: 机器人自动清洁指定区域

**流程**:
1. 检查机器人状态
2. 判断电量是否充足 (>20%)
3. 判断是否需要跨楼层
4. 如需跨楼层，调用电梯
5. 开启沿途门禁
6. 执行清洁任务
7. 发送完成通知

**变量**:

| 变量 | 类型 | 必填 | 说明 |
|------|------|------|------|
| robot_id | string | 是 | 机器人ID |
| target_floor | number | 是 | 目标楼层 |
| area_id | string | 是 | 清洁区域ID |
| cleaning_type | string | 否 | quick/standard/deep |
| notify_on_complete | boolean | 否 | 完成时通知 |

### 4.3 机器人配送工作流

**场景**: 机器人自动配送物品

**流程**:
1. 检查机器人状态
2. 前往取件点
3. 等待装载
4. 判断是否跨楼层
5. 前往送达点
6. 通知收件人
7. 等待取件
8. 处理超时情况

**变量**:

| 变量 | 类型 | 必填 | 说明 |
|------|------|------|------|
| robot_id | string | 是 | 配送机器人ID |
| pickup_location | string | 是 | 取件位置 |
| delivery_location | string | 是 | 送达位置 |
| recipient_id | string | 是 | 收件人ID |
| recipient_phone | string | 否 | 收件人电话 |
| pickup_timeout | number | 否 | 取件超时(秒) |
| delivery_timeout | number | 否 | 送达超时(秒) |

### 4.4 紧急充电工作流

**场景**: 机器人电量过低时自动充电

**流程**:
1. 暂停当前任务
2. 查找最近充电站
3. 导航到充电站
4. 开始充电
5. 等待充电完成
6. 恢复原任务

**变量**:

| 变量 | 类型 | 必填 | 说明 |
|------|------|------|------|
| robot_id | string | 是 | 机器人ID |
| current_task_id | string | 否 | 当前任务ID |
| min_charge_level | number | 否 | 最低充电量% |
| notify_ops | boolean | 否 | 通知运维 |

### 4.5 访客迎宾工作流

**场景**: 机器人迎接访客并引导至目的地

**流程**:
1. 验证访客信息
2. 分配迎宾机器人
3. 前往大堂
4. 播放欢迎语
5. 引导访客（如需跨楼层，调用电梯）
6. 通知被访人

**变量**:

| 变量 | 类型 | 必填 | 说明 |
|------|------|------|------|
| visitor_name | string | 是 | 访客姓名 |
| host_id | string | 是 | 被访人ID |
| destination | string | 是 | 目的地 |
| welcome_message | string | 否 | 欢迎语 |
| vip_mode | boolean | 否 | VIP模式 |

### 4.6 巡逻检查工作流

**场景**: 机器人/无人机自动巡逻检查

**流程**:
1. 加载巡逻路线
2. 前往起点
3. 循环各检查点
4. 执行巡检
5. 如发现异常，记录并拍照
6. 紧急情况立即告警
7. 生成巡检报告

**变量**:

| 变量 | 类型 | 必填 | 说明 |
|------|------|------|------|
| robot_id | string | 是 | 巡逻设备ID |
| robot_type | string | 否 | patrol_robot/drone/robot_dog |
| route_id | string | 是 | 巡逻路线ID |
| inspection_items | array | 否 | 检查项目 |
| alert_on_anomaly | boolean | 否 | 异常告警 |
| generate_report | boolean | 否 | 生成报告 |

### 4.7 使用模板

#### 在设计器中使用

1. 点击工具栏「模板」按钮
2. 选择所需模板
3. 填写变量参数
4. 点击「创建」
5. 根据需要调整节点
6. 保存并发布

#### 通过 API 使用

```bash
# 基于模板启动工作流
curl -X POST http://localhost:8200/api/v1/workflows/start \
  -H "Content-Type: application/json" \
  -d '{
    "template_id": "robot-cleaning-workflow",
    "input": {
      "robot_id": "robot-001",
      "target_floor": 5,
      "area_id": "zone-a"
    }
  }'
```

---

## 5. API 接口参考

### 5.1 认证

当前版本暂未启用认证，生产环境建议配置 JWT 认证。

### 5.2 基础端点

#### 健康检查

```
GET /health

响应:
{
  "status": "healthy",
  "service": "ecis-orchestrator",
  "version": "0.1.0"
}
```

#### 就绪检查

```
GET /ready

响应:
{
  "status": "ready",
  "temporal": "connected"
}
```

### 5.3 模板接口

#### 列出模板

```
GET /api/v1/templates
GET /api/v1/templates?category=cleaning

响应:
{
  "templates": [...],
  "total": 5,
  "categories": ["cleaning", "delivery", "maintenance", "service", "security"]
}
```

#### 获取模板详情

```
GET /api/v1/templates/{template_id}

响应:
{
  "template_id": "robot-cleaning-workflow",
  "name": "机器人清洁工作流",
  "variables": [...],
  "nodes": [...],
  "edges": [...]
}
```

#### 验证模板输入

```
POST /api/v1/templates/{template_id}/validate
Content-Type: application/json

{
  "input": {
    "robot_id": "robot-001",
    "target_floor": 5
  }
}

响应:
{
  "valid": true,
  "errors": []
}
```

### 5.4 Agent 接口

#### 列出 Agent

```
GET /api/v1/tasks/agents

响应:
[
  {
    "agent_id": "robot-001",
    "agent_type": "robot",
    "capabilities": ["cleaning.floor.standard"],
    "status": "ready",
    "current_load": 0,
    "max_load": 5
  }
]
```

#### 注册 Agent

```
POST /api/v1/tasks/agents
Content-Type: application/json

{
  "agent_id": "robot-new",
  "agent_type": "robot",
  "capabilities": ["cleaning.floor.standard"],
  "max_load": 5
}

响应:
{
  "status": "registered",
  "agent_id": "robot-new"
}
```

#### 更新 Agent 状态

```
PUT /api/v1/tasks/agents/{agent_id}/status?status=busy

响应:
{
  "agent_id": "robot-001",
  "old_status": "ready",
  "new_status": "busy"
}
```

#### 查找可用 Agent

```
GET /api/v1/tasks/agents/available?capability=cleaning.floor.standard

响应:
[
  {
    "agent_id": "robot-001",
    "agent_type": "robot",
    "capabilities": ["cleaning.floor.standard"],
    "status": "ready",
    "current_load": 0
  }
]
```

### 5.5 任务接口

#### 分派任务

```
POST /api/v1/tasks/dispatch
Content-Type: application/json

{
  "capability": "cleaning.floor.standard",
  "parameters": {
    "floor": "floor-5",
    "zone": "zone-a"
  },
  "priority": 3
}

响应:
{
  "task_id": "task-xxx",
  "agent_id": "robot-001",
  "status": "assigned"
}
```

#### 完成任务

```
POST /api/v1/tasks/{task_id}/complete?success=true

响应:
{
  "task_id": "task-xxx",
  "status": "completed",
  "completed_at": "2026-01-28T10:30:00Z"
}
```

#### 获取统计信息

```
GET /api/v1/tasks/stats/overview

响应:
{
  "agents": {
    "total": 5,
    "ready": 3,
    "busy": 2,
    "offline": 0
  },
  "tasks": {
    "total": 100,
    "pending": 5,
    "running": 10,
    "completed": 80,
    "failed": 5
  }
}
```

---

## 6. Agent 管理

### 6.1 Agent 类型

#### 机器人 Agent (robot)

| 能力 | 说明 |
|------|------|
| cleaning.floor.standard | 标准地面清洁 |
| cleaning.floor.deep | 深度地面清洁 |
| delivery.* | 配送能力 |
| patrol.* | 巡逻能力 |
| navigation.* | 导航能力 |

#### 设施 Agent (facility)

| 能力 | 说明 |
|------|------|
| elevator.call | 呼叫电梯 |
| elevator.control | 控制电梯 |
| access.door | 门禁控制 |
| access.route | 路径门禁 |
| lighting.control | 照明控制 |
| hvac.control | 空调控制 |

#### 人员 Agent (human)

| 能力 | 说明 |
|------|------|
| approval.* | 审批能力 |
| confirmation.* | 确认能力 |
| intervention.* | 人工介入 |

### 6.2 Agent 状态

| 状态 | 说明 |
|------|------|
| ready | 就绪，可接收任务 |
| busy | 忙碌，正在执行任务 |
| maintenance | 维护中 |
| offline | 离线 |
| error | 错误状态 |

### 6.3 负载均衡

系统自动进行任务负载均衡:

1. 查找具有所需能力的 Agent
2. 过滤出状态为 ready 的 Agent
3. 选择当前负载最低的 Agent
4. 分配任务并更新负载

---

## 7. 工作流监控

### 7.1 Temporal UI

访问 http://localhost:8233 查看工作流状态。

#### 工作流列表

- 查看所有运行中的工作流
- 按状态过滤 (Running/Completed/Failed)
- 按时间范围过滤

#### 工作流详情

- 执行历史 (每个步骤的开始/结束时间)
- 输入输出数据
- 错误信息
- 重试历史

### 7.2 状态查询 API

```bash
# 获取任务统计
curl http://localhost:8200/api/v1/tasks/stats/overview
```

### 7.3 日志查看

```bash
# 查看编排器日志
docker logs ecis-orchestrator -f

# 查看 Temporal 日志
docker logs ecis-temporal -f
```

---

## 8. 最佳实践

### 8.1 工作流设计

1. **保持简单**: 每个工作流专注于一个业务场景
2. **合理拆分**: 复杂流程拆分为多个子流程
3. **错误处理**: 添加错误分支和重试配置
4. **超时设置**: 为每个任务设置合理的超时时间
5. **通知机制**: 在关键节点添加通知

### 8.2 任务超时配置

| 任务类型 | 建议超时 |
|---------|---------|
| 状态检查 | 30秒 |
| 导航移动 | 300秒 (5分钟) |
| 清洁任务 | 7200秒 (2小时) |
| 等待装载 | 300秒 |
| 人工审批 | 3600秒 (1小时) |

### 8.3 重试策略

```json
{
  "retry": {
    "max_attempts": 3,
    "initial_interval": 30,
    "backoff_coefficient": 2,
    "max_interval": 300
  }
}
```

### 8.4 能力命名规范

```
{domain}.{action}.{variant}

示例:
- cleaning.floor.standard
- delivery.package.express
- facility.elevator.call
```

---

## 9. 故障排除

### 9.1 常见问题

#### 工作流启动失败

**原因**: Temporal 连接失败或 Worker 未启动

**解决**:
```bash
# 检查 Temporal 状态
docker ps | grep temporal

# 重启 Temporal
docker-compose restart temporal

# 重启 Worker
python -m app.workers.main_worker
```

#### Agent 无法分配任务

**原因**: 无可用 Agent 或能力不匹配

**解决**:
```bash
# 查看可用 Agent
curl http://localhost:8200/api/v1/tasks/agents

# 检查能力匹配
curl "http://localhost:8200/api/v1/tasks/agents/available?capability=xxx"
```

#### 工作流验证失败

**常见错误**:
- 缺少开始/结束节点
- 存在孤立节点
- 任务节点未配置能力

#### 模板加载失败

**解决**:
```bash
# 重新加载模板
curl -X POST http://localhost:8200/api/v1/templates/reload
```

### 9.2 日志分析

```bash
# 查看错误日志
docker logs ecis-orchestrator 2>&1 | grep ERROR

# 查看 Temporal Worker 日志
docker logs ecis-worker 2>&1 | grep -i error
```

### 9.3 联系支持

如遇到无法解决的问题，请提供以下信息:

1. 错误信息截图
2. 工作流 ID
3. 相关日志
4. 重现步骤

---

## 附录

### A. 快捷键

| 快捷键 | 功能 |
|--------|------|
| Ctrl+S | 保存 |
| Ctrl+Z | 撤销 |
| Ctrl+Y | 重做 |
| Ctrl+A | 全选 |
| Delete | 删除 |
| Escape | 取消选择 |

### B. 术语表

| 术语 | 说明 |
|------|------|
| Agent | 可执行任务的智能体 |
| Capability | Agent 的能力标识 |
| Workflow | 工作流定义 |
| Activity | 工作流中的单个操作 |
| Temporal | 工作流引擎 |
| Worker | 执行工作流的进程 |

### C. 版本历史

| 版本 | 日期 | 说明 |
|------|------|------|
| 1.0.0 | 2026-01-28 | 初始版本 |

---

**文档版本**: 1.0.0
**最后更新**: 2026-01-28
**版权所有**: ECIS Team
