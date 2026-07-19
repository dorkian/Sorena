"""Pushes Sorena's agent state (idle/listening/speaking) to the orb face
(web/orb.html) over a local WebSocket. `websockets` is async-native, so this
runs its own event loop in a background thread and bridges into it with
`run_coroutine_threadsafe` -- the same pattern `mcp_client.MCPBridge` uses
(ADR 0004) to keep the rest of the (synchronous) codebase untouched. See
ADR 0009 for why a bare `websockets` server instead of a web framework.
"""

import asyncio
import json
import logging
import threading

import websockets

PORT = 8765

# Any TCP connection that touches this port without completing a real
# WebSocket handshake -- a browser's speculative/aborted connection on
# reload, a port probe, antivirus poking it -- makes `websockets` log a full
# "opening handshake failed" traceback at ERROR level by default. Confirmed
# by direct reproduction (raw socket connect-then-close) that this is
# harmless: the server keeps running and serves real clients immediately
# after. Silencing it here so a routine, expected event doesn't read as a
# crash in start.bat's console.
logging.getLogger("websockets.server").setLevel(logging.CRITICAL)

_loop: asyncio.AbstractEventLoop | None = None
_clients: set = set()
_started = threading.Event()

# Set by main.py once the voice pipeline's models (wake word, etc.) have
# finished loading -- a fresh browser tab needs this in its initial config
# message (not just a broadcast) since it may connect before or after that
# happens. Text chat doesn't depend on it and stays usable regardless; this
# only gates the "ready to listen" indicator in the UI.
_ready = False

# Bounds concurrent orchestrator.run() calls (LLM + tool execution, shared
# SQLite/trace-file writes) from a burst of chat messages. A single real
# user sends one message at a time; this only throttles the excess, it
# never drops a message -- the extra threads just block on acquire() until
# a slot frees.
_CHAT_CONCURRENCY_CAP = 4
_chat_semaphore = threading.Semaphore(_CHAT_CONCURRENCY_CAP)


def _handle_chat(text: str, model: str | None = None) -> None:
    """Run one text turn through the orchestrator and push the transcript
    back to the face. Runs on a worker thread -- orchestrator.run() is
    synchronous and slow (LLM calls). `model` is the user's explicit pick
    from the chat UI's model dropdown, or None for the default fallback
    chain (see sorena.router.chat's model_override)."""
    with _chat_semaphore:
        push_turn("user", text)
        push_state("thinking")
        from sorena.agents import orchestrator  # lazy: keeps face importable without agent deps

        try:
            reply = orchestrator.run(text, model_override=model)
        except Exception as exc:  # surface backend failures in the UI, never drop the turn
            reply = f"Something went wrong handling that: {exc}"
        push_turn("assistant", reply)
        push_state("idle")


async def _handler(ws) -> None:
    _clients.add(ws)
    from sorena.config import PROVIDER_CHAIN  # lazy: keeps face importable without agent deps

    await ws.send(json.dumps({"type": "config", "models": PROVIDER_CHAIN, "ready": _ready}))
    try:
        async for raw in ws:
            try:
                msg = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                continue
            if not isinstance(msg, dict):
                continue
            if msg.get("type") == "chat" and msg.get("text"):
                threading.Thread(
                    target=_handle_chat, args=(msg["text"], msg.get("model")), daemon=True
                ).start()
            elif msg.get("type") == "stop":
                # single click/tap on the orb while it's speaking -- lazy
                # import keeps face importable in text-only mode without
                # pulling in the voice stack (sounddevice/piper).
                from sorena.voice import tts

                tts.request_stop()
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
        # None covers non-browser clients that send no Origin header (test
        # clients, local scripts); "null" covers a browser opening
        # web/index.html directly via file:// (an opaque origin serializes
        # to the literal string "null" per the Fetch spec);
        # "http://localhost:8420" covers the actual production launch path
        # -- start.bat serves web/ over plain HTTP on that port rather than
        # opening it as a file:// page, so its real Origin header is that
        # exact string, not "null". Anything else -- a real origin from some
        # other, cross-site page -- is rejected at the handshake, closing
        # the cross-site WebSocket hijacking hole (any open browser tab
        # could otherwise drive the full orchestrator with zero auth just
        # by knowing this port); a malicious page cannot spoof its Origin
        # header to claim to be localhost:8420, since browsers set it from
        # the page's real origin and JS cannot override it.
        async with websockets.serve(
            _handler, "localhost", PORT, origins=[None, "null", "http://localhost:8420"]
        ):
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


def set_ready() -> None:
    """Marks the voice pipeline as ready to listen (wake word model loaded)
    and tells any already-connected browser tab -- a tab that connects
    *after* this still gets it via the initial config message's "ready"
    field, so timing between the two never matters."""
    global _ready
    _ready = True
    if _loop is None:
        return
    asyncio.run_coroutine_threadsafe(_broadcast(json.dumps({"type": "ready"})), _loop)


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
