# Sorena

*Named after the Parthian general known for cunning, decisive action.*

Local-first, $0/month Jarvis-style AI assistant, built phase by phase. Each phase adds one capability and ships as a tagged release — see [`docs/specs/`](docs/specs/README.md) for the full roadmap.

![demo](docs/demo.gif)
<!-- demo GIF placeholder — replace after Phase 4 (voice pipeline) ships -->

## Architecture

```mermaid
flowchart LR
    User -->|voice / text| Agent[Agent Loop]
    Agent --> Router[LLM Router\nGroq → Gemini]
    Agent --> Tools[Tool Registry]
    Agent --> MCP[MCP Client]
    Agent --> Memory[Memory / RAG\nSQLite + embeddings]
    MCP --> Servers[External MCP Servers\ne.g. code-graph-mcp]
    Agent --> Voice[Voice Pipeline\nwhisper.cpp + Piper]
    Voice --> User
```

## Roadmap

| Phase | Capability | Release |
|---|---|---|
| 0 | Repo foundation | v0.0.1 |
| 1 | LLM router with fallback | v0.1.0 |
| 2 | Tool-calling agent loop | v0.2.0 |
| 3 | MCP integration (client + server) | v0.3.0 |
| 4 | Voice pipeline | v0.4.0 |
| 5 | Memory & RAG | v0.5.0 |
| 6 | Evaluation & observability | v1.0.0 |

Full specs, deliverables, and definition-of-done per phase: [`docs/specs/`](docs/specs/README.md).

## Quickstart

```bash
uv sync                    # install dependencies
uv run pytest               # run tests
uv run ruff check .         # lint
uv run ruff format .        # format
pre-commit install          # enable git hooks (once)
```

## Demo: forced fallback

`sorena.router.chat()` is the single entry point every other phase calls through. It tries providers in order (Groq → Gemini), retrying each with exponential backoff, and skips a provider locally once its free-tier RPM is hit — before a real 429 happens. Every call logs one JSONL record to `traces/telemetry.jsonl`.

```bash
uv run python examples/demo_fallback.py
```

Expected output — the primary provider is broken on purpose, so you see it fail and the router falls through automatically:

```
[router] groq/not-a-real-model failed: litellm.BadRequestError: ...

Final reply: <a real reply from Gemini>
```

## Demo: multi-step tool-calling agent

`sorena.agent.run()` is a ReAct-style loop: LLM call → tool call → tool result → LLM call, repeated until the model returns a plain answer or a max-hop guard (8 hops) trips. Four tools are registered: current time, file search, web search (Tavily), and an allow-listed shell command runner. A validation layer catches unknown tool names and malformed arguments and feeds them back as an error observation instead of crashing. Conversation memory is a rolling token-budget window that compresses older turns into an LLM-generated summary once it overflows.

Requires a `TAVILY_API_KEY` in `.env` (free tier at [tavily.com](https://tavily.com)) for the web search tool.

```bash
uv run python examples/demo_agent.py
```

Real captured output — one prompt requiring two sequential tool calls (time + web search), resolved end-to-end with no manual intervention:

```
User: What is the current UTC time, and search the web for who won the most recent Super Bowl? Use tools for both, then summarize both answers.

Agent: The current UTC time is 2026-07-15T11:25:43.972124+00:00. The most recent Super Bowl winner is not explicitly stated in the search results provided, but based on the information given, it appears that the Super Bowl winners for the last few years are not listed. However, the winners of some of the past Super Bowls are mentioned, such as the Kansas City Chiefs, New York Giants, and Pittsburgh Steelers. To find the most recent Super Bowl winner, it would be best to check the latest sports news or the official NFL website.
```

(The time tool call resolved correctly; the web search tool call also succeeded — the vague answer reflects the LLM's synthesis of that day's search results, not a tool failure.)

## Development

- Spec-first: every phase has a spec in `docs/specs/` before code is written
- Architecture decisions are recorded in `docs/adr/`
- CI runs lint + tests on every push/PR ([`.github/workflows/ci.yml`](.github/workflows/ci.yml))

## License

MIT — see [LICENSE](LICENSE).
