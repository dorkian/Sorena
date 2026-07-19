import asyncio
import json
import logging
import threading

import pytest
import websockets

from sorena import face


@pytest.fixture(autouse=True)
def _reset_ready(monkeypatch):
    # _ready is a plain module-level bool set by set_ready() -- reset before
    # every test so one test calling set_ready() can't leak "ready" into an
    # unrelated test's initial config message, regardless of run order.
    monkeypatch.setattr(face, "_ready", False)


def test_websockets_server_logger_is_quieted():
    # a browser's aborted/speculative connection (reload, prefetch) or a
    # port probe logs a full "opening handshake failed" traceback at ERROR
    # by default -- harmless (confirmed by direct reproduction: the server
    # keeps serving real clients right after), but reads as a crash in
    # start.bat's console. Regression guard for the setLevel() in face.py's
    # module body -- easy to accidentally delete without noticing why it's
    # there, since nothing else exercises it.
    assert logging.getLogger("websockets.server").level == logging.CRITICAL


def test_push_state_is_a_noop_before_the_server_has_started(monkeypatch):
    monkeypatch.setattr(face, "_loop", None)
    # must not raise even with no server, no loop, no connected clients
    face.push_state("listening")
    face.push_state("speaking", level=0.4)


def test_push_state_delivers_to_a_connected_client():
    face.start()
    connected = threading.Event()
    received = []

    async def client():
        async with websockets.connect(f"ws://localhost:{face.PORT}/orb") as ws:
            await asyncio.wait_for(ws.recv(), timeout=3)  # the on-connect config message
            connected.set()
            received.append(await asyncio.wait_for(ws.recv(), timeout=3))

    thread = threading.Thread(target=lambda: asyncio.run(client()))
    thread.start()
    assert connected.wait(timeout=3), "client never connected"

    face.push_state("speaking", level=0.8)
    thread.join(timeout=5)

    assert received
    assert json.loads(received[0]) == {"state": "speaking", "level": 0.8}


def test_rejects_cross_origin_connection():
    # Any website open in the user's browser could otherwise open a WS
    # connection to this port and drive the full orchestrator -- regression
    # guard for the origins=[None, "null"] check in face.py's serve() call.
    face.start()

    async def client():
        async with websockets.connect(
            f"ws://localhost:{face.PORT}/orb", origin="https://evil.example.com"
        ):
            pass  # should never get here

    with pytest.raises(websockets.exceptions.InvalidStatus):
        asyncio.run(client())


def test_accepts_null_origin_connection():
    # A real browser opening web/index.html via file:// sends Origin: null
    # (an opaque origin's literal serialization) -- must still be allowed.
    face.start()

    async def client():
        async with websockets.connect(f"ws://localhost:{face.PORT}/orb", origin="null") as ws:
            return json.loads(await asyncio.wait_for(ws.recv(), timeout=3))

    msg = asyncio.run(client())
    assert msg["type"] == "config"


def test_accepts_start_bat_origin_connection():
    # start.bat serves web/ over plain HTTP on 8420 (not file://) -- its
    # real Origin header is this exact string, and must still be allowed.
    # Regression test: this exact case was missed on the first pass and
    # broke the real launch path (start.bat) while the unit tests still
    # passed, since they only exercised file://'s "null" and no-header cases.
    face.start()

    async def client():
        async with websockets.connect(
            f"ws://localhost:{face.PORT}/orb", origin="http://localhost:8420"
        ) as ws:
            return json.loads(await asyncio.wait_for(ws.recv(), timeout=3))

    msg = asyncio.run(client())
    assert msg["type"] == "config"


def test_config_message_lists_the_provider_chain_on_connect():
    from sorena.config import PROVIDER_CHAIN

    face.start()

    async def client():
        async with websockets.connect(f"ws://localhost:{face.PORT}/orb") as ws:
            return json.loads(await asyncio.wait_for(ws.recv(), timeout=3))

    msg = asyncio.run(client())

    assert msg == {"type": "config", "models": PROVIDER_CHAIN, "ready": False}


def test_config_message_reflects_ready_state_for_a_late_joining_client():
    face.start()
    face.set_ready()

    async def client():
        async with websockets.connect(f"ws://localhost:{face.PORT}/orb") as ws:
            return json.loads(await asyncio.wait_for(ws.recv(), timeout=3))

    msg = asyncio.run(client())

    assert msg["ready"] is True


def test_set_ready_broadcasts_to_an_already_connected_client():
    face.start()
    connected = threading.Event()
    received = []

    async def client():
        async with websockets.connect(f"ws://localhost:{face.PORT}/orb") as ws:
            await asyncio.wait_for(ws.recv(), timeout=3)  # the on-connect config message
            connected.set()
            received.append(json.loads(await asyncio.wait_for(ws.recv(), timeout=3)))

    thread = threading.Thread(target=lambda: asyncio.run(client()))
    thread.start()
    assert connected.wait(timeout=3), "client never connected"

    face.set_ready()
    thread.join(timeout=5)

    assert received == [{"type": "ready"}]


def test_stop_message_calls_tts_request_stop(monkeypatch):
    from sorena.voice import tts

    calls = []
    monkeypatch.setattr(tts, "request_stop", lambda: calls.append(True))
    face.start()

    async def client():
        async with websockets.connect(f"ws://localhost:{face.PORT}/orb") as ws:
            await asyncio.wait_for(ws.recv(), timeout=3)  # the on-connect config message
            await ws.send(json.dumps({"type": "stop"}))
            await asyncio.sleep(0.2)  # let the handler process it before disconnecting

    asyncio.run(client())

    assert calls == [True]


def test_chat_message_routes_to_orchestrator_and_pushes_transcript(monkeypatch):
    import sorena.agents.orchestrator as orchestrator

    monkeypatch.setattr(orchestrator, "run", lambda text, model_override=None: f"echo: {text}")
    face.start()
    received = []

    async def client():
        async with websockets.connect(f"ws://localhost:{face.PORT}/orb") as ws:
            await asyncio.wait_for(ws.recv(), timeout=3)  # the on-connect config message
            await ws.send(json.dumps({"type": "chat", "text": "hello"}))
            # expect: user turn, thinking state, assistant turn, idle state
            for _ in range(4):
                received.append(json.loads(await asyncio.wait_for(ws.recv(), timeout=5)))

    asyncio.run(client())

    turns = [m for m in received if m.get("type") == "turn"]
    assert {"type": "turn", "role": "user", "text": "hello"} in turns
    assert {"type": "turn", "role": "assistant", "text": "echo: hello"} in turns


def test_chat_message_with_model_field_passes_override_to_orchestrator(monkeypatch):
    import sorena.agents.orchestrator as orchestrator

    captured = {}

    def fake_run(text, model_override=None):
        captured["model_override"] = model_override
        return "ok"

    monkeypatch.setattr(orchestrator, "run", fake_run)
    face.start()

    async def client():
        async with websockets.connect(f"ws://localhost:{face.PORT}/orb") as ws:
            await asyncio.wait_for(ws.recv(), timeout=3)  # the on-connect config message
            await ws.send(
                json.dumps(
                    {"type": "chat", "text": "hello", "model": "openrouter/openai/gpt-oss-120b"}
                )
            )
            # expect: user turn, thinking state, assistant turn, idle state
            for _ in range(4):
                await asyncio.wait_for(ws.recv(), timeout=5)

    asyncio.run(client())

    assert captured["model_override"] == "openrouter/openai/gpt-oss-120b"
