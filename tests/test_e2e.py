"""
端到端测试

测试工作流的完整执行流程
"""

import asyncio
import sys

from temporalio.client import Client

# 添加项目路径
sys.path.insert(0, "/root/projects/ecis/ecis-orchestrator")

from src.core.config import get_config
from src.workflows.cleaning import CleaningWorkflowInput, RobotCleaningWorkflow
from src.workflows.approval import ApprovalWorkflow, ApprovalWorkflowInput


async def test_cleaning_workflow():
    """测试清洁工作流"""
    config = get_config()
    client = await Client.connect(config.temporal.address)

    print("=" * 50)
    print("Testing Cleaning Workflow")
    print("=" * 50)

    input_data = CleaningWorkflowInput(
        floor_id="floor-3",
        zone_id="zone-a",
        cleaning_mode="standard",
        priority=3,
    )

    # 启动工作流
    workflow_id = f"test-cleaning-{int(asyncio.get_event_loop().time())}"
    print(f"Starting workflow: {workflow_id}")

    handle = await client.start_workflow(
        RobotCleaningWorkflow.run,
        input_data,
        id=workflow_id,
        task_queue=config.temporal.task_queue,
    )

    print(f"Workflow started: {handle.id}")

    # 查询状态
    status = await handle.query("get_status")
    print(f"Initial status: {status}")

    # 等待结果
    print("Waiting for result...")
    result = await handle.result()

    print(f"Result: success={result.success}, robot_id={result.robot_id}")
    print(f"Message: {result.message}")
    print(f"Duration: {result.duration_minutes} minutes")
    print(f"Area cleaned: {result.area_cleaned_sqm} sqm")

    return result.success


async def test_approval_workflow():
    """测试审批工作流"""
    config = get_config()
    client = await Client.connect(config.temporal.address)

    print("\n" + "=" * 50)
    print("Testing Approval Workflow")
    print("=" * 50)

    input_data = ApprovalWorkflowInput(
        request_type="test_approval",
        title="测试审批",
        description="这是一个测试审批请求",
        data={"floor": 3, "reason": "Test"},
        approvers=["manager-001"],
        timeout_hours=1,
    )

    # 启动工作流
    workflow_id = f"test-approval-{int(asyncio.get_event_loop().time())}"
    print(f"Starting workflow: {workflow_id}")

    handle = await client.start_workflow(
        ApprovalWorkflow.run,
        input_data,
        id=workflow_id,
        task_queue=config.temporal.task_queue,
    )

    print(f"Workflow started: {handle.id}")

    # 等待工作流初始化
    await asyncio.sleep(2)

    # 查询状态
    status = await handle.query("get_status")
    print(f"Status before approval: {status}")

    # 发送 approve 信号
    print("Sending approve signal...")
    await handle.signal(ApprovalWorkflow.approve, args=["tester", "Test approved", None])

    # 等待结果
    print("Waiting for result...")
    result = await handle.result()

    print(f"Result: status={result.status}")
    print(f"Decided by: {result.decided_by}")
    print(f"Reason: {result.reason}")

    return result.status == "approved"


async def main():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("  ECIS Orchestrator End-to-End Tests")
    print("=" * 60 + "\n")

    results = {}

    try:
        results["cleaning"] = await test_cleaning_workflow()
    except Exception as e:
        print(f"Cleaning workflow test failed: {e}")
        results["cleaning"] = False

    try:
        results["approval"] = await test_approval_workflow()
    except Exception as e:
        print(f"Approval workflow test failed: {e}")
        results["approval"] = False

    # 打印总结
    print("\n" + "=" * 60)
    print("  Test Results Summary")
    print("=" * 60)

    all_passed = True
    for name, passed in results.items():
        status = "✓ PASSED" if passed else "✗ FAILED"
        print(f"  {name}: {status}")
        if not passed:
            all_passed = False

    print("=" * 60)

    if all_passed:
        print("All tests passed!")
        return 0
    else:
        print("Some tests failed!")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
