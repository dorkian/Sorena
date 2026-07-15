# Phase 3 — MCP Integration

**Status:** Complete (v0.3.0)
**Depends on:** Phase 2 (agent loop)
**Target duration:** 1 week
**Release tag:** v0.3.0

## Goal
Wire the agent into the Model Context Protocol on both sides: as a client that can discover and call tools from any MCP server, and as a server that exposes the agent's own tools to other MCP clients (Claude Desktop, Claude Code).

## Skill learned
Model Context Protocol. Rapidly becoming the standard tool-interop layer for AI agents, and you already have a running head start via the existing `code-graph-mcp` project to dogfood.

## Deliverables
- MCP client embedded in the agent loop: discovers a connected server's tools at startup and merges them into the Phase 2 tool registry
- Connect `code-graph-mcp` (existing project) as the first real server — proves the client against a server you already know intimately
- MCP server exposing Sorena's own native tools (time/date, file search, web search, shell) so Claude Desktop or Claude Code can call them
- Config for adding/removing MCP servers without code changes (a simple JSON/YAML server list)
- Graceful handling of a server that's unreachable at startup — agent still boots with whatever tools it does have

## Definition of Done
- [x] Agent successfully calls at least one `code-graph-mcp` tool through the MCP client and uses the result in a response
- [x] Tools discovered from an MCP server appear in the same registry/schema shape as native tools (no special-casing at call time)
- [x] Sorena's MCP server, when pointed to from Claude Desktop/Code, lets Claude call at least 2 of Sorena's native tools successfully
- [x] Killing a configured MCP server before agent startup does not crash the agent — it boots with the remaining tools and logs the failure
- [x] Adding a new MCP server to config and restarting picks it up with no code change
- [x] README demo: real transcript of the agent calling `code-graph-mcp` via MCP, and a real Claude session calling Sorena's own MCP server (screen recording swapped for a captured transcript/screenshot, consistent with how the Phase 2 demo was documented)
- [x] Repo tagged `v0.3.0`

## Efficient Learning Path
- The official MCP specification site (modelcontextprotocol.io) — read "Core architecture" and "Tools" sections only; skip resources/prompts/sampling until you actually need them
- The official Python MCP SDK README/quickstart — build the "hello world" server from it before touching your own tools
- Your own `code-graph-mcp` source as the best possible worked example — you already understand it, so use it to sanity-check the spec's abstractions instead of reading generic third-party tutorials
- Skim 1–2 other public MCP servers (from the MCP servers reference repo) only if you get stuck on a specific integration detail — don't survey the ecosystem broadly

**Methodology:** get the client working against `code-graph-mcp` first — it's a known-good server, so any bug you hit is in your client code, not the server. Only build the server side once the client round-trip is proven.

## Interview line
*"I've built both sides of MCP — servers (code-graph-mcp, published) and a client in my agent."* Very few candidates can say this.
