"""cctvQL component for Viseron.

Provides a natural-language query layer across your cameras by connecting
Viseron to a running cctvQL server (https://github.com/arunrajiah/cctvql).

Configuration example (config.yaml):

    cctvql:
      host: 192.168.1.50
      port: 8000
      api_key: ""          # optional
      scan_interval: 30
      auto_enrich: false   # set true to auto-query on every detection
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

import httpx
import voluptuous as vol

from viseron.components.cctvql.const import (
    COMPONENT,
    CONFIG_API_KEY,
    CONFIG_AUTO_ENRICH,
    CONFIG_HOST,
    CONFIG_PORT,
    CONFIG_SCAN_INTERVAL,
    DEFAULT_AUTO_ENRICH,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DESC_API_KEY,
    DESC_AUTO_ENRICH,
    DESC_HOST,
    DESC_PORT,
    DESC_SCAN_INTERVAL,
)

if TYPE_CHECKING:
    from viseron import Viseron

LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA: vol.Schema = vol.Schema(
    {
        vol.Required(COMPONENT, description="cctvQL integration"): vol.Schema(
            {
                vol.Required(CONFIG_HOST, description=DESC_HOST): str,
                vol.Optional(
                    CONFIG_PORT,
                    default=DEFAULT_PORT,
                    description=DESC_PORT,
                ): vol.Coerce(int),
                vol.Optional(
                    CONFIG_API_KEY,
                    default=None,
                    description=DESC_API_KEY,
                ): vol.Any(str, None),
                vol.Optional(
                    CONFIG_SCAN_INTERVAL,
                    default=DEFAULT_SCAN_INTERVAL,
                    description=DESC_SCAN_INTERVAL,
                ): vol.All(vol.Coerce(int), vol.Range(min=5)),
                vol.Optional(
                    CONFIG_AUTO_ENRICH,
                    default=DEFAULT_AUTO_ENRICH,
                    description=DESC_AUTO_ENRICH,
                ): bool,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


def setup(vis: Viseron, config: dict[str, Any]) -> bool:
    """Set up the cctvQL component."""
    cfg = config[COMPONENT]
    client = CctvqlClient(
        host=cfg[CONFIG_HOST],
        port=cfg[CONFIG_PORT],
        api_key=cfg.get(CONFIG_API_KEY),
    )

    try:
        loop = asyncio.get_event_loop()
        health = loop.run_until_complete(client.health())
        LOGGER.info(
            "Connected to cctvQL at %s:%s — status: %s",
            cfg[CONFIG_HOST],
            cfg[CONFIG_PORT],
            health.get("status", "ok"),
        )
    except Exception as exc:
        LOGGER.error("Cannot connect to cctvQL at %s:%s — %s", cfg[CONFIG_HOST], cfg[CONFIG_PORT], exc)
        return False

    vis.data[COMPONENT] = CctvqlComponent(vis, cfg, client)
    return True


def unload(vis: Viseron) -> None:
    """Unload cctvQL component."""
    vis.data.pop(COMPONENT, None)
    LOGGER.debug("cctvQL component unloaded")


# ---------------------------------------------------------------------------
# HTTP client
# ---------------------------------------------------------------------------


class CctvqlClient:
    """Async HTTP client for the cctvQL REST API."""

    def __init__(self, host: str, port: int, api_key: str | None = None) -> None:
        self.base_url = f"http://{host}:{port}"
        self._headers: dict[str, str] = {}
        if api_key:
            self._headers["X-API-Key"] = api_key
        self._timeout = httpx.Timeout(10.0)

    async def health(self) -> dict[str, Any]:
        async with httpx.AsyncClient(headers=self._headers, timeout=self._timeout) as c:
            resp = await c.get(f"{self.base_url}/health")
            resp.raise_for_status()
            return resp.json()

    async def query(self, query_text: str, session_id: str = "viseron") -> dict[str, Any]:
        async with httpx.AsyncClient(headers=self._headers, timeout=self._timeout) as c:
            resp = await c.post(
                f"{self.base_url}/query",
                json={"query": query_text, "session_id": session_id},
            )
            resp.raise_for_status()
            return resp.json()

    async def cameras(self) -> list[dict[str, Any]]:
        async with httpx.AsyncClient(headers=self._headers, timeout=self._timeout) as c:
            resp = await c.get(f"{self.base_url}/cameras")
            resp.raise_for_status()
            return resp.json()

    async def events(
        self,
        camera: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"limit": limit}
        if camera:
            params["camera"] = camera
        async with httpx.AsyncClient(headers=self._headers, timeout=self._timeout) as c:
            resp = await c.get(f"{self.base_url}/events", params=params)
            resp.raise_for_status()
            return resp.json()

    async def ptz(
        self,
        camera_id: str,
        action: str,
        speed: int = 50,
        preset_id: int | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {"action": action, "speed": speed}
        if preset_id is not None:
            body["preset_id"] = preset_id
        async with httpx.AsyncClient(headers=self._headers, timeout=self._timeout) as c:
            resp = await c.post(f"{self.base_url}/cameras/{camera_id}/ptz", json=body)
            resp.raise_for_status()
            return resp.json()


# ---------------------------------------------------------------------------
# Component
# ---------------------------------------------------------------------------


class CctvqlComponent:
    """Manages cctvQL state and event subscriptions within Viseron."""

    def __init__(
        self,
        vis: Viseron,
        config: dict[str, Any],
        client: CctvqlClient,
    ) -> None:
        self._vis = vis
        self._config = config
        self._client = client

        if config.get(CONFIG_AUTO_ENRICH):
            vis.listen_event("object_detector_result", self._on_detection)
            LOGGER.debug("cctvQL auto-enrich enabled — listening for detections")

        LOGGER.debug("cctvQL component ready")

    # ------------------------------------------------------------------
    # Event handler
    # ------------------------------------------------------------------

    def _on_detection(self, event: Any) -> None:
        """Auto-query cctvQL when Viseron fires an object detection event."""
        camera_name: str = getattr(event.data, "camera_name", "unknown")
        objects: list = getattr(event.data, "objects", [])
        if not objects:
            return

        labels = list({obj.label for obj in objects if hasattr(obj, "label")})
        if not labels:
            return

        query = f"What happened on {camera_name}? Detected: {', '.join(labels)}."
        try:
            loop = asyncio.get_event_loop()
            result = loop.run_until_complete(self._client.query(query))
            LOGGER.info(
                "cctvQL [%s]: %s",
                camera_name,
                result.get("answer", "no answer"),
            )
        except Exception as exc:
            LOGGER.debug("cctvQL auto-enrich failed for %s: %s", camera_name, exc)

    # ------------------------------------------------------------------
    # Public async API (callable by other Viseron components)
    # ------------------------------------------------------------------

    async def async_query(self, query_text: str, session_id: str = "viseron") -> dict[str, Any]:
        return await self._client.query(query_text, session_id=session_id)

    async def async_cameras(self) -> list[dict[str, Any]]:
        return await self._client.cameras()

    async def async_events(
        self, camera: str | None = None, limit: int = 20
    ) -> list[dict[str, Any]]:
        return await self._client.events(camera=camera, limit=limit)

    async def async_ptz(
        self,
        camera_id: str,
        action: str,
        speed: int = 50,
        preset_id: int | None = None,
    ) -> dict[str, Any]:
        return await self._client.ptz(camera_id, action=action, speed=speed, preset_id=preset_id)
