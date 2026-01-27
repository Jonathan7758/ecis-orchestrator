"""
Workflows 模块

Temporal Workflow 定义
"""

from .approval import (
    ApprovalWorkflow,
    ApprovalWorkflowInput,
    ApprovalWorkflowResult,
    MultiStageApprovalWorkflow,
)
from .cleaning import (
    CleaningWorkflowInput,
    CleaningWorkflowResult,
    RobotCleaningWorkflow,
)
from .delivery import (
    DeliveryWorkflow,
    DeliveryWorkflowInput,
    DeliveryWorkflowResult,
)
from .scheduled import (
    ScheduledCleaningWorkflow,
    ScheduledPatrolWorkflow,
    ScheduledTaskInput,
    ScheduledTaskResult,
)

__all__ = [
    # Cleaning
    "RobotCleaningWorkflow",
    "CleaningWorkflowInput",
    "CleaningWorkflowResult",
    # Approval
    "ApprovalWorkflow",
    "ApprovalWorkflowInput",
    "ApprovalWorkflowResult",
    "MultiStageApprovalWorkflow",
    # Delivery
    "DeliveryWorkflow",
    "DeliveryWorkflowInput",
    "DeliveryWorkflowResult",
    # Scheduled
    "ScheduledCleaningWorkflow",
    "ScheduledPatrolWorkflow",
    "ScheduledTaskInput",
    "ScheduledTaskResult",
]
