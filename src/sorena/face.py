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


def _handle_chat(text: str) -> None:
    """Run one text turn through the orchestrator and push the transcript
    back to the face. Runs on a worker thread -- orchestrator.run() is
    synchronous and slow (LLM calls)."""
    push_turn("user", text)
    push_state("idle")  # thinking
    from sorena.agents import orchestrator  # lazy: keeps face importable without agent deps

    try:
        reply = orchestrator.run(text)
    except Exception as exc:  # surface backend failures in the UI, never drop the turn
        reply = f"Something went wrong handling that: {exc}"
    push_turn("assistant", reply)
    push_state("idle")


async def _handler(ws) -> None:
    _clients.add(ws)
    try:
        async for raw in ws:
            try:
                msg = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                continue
            if isinstance(msg, dict) and msg.get("type") == "chat" and msg.get("text"):
                threading.Thread(target=_handle_chat, args=(msg["text"],), daemon=True).start()
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


def push_state(state: str, level: float | None = None, agent: dict | None = None) -> None:
    """Push a state update to any connected orb face. No-op if the server
    hasn't been started or no browser tab is connected -- the voice pipeline
    never blocks on the face being open.

    `agent` is the active persona's display info, e.g. {"name": "Sorena",
    "color": "#F2B33D", "icon": "orchestrator.svg"} -- the orb tints itself
    toward that color and shows the icon (looked up under web/icons/). See
    sorena.agents.personas."""
    if _loop is None:
        return
    payload = {"state": state}
    if level is not None:
        payload["level"] = level
    if agent is not None:
        payload["agent"] = agent
    asyncio.run_coroutine_threadsafe(_broadcast(json.dumps(payload)), _loop)


def push_turn(role: str, text: str, agent: dict | None = None) -> None:
    """Push one transcript turn ("user" or "assistant") to the face so the
    conversation panel stays in sync with voice and text turns alike."""
    if _loop is None:
        return
    payload: dict = {"type": "turn", "role": role, "text": text}
    if agent is not None:
        payload["agent"] = agent
    asyncio.run_coroutine_threadsafe(_broadcast(json.dumps(payload)), _loop)


if __name__ == "__main__":
    # Text-only mode: serve the face bridge without the voice pipeline.
    #   uv run python -m sorena.face   then open web/index.html
    # Run via the canonical `sorena.face` module, not this `__main__` copy --
    # otherwise the rest of the codebase pushes to a second, serverless instance.
    from sorena import face as _face

    _face.start()
    print(f"Sorena face bridge on ws://localhost:{_face.PORT} -- open web/index.html")
    threading.Event().wait()  # run until Ctrl+C
