"""
Federation 模块

提供与 Federation Gateway 的集成
"""

from src.federation.federation_client import (
    FederationClient,
    FederationConfig,
    RegisteredAgent,
)

__all__ = [
    "FederationClient",
    "FederationConfig",
    "RegisteredAgent",
]
