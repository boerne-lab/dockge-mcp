import asyncio
import time
import jwt
import socketio
from .settings import settings
from collections import deque

ALL_ENDPOINTS = "##ALL_DOCKGE_ENDPOINTS##"

class TokenCache:
    def __init__(self):
        self.token: str | None = None
        self.decoded_token: dict | None = None

    def get(self) -> str | None:
        """Returns the token if it's not expired."""
        if self.token and self.decoded_token:
            # Check if 'exp' (expiration time) exists and is in the future
            if "exp" in self.decoded_token and self.decoded_token["exp"] > time.time():
                return self.token
        return None

    def set(self, token: str):
        """Sets and decodes the token."""
        self.token = token
        try:
            # Decode without verification to inspect claims like expiration
            self.decoded_token = jwt.decode(token, options={"verify_signature": False})
        except jwt.DecodeError:
            self.decoded_token = None
            self.token = None

class DockgeClient:
    def __init__(self):
        self.sio = socketio.AsyncClient(logger=False, engineio_logger=False) # Disable logging
        self.token_cache = TokenCache()
        self.connected = False
        self.authenticated = False
        self.terminal_log_sessions: dict[str, deque] = {}

        self.all_agent_stack_lists = {}  # Stores stack lists from all agents

        # Add catch-all listener for debugging
        @self.sio.on("*")
        def catch_all(event, data):
            pass

        # Persistent listener for "agent" events
        @self.sio.on("agent")
        def persistent_agent_listener(sub_event_name, data, third_arg=None):
            if sub_event_name == "stackList":
                endpoint = data.get("endpoint", "") # Default to empty string for primary
                self.all_agent_stack_lists[endpoint] = data.get("stackList", {})
            elif sub_event_name == "terminalWrite":
                terminal_name = data
                log_chunk = third_arg
                if terminal_name in self.terminal_log_sessions and log_chunk is not None:
                    self.terminal_log_sessions[terminal_name].append(log_chunk)
            else:
                pass

    async def start_log_session(self, terminal_name: str):
        """
        Initializes a new log session for a terminal, fetching the initial buffer.
        """
        await self._connect_and_authenticate()

        # Create a new deque with a max length of 100 chunks
        log_deque = deque(maxlen=100)
        self.terminal_log_sessions[terminal_name] = log_deque

        callback_future = asyncio.Future()
        def event_callback(data):
            if not callback_future.done():
                callback_future.set_result(data)

        await self.sio.emit(
            "agent",
            ("", "terminalJoin", terminal_name),
            callback=event_callback,
        )

        try:
            result = await asyncio.wait_for(callback_future, timeout=10.0)
            if result.get("ok"):
                buffer_content = result.get("buffer", "")
                if buffer_content:
                    # Append the whole initial buffer as one chunk
                    log_deque.append(buffer_content)
        except (asyncio.TimeoutError, Exception):
            # Fail silently, subsequent terminalWrite events will still populate the log
            pass

    async def _connect_and_authenticate(self):
        if not self.connected:
            await self.sio.connect(str(settings.dockge_url))
            self.connected = True

        if not self.authenticated:
            cached_token = self.token_cache.get()
            if cached_token:
                auth_future = asyncio.Future()
                def auth_callback(data):
                    if not auth_future.done():
                        auth_future.set_result(data)
                await self.sio.emit("loginByToken", cached_token, callback=auth_callback)
                auth_result = await asyncio.wait_for(auth_future, timeout=10.0)
                if auth_result.get("ok"):
                    self.authenticated = True
                    return
                else:
                    self.token_cache.set(None) # Clear invalid token

            # Perform full login if not authenticated or cached token failed
            login_future = asyncio.Future()
            def login_callback(data):
                if not login_future.done():
                    login_future.set_result(data)

            await self.sio.emit("login", {
                "username": settings.dockge_username,
                "password": settings.dockge_password,
            }, callback=login_callback)

            login_result = await asyncio.wait_for(login_future, timeout=10.0)

            if login_result.get("ok") and login_result.get("token"):
                token = login_result["token"]
                self.token_cache.set(token)
                self.authenticated = True
            else:
                raise ConnectionRefusedError(f"Dockge login failed: {login_result.get('msg')}")

    async def _call_api(self, event_name: str, *args, endpoint: str = ""):
        await self._connect_and_authenticate()

        # Special handling for requestStackList to capture the broadcasted list
        if event_name == "requestStackList":
            return {"ok": True, "stackList": self.all_agent_stack_lists}

        else:
            # For other events, use the existing callback mechanism
            callback_future = asyncio.Future()
            def event_callback(data):
                if not callback_future.done():
                    callback_future.set_result(data)

            await self.sio.emit(
                "agent",
                (endpoint, event_name, *args),
                callback=event_callback,
            )

            # 4. Wait for the result
            result = await asyncio.wait_for(callback_future, timeout=30.0)
            return result

    async def disconnect(self):
        if self.connected:
            print("DEBUG: Disconnecting from Dockge server...")
            await self.sio.disconnect()
            self.connected = False
            self.authenticated = False

    async def get_terminal_log_lines(self, terminal_name: str, last_x_lines: int = 50) -> list[str]:
        """
        Fetches the last X Docker container terminal log lines directly from the Dockge server.
        Max history is determined by the Dockge server's buffer (typically 100 chunks).
        """
        # 1. Check for an active log session
        if terminal_name in self.terminal_log_sessions:
            buffered_chunks = list(self.terminal_log_sessions[terminal_name])
            full_log = "".join(buffered_chunks)
            lines = full_log.splitlines()
            return lines[-last_x_lines:]

        # 2. Fallback to original on-demand fetching for other terminals
        await self._connect_and_authenticate()

        callback_future = asyncio.Future()
        def event_callback(data):
            if not callback_future.done():
                callback_future.set_result(data)

        await self.sio.emit(
            "agent",
            ("", "terminalJoin", terminal_name),
            callback=event_callback,
        )
        
        try:
            result = await asyncio.wait_for(callback_future, timeout=10.0)

            if result.get("ok"):
                buffer_content = result.get("buffer", "")
                lines = buffer_content.splitlines()
                return lines[-last_x_lines:]
            else:
                error_msg = result.get("msg", "Unknown error from Dockge")
                return [f"Error fetching logs: {error_msg}"]
                
        except asyncio.TimeoutError:
            return ["Error: Timed out waiting for log buffer from Dockge."]
        except Exception as e:
            return [f"An unexpected error occurred: {e}"]

    async def start_interactive_terminal(self, stack_name: str, service_name: str, endpoint: str = "", shell: str = "bash") -> dict:
        """
        Starts an interactive terminal session for a Docker container.
        """
        await self._connect_and_authenticate()
        callback_future = asyncio.Future()
        def event_callback(data):
            if not callback_future.done():
                callback_future.set_result(data)

        await self.sio.emit(
            "agent",
            (endpoint, "interactiveTerminal", stack_name, service_name, shell),
            callback=event_callback,
        )
        result = await asyncio.wait_for(callback_future, timeout=30.0)
        return result

    async def send_terminal_input(self, terminal_name: str, command: str, endpoint: str = "") -> dict:
        """
        Sends a command to an active interactive terminal session.
        This is an emit-and-forget operation; terminal output is received via 'terminalWrite' events.
        """
        await self._connect_and_authenticate()
        # Ensure the command ends with a carriage return for shell execution
        if not command.endswith('\r'):
            command += '\r'

        await self.sio.emit(
            "agent",
            (endpoint, "terminalInput", terminal_name, command),
        )
        return {"ok": True} # Assume success for emit-and-forget

# Create a global instance of the client
dockge_client = DockgeClient()

async def call_dockge_api(event_name: str, *args, endpoint: str = ""):
    """
    Connects to Dockge, authenticates, and emits an event to a specific endpoint.
    Manages the JWT lifecycle by logging in once and reusing the token.
    """
    try:
        return await dockge_client._call_api(event_name, *args, endpoint=endpoint)
    except Exception as e:
        return {"ok": False, "msg": f"An error occurred while communicating with Dockge: {str(e)}"}
