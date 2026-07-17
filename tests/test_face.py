import asyncio
import json
import threading

import websockets

from sorena import face


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
            connected.set()
            received.append(await asyncio.wait_for(ws.recv(), timeout=3))

    thread = threading.Thread(target=lambda: asyncio.run(client()))
    thread.start()
    assert connected.wait(timeout=3), "client never connected"

    face.push_state("speaking", level=0.8)
    thread.join(timeout=5)

    assert received
    assert json.loads(received[0]) == {"state": "speaking", "level": 0.8}


def test_chat_message_routes_to_orchestrator_and_pushes_transcript(monkeypatch):
    import sorena.agents.orchestrator as orchestrator

    monkeypatch.setattr(orchestrator, "run", lambda text: f"echo: {text}")
    face.start()
    received = []

    async def client():
        async with websockets.connect(f"ws://localhost:{face.PORT}/orb") as ws:
            await ws.send(json.dumps({"type": "chat", "text": "hello"}))
            # expect: user turn, idle state, assistant turn, idle state
            for _ in range(4):
                received.append(json.loads(await asyncio.wait_for(ws.recv(), timeout=5)))

    asyncio.run(client())

    turns = [m for m in received if m.get("type") == "turn"]
    assert {"type": "turn", "role": "user", "text": "hello"} in turns
    assert {"type": "turn", "role": "assistant", "text": "echo: hello"} in turns
