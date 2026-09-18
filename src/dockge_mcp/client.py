"""Resilient Dockge Socket.IO client for the upstream Dockge MCP server."""

import asyncio
import time
from collections import deque
from typing import Any

import jwt
import socketio

from .settings import settings


class TokenCache:
    def __init__(self) -> None:
        self.token: str | None = None
        self.decoded_token: dict[str, Any] | None = None

    def get(self) -> str | None:
        if not self.token or not self.decoded_token:
            return None
        expires = self.decoded_token.get("exp")
        if isinstance(expires, (int, float)) and expires > time.time() + 30:
            return self.token
        self.clear()
        return None

    def set(self, token: str) -> None:
        try:
            decoded = jwt.decode(token, options={"verify_signature": False})
        except (jwt.DecodeError, TypeError):
            self.clear()
        else:
            self.token = token
            self.decoded_token = decoded

    def clear(self) -> None:
        self.token = None
        self.decoded_token = None


class DockgeClient:
    def __init__(self) -> None:
        self.sio = socketio.AsyncClient(
            logger=False,
            engineio_logger=False,
            reconnection=True,
            reconnection_attempts=0,
            reconnection_delay=1,
            reconnection_delay_max=10,
        )
        self.token_cache = TokenCache()
        self.authenticated = False
        self._connection_lock = asyncio.Lock()
        self.terminal_log_sessions: dict[str, deque[str]] = {}
        self.all_agent_stack_lists: dict[str, Any] = {}

        @self.sio.event
        async def connect() -> None:
            # Every Socket.IO connection needs a fresh Dockge authentication.
            self.authenticated = False

        @self.sio.event
        async def disconnect() -> None:
            self.authenticated = False

        @self.sio.on("agent")
        def persistent_agent_listener(
            sub_event_name: str, data: Any, third_arg: Any = None
        ) -> None:
            if sub_event_name == "stackList" and isinstance(data, dict):
                endpoint = data.get("endpoint", "")
                self.all_agent_stack_lists[endpoint] = data.get("stackList", {})
            elif sub_event_name == "terminalWrite":
                terminal_name = data
                if terminal_name in self.terminal_log_sessions and third_arg is not None:
                    self.terminal_log_sessions[terminal_name].append(str(third_arg))

    async def _connect_and_authenticate(self) -> None:
        async with self._connection_lock:
            if not self.sio.connected:
                self.authenticated = False
                last_error: Exception | None = None
                for attempt in range(5):
                    try:
                        await self.sio.connect(
                            str(settings.dockge_url), wait=True, wait_timeout=10
                        )
                        break
                    except Exception as error:
                        last_error = error
                        if self.sio.connected:
                            await self.sio.disconnect()
                        if attempt < 4:
                            await asyncio.sleep(min(2**attempt, 8))
                else:
                    raise ConnectionError(
                        f"Dockge ist nach 5 Versuchen nicht erreichbar: {last_error}"
                    ) from last_error

            if self.authenticated:
                return

            cached_token = self.token_cache.get()
            if cached_token:
                result = await self._emit_with_callback("loginByToken", cached_token, 10)
                if result.get("ok"):
                    self.authenticated = True
                    return
                self.token_cache.clear()

            result = await self._emit_with_callback(
                "login",
                {
                    "username": settings.dockge_username,
                    "password": settings.dockge_password,
                },
                10,
            )
            if not result.get("ok") or not result.get("token"):
                raise ConnectionRefusedError(
                    f"Dockge-Anmeldung fehlgeschlagen: {result.get('msg', 'unbekannt')}"
                )
            self.token_cache.set(result["token"])
            self.authenticated = True

    async def _emit_with_callback(
        self, event: str, data: Any, timeout: float
    ) -> dict[str, Any]:
        loop = asyncio.get_running_loop()
        future: asyncio.Future[dict[str, Any]] = loop.create_future()

        def callback(result: dict[str, Any]) -> None:
            if not future.done():
                future.set_result(result)

        await self.sio.emit(event, data, callback=callback)
        return await asyncio.wait_for(future, timeout=timeout)

    async def _agent_call(
        self, endpoint: str, event_name: str, *args: Any, timeout: float = 30
    ) -> dict[str, Any]:
        return await self._emit_with_callback(
            "agent", (endpoint, event_name, *args), timeout
        )

    async def _call_api(
        self, event_name: str, *args: Any, endpoint: str = ""
    ) -> dict[str, Any]:
        await self._connect_and_authenticate()
        if event_name == "requestStackList":
            # Dockge publishes stackList through the persistent agent listener.
            await self._agent_call(endpoint, event_name)
            await asyncio.sleep(0.25)
            return {"ok": True, "stackList": self.all_agent_stack_lists}
        return await self._agent_call(endpoint, event_name, *args)

    async def start_log_session(self, terminal_name: str) -> None:
        await self._connect_and_authenticate()
        log_deque: deque[str] = deque(maxlen=100)
        self.terminal_log_sessions[terminal_name] = log_deque
        try:
            result = await self._agent_call("", "terminalJoin", terminal_name, timeout=10)
            if result.get("ok") and result.get("buffer"):
                log_deque.append(str(result["buffer"]))
        except (asyncio.TimeoutError, socketio.exceptions.SocketIOError):
            # Live terminalWrite events can still fill the buffer.
            pass

    async def get_terminal_log_lines(
        self, terminal_name: str, last_x_lines: int = 50
    ) -> list[str]:
        if terminal_name in self.terminal_log_sessions:
            lines = "".join(self.terminal_log_sessions[terminal_name]).splitlines()
            return lines[-last_x_lines:]
        await self._connect_and_authenticate()
        try:
            result = await self._agent_call("", "terminalJoin", terminal_name, timeout=10)
        except asyncio.TimeoutError:
            return ["Error: Zeitüberschreitung beim Abrufen des Dockge-Logs."]
        if not result.get("ok"):
            return [f"Error fetching logs: {result.get('msg', 'Unknown error from Dockge')}"]
        return str(result.get("buffer", "")).splitlines()[-last_x_lines:]

    async def start_interactive_terminal(
        self,
        stack_name: str,
        service_name: str,
        endpoint: str = "",
        shell: str = "bash",
    ) -> dict[str, Any]:
        await self._connect_and_authenticate()
        return await self._agent_call(
            endpoint, "interactiveTerminal", stack_name, service_name, shell
        )

    async def send_terminal_input(
        self, terminal_name: str, command: str, endpoint: str = ""
    ) -> dict[str, Any]:
        await self._connect_and_authenticate()
        if not command.endswith("\r"):
            command += "\r"
        await self.sio.emit(
            "agent", (endpoint, "terminalInput", terminal_name, command)
        )
        return {"ok": True}

    async def disconnect(self) -> None:
        self.authenticated = False
        if self.sio.connected:
            await self.sio.disconnect()


dockge_client = DockgeClient()


async def call_dockge_api(
    event_name: str, *args: Any, endpoint: str = ""
) -> dict[str, Any]:
    try:
        return await dockge_client._call_api(event_name, *args, endpoint=endpoint)
    except Exception as error:
        # A failed connection must never poison subsequent tool calls.
        dockge_client.authenticated = False
        return {
            "ok": False,
            "msg": f"An error occurred while communicating with Dockge: {error}",
        }
