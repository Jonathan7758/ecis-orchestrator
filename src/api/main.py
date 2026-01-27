"""
FastAPI 应用主入口

提供 REST API 接口
"""

from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from temporalio.client import Client

from src.core.config import get_config

# 全局 Temporal 客户端
temporal_client: Optional[Client] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    global temporal_client

    config = get_config()

    # 启动时连接 Temporal
    print(f"Connecting to Temporal: {config.temporal.address}")
    temporal_client = await Client.connect(config.temporal.address)
    print("Connected to Temporal")

    yield

    # 关闭时清理
    print("Shutting down...")


# 创建 FastAPI 应用
app = FastAPI(
    title="ECIS Orchestrator API",
    description="Workflow orchestration service for ECIS platform",
    version="0.1.0",
    lifespan=lifespan,
)

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应该限制
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_temporal_client() -> Client:
    """获取 Temporal 客户端"""
    if temporal_client is None:
        raise RuntimeError("Temporal client not initialized")
    return temporal_client


# 健康检查
@app.get("/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "service": "ecis-orchestrator",
        "version": "0.1.0",
    }


@app.get("/ready")
async def readiness_check():
    """就绪检查"""
    try:
        client = get_temporal_client()
        # 尝试连接 Temporal
        await client.service_client.check_health()
        return {"status": "ready", "temporal": "connected"}
    except Exception as e:
        return {"status": "not_ready", "error": str(e)}


# 导入路由
from src.api.routes import workflows, approvals

app.include_router(workflows.router, prefix="/api/v1")
app.include_router(approvals.router, prefix="/api/v1")


if __name__ == "__main__":
    import uvicorn

    config = get_config()
    uvicorn.run(
        "src.api.main:app",
        host=config.app.host,
        port=config.app.port,
        reload=config.app.debug,
    )
