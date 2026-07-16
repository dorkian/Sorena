"""Pushes Sorena's agent state (idle/listening/speaking) to the orb face
(web/orb.html) over a local WebSocket. `websockets` is async-native, so this
runs its own event loop in a background thread and bridges into it with
`run_coroutine_threadsafe` -- the same pattern `mcp_client.MCPBridge` uses
(ADR 0004) to keep the rest of the (synchronous) codebase untouched. See
ADR 0009 for why a bare `websockets` server instead of a web framework.
"""

import asyncio
import json
import threading

import websockets

PORT = 8765

_loop: asyncio.AbstractEventLoop | None = None
_clients: set = set()
_started = threading.Event()


async def _handler(ws) -> None:
    _clients.add(ws)
    try:
        await ws.wait_closed()
    finally:
        _clients.discard(ws)


async def _broadcast(message: str) -> None:
    if not _clients:
        return
    await asyncio.gather(*(c.send(message) for c in list(_clients)), return_exceptions=True)


def _run_server() -> None:
    global _loop
    _loop = asyncio.new_event_loop()
    asyncio.set_event_loop(_loop)

    async def main() -> None:
        async with websockets.serve(_handler, "localhost", PORT):
            _started.set()
            await asyncio.Future()  # run until the process exits

    _loop.run_until_complete(main())


def start() -> None:
    """Start the WebSocket server once, in a background thread. Safe to call
    on every voice turn -- a no-op after the first call."""
    if _started.is_set():
        return
    threading.Thread(target=_run_server, daemon=True).start()
    _started.wait(timeout=5)


def push_state(state: str, level: float | None = None) -> None:
    """Push a state update to any connected orb face. No-op if the server
    hasn't been started or no browser tab is connected -- the voice pipeline
    never blocks on the face being open."""
    if _loop is None:
        return
    payload = {"state": state}
    if level is not None:
        payload["level"] = level
    asyncio.run_coroutine_threadsafe(_broadcast(json.dumps(payload)), _loop)
