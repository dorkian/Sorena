# Sorena — Code Context

Local-first, $0/month Jarvis-style AI agent. Vault context: `D:\claude-projects\vault\01-Projects\sorena-ai-assistant\`

## Workflow
- Spec-first: every phase has a spec at `docs/specs/phase-N-*.md` before code is written
- Build a phase with `/build`, verify it against its spec with `/review`
- One phase = one tagged release (v0.1.0, v0.2.0, …)

## Stack
Python, `uv`, `ruff`, `pytest`, `mypy`/`pyright`, GitHub Actions CI. See `docs/specs/phase-0-repo-foundation.md` for exact setup.

## Rules
- No LangChain for the core agent loop (Phase 2) — build the ReAct loop raw first
- Prefer free/local inference (Ollama, Groq/Gemini free tiers, whisper.cpp, Piper) over paid APIs
- Type hints + docstrings on every public function
- Non-obvious architectural choices get an ADR in `docs/adr/`
