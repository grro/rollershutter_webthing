import asyncio
import logging
import socket
import threading
from typing import Protocol, cast, List, Dict, Any

from fastmcp import FastMCP, Context
from pydantic import AnyUrl, TypeAdapter
from zeroconf import IPVersion, ServiceInfo, Zeroconf

from rollershutter import Shutter

logger = logging.getLogger(__name__)


class MDNS:
    def __init__(self) -> None:
        self.registered: Dict[str, ServiceInfo] = {}
        self.zc = Zeroconf(ip_version=IPVersion.V4Only)
        self.service_type = "_mcp._tcp.local."
        self.hostname = socket.gethostname()
        self.local_ip = self._resolve_local_ip()

    @staticmethod
    def _resolve_local_ip() -> str:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
        except OSError:
            logger.warning("mDNS: Could not determine local IP, falling back to localhost.")
            return "127.0.0.1"
        finally:
            s.close()

    def register_mdns(self, name: str, port: int) -> None:
        try:
            service_name = f"{name}.{self.service_type}"
            service_info = ServiceInfo(
                type_=self.service_type,
                name=service_name,
                addresses=[socket.inet_aton(self.local_ip)],
                port=port,
                properties={
                    "version": "1.0",
                    "path": "/sse",
                    "server_type": "fastmcp"
                },
                server=f"{self.hostname}.local.",
            )

            logger.info(f"mDNS: Registering {service_name} at {self.local_ip}:{port}")
            self.zc.register_service(service_info)
            self.registered[name] = service_info
        except Exception as e:
            logger.error(f"mDNS Registration failed: {e}")

    def unregister_mdns(self, name: str) -> None:
        service_info = self.registered.pop(name, None)
        if service_info is not None:
            logger.info(f"mDNS: Unregistering service {name}...")
            self.zc.unregister_service(service_info)

    def close(self) -> None:
        """Properly close all registrations and tear down Zeroconf."""
        for name in list(self.registered):
            self.unregister_mdns(name)
        self.zc.close()


class ResourceUpdateSession(Protocol):
    async def send_resource_updated(self, uri: AnyUrl) -> None:
        ...


class RollershutterMCPServer:
    # Extracted to avoid re-instantiating in high-frequency notification loops
    _url_adapter = TypeAdapter(AnyUrl)

    def __init__(self, name: str, port: int, rollershutters: List[Shutter], host: str = "0.0.0.0") -> None:
        self.name = name
        self.host = host
        self.port = port

        self.mdns = MDNS()
        self.mcp = FastMCP(self.name)
        self.active_sessions: set[ResourceUpdateSession] = set()
        self.rollershutters = rollershutters
        self.loop = asyncio.new_event_loop()
        self.last_pos: Dict[str, int] = {}

        for rollershutter in self.rollershutters:
            rollershutter.register_listener(self.__on_value_changed)

        self._register_handlers()

    def _register_handlers(self) -> None:

        @self.mcp.resource("device://rollershutter")
        def get_shutter_names() -> List[str]:
            """
            Discover all available rollershutters tracked by the server.
            Returns a list of device names. Use these names to query specific states.
            """
            return [r.name for r in self.rollershutters]

        @self.mcp.resource("device://rollershutter/{name}")
        def get_shutter(name: str, ctx: Context) -> Dict[str, Any]:
            """
            Retrieve the current position of a specific rollershutter.
            Accessing this resource automatically subscribes the client to SSE push notifications
            whenever the physical shutter moves.
            """
            try:
                req_ctx = ctx.request_context
                if req_ctx and req_ctx.session and req_ctx.session not in self.active_sessions:
                    self.active_sessions.add(cast(ResourceUpdateSession, req_ctx.session))
                    logger.info(f"[Server] Client session registered for updates (Resource: {name}).")
            except Exception as e:
                logger.debug(f"[Server] Could not register session: {e}")

            for r in self.rollershutters:
                if r.name == name:
                    return {
                        "name": r.name,
                        "pos": r.position,
                        "last_updated_utc": r.last_pos_update.isoformat() if r.last_pos_update else None
                    }

            # Fixed: Properly references self.rollershutters to prevent an AttributeError
            raise ValueError(f"Device '{name}' not found. Available devices: {[r.name for r in self.rollershutters]}")


        @self.mcp.tool()
        def set_position(name: str, position: int) -> Dict[str, Any]:
            """
            Moves a specific rollershutter or all shutters to a target position.
            Orientation:
            0 = FULLY OPEN (Sunshine/Daylight).
            100 = FULLY CLOSED (Privacy/Night mode).

            :param name: The name of the shutter (e.g., 'Kitchen') or 'all' to move everything.
            :param position: Target position from 0 (open) to 100 (closed).
            """
            if not (0 <= position <= 100):
                return {"error": "Position must be between 0 (open) and 100 (closed)."}

            # Logic for 'all' group
            if name.lower() == "all":
                for s in self.rollershutters:
                    s.set_position(position)
                return {"status": "success", "message": f"All shutters are moving to {position}%."}

            # Logic for individual shutters
            shutter = next((s for s in self.rollershutters if s.name == name), None)
            if shutter is None:
                return {
                    "error": f"Rollershutter '{name}' not found.",
                    "available": [s.name for s in self.rollershutters]
                }

            # Execute the movement
            shutter.set_position(position)
            return {"status": "success", "message": f"{name} is moving to {position}%."}

        @self.mcp.tool()
        def get_system_status() -> Dict[str, Any]:
            """
            Provides a summary of all rollershutters and their current positions.
            Use this tool when the user asks 'Are the shutters closed?' or 'What is the status?'.
            """
            return {
                "shutters": {s.name: {"position": s.position} for s in self.rollershutters}
            }


    def __on_value_changed(self, rollershutter: Shutter) -> None:
        if not self.loop.is_running():
            return
        asyncio.run_coroutine_threadsafe(self._trigger_client_notification(rollershutter.name), self.loop)

    async def _trigger_client_notification(self, name: str) -> None:
        if not self.active_sessions:
            return

        for rollershutter in self.rollershutters:
            if rollershutter.name == name:
                last_pos = self.last_pos.get(name, -1)
                if rollershutter.position != last_pos:
                    self.last_pos[name] = rollershutter.position
                    dead_sessions = set()

                    uri = self._url_adapter.validate_python(f"device://rollershutter/{name}")
                    for session in self.active_sessions:
                        try:
                            await session.send_resource_updated(uri)
                        except Exception:
                            dead_sessions.add(session)

                    self.active_sessions.difference_update(dead_sessions)
                break

    async def __run(self) -> None:
        logger.info(f"MCP Server '{self.name}' running on http://{self.host}:{self.port}/sse")
        await self.mcp.run_async(
            transport="sse",
            host=self.host,
            port=self.port,
            uvicorn_config={"access_log": False, "log_config": None}
        )

    def start(self) -> None:
        self.mdns.register_mdns(self.name, self.port)

        def _run_loop() -> None:
            asyncio.set_event_loop(self.loop)
            try:
                self.loop.run_until_complete(self.__run())
            finally:
                self.loop.close()

        thread = threading.Thread(target=_run_loop, daemon=True)
        thread.start()

    def stop(self) -> None:
        self.mdns.close()
        if self.loop.is_running():
            self.loop.call_soon_threadsafe(self.loop.stop)
        logger.info("MCP Server stopped")