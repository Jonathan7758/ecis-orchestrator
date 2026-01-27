"""
Federation Client - 连接 ECIS Federation Gateway
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field

import httpx

logger = logging.getLogger("ecis_robot.federation")


@dataclass
class FederationConfig:
    """Federation 配置"""
    gateway_url: str
    system_id: str
    system_type: str = "property-service"
    display_name: str = "ECIS Service Robot"
    reconnect_interval: int = 30
    heartbeat_interval: int = 30
    max_reconnect_attempts: int = 10


@dataclass
class RegisteredAgent:
    """已注册的 Agent 信息"""
    agent_id: str
    agent_type: str
    capabilities: List[str]
    token: str
    registered_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class FederationClient:
    """
    Federation 客户端

    负责与 ECIS Federation Gateway 通信
    """

    def __init__(
        self,
        gateway_url: str,
        system_id: str,
        system_type: str = "property-service",
        display_name: str = "ECIS Service Robot",
        reconnect_interval: int = 30,
        heartbeat_interval: int = 30,
        max_reconnect_attempts: int = 10
    ):
        self.config = FederationConfig(
            gateway_url=gateway_url.rstrip("/"),
            system_id=system_id,
            system_type=system_type,
            display_name=display_name,
            reconnect_interval=reconnect_interval,
            heartbeat_interval=heartbeat_interval,
            max_reconnect_attempts=max_reconnect_attempts
        )

        self._client: Optional[httpx.AsyncClient] = None
        self._system_token: Optional[str] = None
        self._is_connected: bool = False
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._reconnect_attempts: int = 0
        self._registered_agents: Dict[str, RegisteredAgent] = {}
        self._last_heartbeat: Optional[datetime] = None

    @property
    def is_connected(self) -> bool:
        return self._is_connected

    @property
    def system_id(self) -> str:
        return self.config.system_id

    @property
    def registered_agents(self) -> Dict[str, RegisteredAgent]:
        return self._registered_agents

    @property
    def last_heartbeat(self) -> Optional[datetime]:
        return self._last_heartbeat

    async def connect(self) -> bool:
        try:
            self._client = httpx.AsyncClient(timeout=30.0)

            response = await self._client.post(
                f"{self.config.gateway_url}/api/v1/systems/register",
                json={
                    "system_id": self.config.system_id,
                    "system_type": self.config.system_type,
                    "display_name": self.config.display_name,
                    "capabilities": ["cleaning", "delivery", "patrol"]
                }
            )

            if response.status_code == 200:
                data = response.json()
                self._system_token = data.get("token")
                self._is_connected = True
                self._reconnect_attempts = 0
                self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
                logger.info(f"Connected to Federation Gateway: {self.config.gateway_url}")
                return True
            else:
                logger.error(f"Failed to register system: {response.status_code}")
                return False

        except Exception as e:
            logger.error(f"Failed to connect to Federation Gateway: {e}")
            return False

    async def disconnect(self) -> None:
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass

        if self._client:
            await self._client.aclose()

        self._is_connected = False
        self._system_token = None
        logger.info("Disconnected from Federation Gateway")

    async def reconnect(self) -> bool:
        if self._reconnect_attempts >= self.config.max_reconnect_attempts:
            logger.error("Max reconnect attempts reached")
            return False

        self._reconnect_attempts += 1
        await self.disconnect()
        logger.info(f"Attempting to reconnect ({self._reconnect_attempts}/{self.config.max_reconnect_attempts})")
        await asyncio.sleep(self.config.reconnect_interval)
        return await self.connect()

    async def register_agent(self, agent_id: str, agent_type: str, capabilities: List[str]) -> Optional[str]:
        if not self._is_connected:
            logger.warning("Not connected to Federation Gateway")
            return None

        try:
            response = await self._client.post(
                f"{self.config.gateway_url}/api/v1/agents/register",
                headers={"Authorization": f"Bearer {self._system_token}"},
                json={
                    "agent_id": agent_id,
                    "agent_type": agent_type,
                    "system_id": self.config.system_id,
                    "capabilities": capabilities
                }
            )

            if response.status_code == 200:
                data = response.json()
                token = data.get("token")
                self._registered_agents[agent_id] = RegisteredAgent(
                    agent_id=agent_id,
                    agent_type=agent_type,
                    capabilities=capabilities,
                    token=token
                )
                logger.info(f"Registered agent: {agent_id}")
                return token
            else:
                logger.error(f"Failed to register agent: {response.status_code}")
                return None
        except Exception as e:
            logger.error(f"Failed to register agent: {e}")
            return None

    async def publish_event(self, event: Dict[str, Any]) -> Optional[str]:
        if not self._is_connected:
            return None

        try:
            response = await self._client.post(
                f"{self.config.gateway_url}/api/v1/events",
                headers={"Authorization": f"Bearer {self._system_token}"},
                json=event
            )

            if response.status_code == 200:
                return response.json().get("event_id")
            return None
        except Exception as e:
            logger.error(f"Failed to publish event: {e}")
            return None

    async def list_registered_agents(self) -> List[Dict[str, Any]]:
        return [
            {
                "agent_id": agent.agent_id,
                "agent_type": agent.agent_type,
                "capabilities": agent.capabilities,
                "registered_at": agent.registered_at.isoformat()
            }
            for agent in self._registered_agents.values()
        ]

    async def _heartbeat_loop(self) -> None:
        while self._is_connected:
            try:
                await asyncio.sleep(self.config.heartbeat_interval)
                if not self._is_connected:
                    break

                response = await self._client.post(
                    f"{self.config.gateway_url}/api/v1/systems/{self.config.system_id}/heartbeat",
                    headers={"Authorization": f"Bearer {self._system_token}"}
                )

                if response.status_code == 200:
                    self._last_heartbeat = datetime.now(timezone.utc)
                else:
                    logger.warning(f"Heartbeat failed: {response.status_code}")
                    await self.reconnect()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Heartbeat error: {e}")
                await self.reconnect()
