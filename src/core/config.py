"""
配置管理模块

职责：
- 环境变量加载
- 配置验证
- 配置单例管理
"""

from typing import Optional

from pydantic import ConfigDict
from pydantic_settings import BaseSettings


class TemporalConfig(BaseSettings):
    """Temporal 配置"""

    model_config = ConfigDict(env_prefix="TEMPORAL_")

    host: str = "localhost"
    port: int = 7233
    namespace: str = "default"
    task_queue: str = "ecis-orchestrator-queue"

    @property
    def address(self) -> str:
        return f"{self.host}:{self.port}"


class DatabaseConfig(BaseSettings):
    """数据库配置"""

    model_config = ConfigDict(env_prefix="DATABASE_")

    url: str = "postgresql+asyncpg://temporal:temporal@localhost:5434/orchestrator"
    pool_size: int = 10
    max_overflow: int = 20


class RedisConfig(BaseSettings):
    """Redis 配置"""

    model_config = ConfigDict(env_prefix="REDIS_")

    url: str = "redis://localhost:6380"


class FederationConfig(BaseSettings):
    """Federation 配置"""

    model_config = ConfigDict(env_prefix="FEDERATION_")

    enabled: bool = True
    gateway_url: str = "http://localhost:8100"
    system_id: str = "orchestrator"
    heartbeat_interval: int = 30


class LLMConfig(BaseSettings):
    """LLM 配置"""

    model_config = ConfigDict(env_prefix="ANTHROPIC_")

    api_key: str = ""
    model: str = "claude-3-sonnet-20240229"
    max_tokens: int = 4096


class AppConfig(BaseSettings):
    """应用配置"""

    model_config = ConfigDict(env_prefix="APP_")

    debug: bool = True
    log_level: str = "INFO"
    host: str = "0.0.0.0"
    port: int = 8200


class Config(BaseSettings):
    """主配置"""

    app: AppConfig = AppConfig()
    temporal: TemporalConfig = TemporalConfig()
    database: DatabaseConfig = DatabaseConfig()
    redis: RedisConfig = RedisConfig()
    federation: FederationConfig = FederationConfig()
    llm: LLMConfig = LLMConfig()


# 单例
_config: Optional[Config] = None


def get_config() -> Config:
    """获取配置单例"""
    global _config
    if _config is None:
        _config = Config()
    return _config


def reset_config() -> None:
    """重置配置（用于测试）"""
    global _config
    _config = None
