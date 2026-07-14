# Sorena

*Named after the Parthian general known for cunning, decisive action.*

Local-first, $0/month Jarvis-style AI assistant, built phase by phase. Each phase adds one capability and ships as a tagged release — see [`docs/specs/`](docs/specs/README.md) for the full roadmap.

![demo](docs/demo.gif)
<!-- demo GIF placeholder — replace after Phase 4 (voice pipeline) ships -->

## Architecture

```mermaid
flowchart LR
    User -->|voice / text| Agent[Agent Loop]
    Agent --> Router[LLM Router\nGroq → Gemini → Ollama]
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

## Development

- Spec-first: every phase has a spec in `docs/specs/` before code is written
- Architecture decisions are recorded in `docs/adr/`
- CI runs lint + tests on every push/PR ([`.github/workflows/ci.yml`](.github/workflows/ci.yml))

## License

MIT — see [LICENSE](LICENSE).
