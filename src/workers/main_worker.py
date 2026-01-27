"""
主 Worker

注册所有工作流和 Activity，启动 Temporal Worker
"""

import asyncio
import logging
import signal
import sys

from temporalio.client import Client
from temporalio.worker import Worker

from src.core.config import get_config

# 导入所有工作流
from src.workflows.cleaning import RobotCleaningWorkflow
from src.workflows.approval import ApprovalWorkflow, MultiStageApprovalWorkflow

# 导入所有 Activity
from src.activities.robot import (
    get_robot_status,
    assign_task_to_robot,
    wait_for_robot_task_completion,
    get_robot_location,
    find_available_robot,
)
from src.activities.facility import (
    call_elevator,
    open_door,
    close_door,
    get_doors_on_route,
    grant_zone_access,
    revoke_zone_access,
    get_floor_status,
)
from src.activities.notification import (
    send_notification,
    create_approval_request,
    get_approval_status,
    send_approval_reminder,
    cancel_approval_request,
)
from src.activities.llm import (
    analyze_task_request,
    analyze_exception,
    generate_task_summary,
    extract_workflow_parameters,
)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# 所有工作流类
WORKFLOWS = [
    RobotCleaningWorkflow,
    ApprovalWorkflow,
    MultiStageApprovalWorkflow,
]

# 所有 Activity 函数
ACTIVITIES = [
    # Robot
    get_robot_status,
    assign_task_to_robot,
    wait_for_robot_task_completion,
    get_robot_location,
    find_available_robot,
    # Facility
    call_elevator,
    open_door,
    close_door,
    get_doors_on_route,
    grant_zone_access,
    revoke_zone_access,
    get_floor_status,
    # Notification
    send_notification,
    create_approval_request,
    get_approval_status,
    send_approval_reminder,
    cancel_approval_request,
    # LLM
    analyze_task_request,
    analyze_exception,
    generate_task_summary,
    extract_workflow_parameters,
]


async def run_worker():
    """启动 Worker"""
    config = get_config()

    logger.info(f"Connecting to Temporal: {config.temporal.address}")
    client = await Client.connect(config.temporal.address)

    logger.info(f"Starting worker on queue: {config.temporal.task_queue}")
    worker = Worker(
        client,
        task_queue=config.temporal.task_queue,
        workflows=WORKFLOWS,
        activities=ACTIVITIES,
    )

    # 设置优雅关闭
    shutdown_event = asyncio.Event()

    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}, initiating shutdown...")
        shutdown_event.set()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    logger.info("Worker started, waiting for tasks...")
    logger.info(f"Registered {len(WORKFLOWS)} workflows and {len(ACTIVITIES)} activities")

    # 运行 worker 直到收到关闭信号
    async with worker:
        await shutdown_event.wait()

    logger.info("Worker shutdown complete")


def main():
    """入口函数"""
    try:
        asyncio.run(run_worker())
    except KeyboardInterrupt:
        logger.info("Worker interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Worker failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
