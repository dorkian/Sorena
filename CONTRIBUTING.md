# Contributing

This is primarily a solo/portfolio project, but issues and PRs are welcome.

## Setup

```bash
uv sync
pre-commit install
```

## Workflow

1. Every change should trace back to a spec in `docs/specs/`. If you're proposing new behavior, open an issue first.
2. Run `uv run ruff check .`, `uv run ruff format .`, and `uv run pytest` before opening a PR.
3. CI (`.github/workflows/ci.yml`) runs lint + tests on every PR — it must pass before merge.
4. Non-obvious architectural decisions get a short ADR in `docs/adr/`.

## Commit style

Keep commits scoped to one logical change. Reference the phase spec in the commit message where relevant (e.g. `phase-1: add exponential backoff to provider retry`).
