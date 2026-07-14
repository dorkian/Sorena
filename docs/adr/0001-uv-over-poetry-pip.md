# 0001 — Use uv instead of Poetry or pip+requirements.txt

**Status:** Accepted
**Date:** 2026-07-14

## Context
Needed a dependency/packaging manager for a Python project that will grow through 7 phases (routing, agents, MCP, audio, embeddings) with a mix of pure-Python and native-dependency packages (e.g. whisper.cpp bindings, sentence-transformers).

## Decision
Use [uv](https://docs.astral.sh/uv/) for dependency resolution, virtual env management, and Python version pinning, instead of Poetry or plain pip + `requirements.txt`.

## Rationale
- Single tool for Python version management, venv creation, dependency resolution, and running scripts (`uv run`) — fewer moving parts than pip + pyenv + venv
- Lockfile (`uv.lock`) gives reproducible installs, which `requirements.txt` doesn't guarantee
- Meaningfully faster resolution/install than Poetry or pip, which matters when iterating across phases with heavier ML dependencies
- Actively maintained by Astral (same team as ruff), consistent tooling philosophy
- Free, no account/service required — fits the project's $0/month constraint

## Consequences
- Contributors need `uv` installed (documented in `CONTRIBUTING.md`)
- CI installs `uv` via `astral-sh/setup-uv` rather than relying on a system Python
