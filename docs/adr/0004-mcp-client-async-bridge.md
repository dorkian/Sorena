# 0004 — MCP client: background-thread async bridge, not a full async rewrite

**Status:** Accepted

## Context
The official MCP Python SDK (`mcp`) is async-native: `stdio_client`, `ClientSession.list_tools()`,
and `ClientSession.call_tool()` are all coroutines. Sorena's agent loop (`agent.py`), tool registry
(`tools/registry.py`), and router (`router.py`) are entirely synchronous — `litellm.completion()`,
`subprocess.run()`, and `requests.post()` all block.

Two options: make the agent loop async end-to-end, or bridge the async MCP client into the
existing sync codebase.

## Decision
Bridge, not rewrite. `MCPBridge` (`src/sorena/mcp_client.py`) runs a dedicated background thread
owning its own `asyncio` event loop. Stdio sessions to each configured MCP server are opened once
at startup and held open (via an `AsyncExitStack`) for the process lifetime — not reopened per
call, since that would mean respawning the server subprocess on every tool invocation. A sync
`call_tool()` schedules the actual MCP call onto that loop with
`asyncio.run_coroutine_threadsafe(...).result()` and blocks until it returns.

## Consequences
- The rest of the codebase — `agent.py`, `registry.py`, every existing tool — stays synchronous
  and untouched. MCP tools are merged into the same `TOOLS`/`TOOL_SCHEMAS` dict/list the native
  tools use, so `call_tool()` needed zero special-casing (verified: same dispatch path handles
  `mcp_code-graph_repo_summary` exactly like `get_current_time`).
- One dedicated thread + event loop per process, alive for the process's whole lifetime, not per
  request. Acceptable for a single-user local assistant; would need revisiting (likely: just go
  async) if Sorena ever needs to serve multiple concurrent conversations.
- Rejected: full async rewrite of the agent loop. Would touch every module for a benefit (native
  async MCP calls) that a background-thread bridge gets for a fraction of the diff. Revisit only
  if a second async-native dependency shows up and the bridge pattern starts repeating.
