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
]
