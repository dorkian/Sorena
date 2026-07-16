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
