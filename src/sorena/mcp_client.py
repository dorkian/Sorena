import asyncio
import json
import threading
from collections.abc import Callable
from contextlib import AsyncExitStack
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

CONFIG_PATH = Path(__file__).parent.parent.parent / "config" / "mcp_servers.json"


class MCPBridge:
    """Background asyncio event loop owning persistent stdio MCP sessions for
    the process lifetime, so a sync caller can discover/call MCP tools
    without the whole codebase becoming async."""

    def __init__(self):
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._loop.run_forever, daemon=True)
        self._thread.start()
        self._stack = AsyncExitStack()
        self._sessions: dict[str, ClientSession] = {}

    def _run(self, coro):
        return asyncio.run_coroutine_threadsafe(coro, self._loop).result()

    def connect_all(
        self, config_path: Path = CONFIG_PATH
    ) -> tuple[dict[str, Callable], list[dict]]:
        config = json.loads(config_path.read_text())
        tools: dict[str, Callable] = {}
        schemas: list[dict] = []

        for server in config.get("servers", []):
            name = server["name"]
            try:
                session = self._run(self._connect_one(server))
            except Exception as e:
                print(f"[mcp_client] '{name}' unreachable, skipping: {e}")
                continue

            self._sessions[name] = session
            for tool in self._run(session.list_tools()).tools:
                tool_name = f"mcp_{name}_{tool.name}"
                schemas.append(
                    {
                        "type": "function",
                        "function": {
                            "name": tool_name,
                            "description": tool.description or "",
                            "parameters": tool.inputSchema,
                        },
                    }
                )
                tools[tool_name] = self._make_caller(name, tool.name)

        return tools, schemas

    async def _connect_one(self, server: dict) -> ClientSession:
        params = StdioServerParameters(command=server["command"], args=server.get("args", []))
        read, write = await self._stack.enter_async_context(stdio_client(params))
        session = await self._stack.enter_async_context(ClientSession(read, write))
        await session.initialize()
        return session

    def _make_caller(self, server_name: str, tool_name: str) -> Callable[..., str]:
        def call(**kwargs) -> str:
            result = self._run(self._sessions[server_name].call_tool(tool_name, kwargs))
            return "\n".join(part.text for part in result.content if hasattr(part, "text"))

        return call

    def close(self) -> None:
        self._run(self._stack.aclose())
        self._loop.call_soon_threadsafe(self._loop.stop)


_bridge: MCPBridge | None = None


def load_mcp_tools(config_path: Path = CONFIG_PATH) -> tuple[dict[str, Callable], list[dict]]:
    global _bridge
    _bridge = MCPBridge()
    return _bridge.connect_all(config_path)
