# 0009 — Orb face: bare `websockets` server on a background thread, not a web framework

**Status:** Accepted

## Context
The orb face (`web/orb.html`) is a single self-contained HTML/canvas file
with no build step, already written to expect one thing from the backend:
JSON state pushes (`{"state": "listening", "level": 0.62}`) over a
WebSocket. Sorena needs to push its real agent state (idle/listening/
speaking) from the voice pipeline (`pipeline.py`) as a turn progresses.

Two questions: what serves the WebSocket, and how does a synchronous
codebase (the entire voice pipeline, same as ADR 0004's MCP client problem)
drive an async WebSocket library without a rewrite.

## Decision — bare `websockets`, not FastAPI/a web framework
`src/sorena/face.py` uses the `websockets` package directly
(`websockets.serve()`), not FastAPI or any ASGI framework. There's exactly
one endpoint, no HTTP routes, no request/response bodies to model, and
`web/orb.html` is opened directly as a local file (`file://`) rather than
served — a full web framework would add a dependency and a mental model
(routes, ASGI, static file serving) for a single `send(json)` call.

## Decision — background thread + `run_coroutine_threadsafe`, not an async rewrite
Same shape as `MCPBridge` (ADR 0004): `face.py` runs its own `asyncio` event
loop in a background thread, started lazily the first time `pipeline.py`
calls `face.start()`. The rest of the pipeline stays fully synchronous;
`push_state()` is a plain function that schedules a broadcast onto that loop
via `asyncio.run_coroutine_threadsafe(...)` and returns immediately — it
does not wait for delivery.

## Consequences
- `push_state()` never blocks the voice pipeline on the face being open,
  connected, or even running at all — if `_loop` is `None` (server hasn't
  started) or no client is connected, it's a no-op. A user running Sorena
  headless (no browser open) pays no cost beyond the idle background thread.
- `web/orb.html` reconnects on its own (2s retry) if opened before the
  Python process starts, or if the process restarts mid-session — matches
  how a user would actually use this (leave the tab open, restart Sorena).
- No new runtime service to deploy — same "just a background thread" story
  as `MCPBridge`. Revisit only if the face ever needs more than one endpoint
  or bidirectional control (e.g. clicking the orb to trigger an action),
  at which point a real framework earns its keep.
- Live audio `level` (0–1, e.g. mic RMS or TTS output level) is not wired up
  yet — `push_state()` accepts an optional `level` and the frontend already
  handles it, but the pipeline only pushes `state` for now. `web/orb.html`
  already simulates a level automatically when none is pushed ("demo
  mode"), so this was left for later rather than threading real levels
  through `stt.record()`/`tts.play()` for a cosmetic-only improvement.
