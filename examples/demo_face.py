"""Cycles the orb face through every state without needing real mic/speaker
hardware -- open web/orb.html in a browser first, then run this.

uv run python examples/demo_face.py
"""

import time

from sorena import face

face.start()
print("Face server listening on ws://localhost:8765/orb")
print("Open web/orb.html in a browser, then watch it react.\n")

for state in ["idle", "listening", "speaking", "idle"]:
    print(f"-> {state}")
    face.push_state(state)
    time.sleep(4)
