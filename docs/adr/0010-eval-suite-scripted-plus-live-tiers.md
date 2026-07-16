# 0010 — Eval suite: scripted (CI-gated) tier + live (skip-gated) tier, not one suite

**Status:** Accepted

## Context
Phase 6 wants an eval suite that catches regressions in "did the agent pick
the right tool" and "was the final answer correct," wired into CI on every
PR. But CI (`.github/workflows/ci.yml`) has no LLM provider API keys
configured as GitHub secrets — `uv run pytest` runs with an empty `.env`.
A suite that calls a real model can't run there at all, yet a suite that
*only* mocks the model's decisions can't actually evaluate whether the
model would make that decision — it would just be re-testing whatever the
test itself scripted.

## Decision
Two tiers, same harness (`tests/evals/`), same `agent.run()` call path:

- **Deterministic tier** (`EvalCase(live=False)`): the LLM's decision at
  each hop is scripted (`tests/evals/harness.py`'s `tool_call`/`tool_calls`/
  `final`), monkeypatching `router.chat`. These test the agent loop's
  *orchestration mechanics* — correct dispatch, error recovery on a bad
  tool call, trace capture, the max-hops exception path — not the model's
  judgment. Most are regression cases mined from real bugs already hit in
  Phases 2, 3, and 5 (unknown-tool handling, the `json.loads("null")`
  crash, the MCP zero-special-casing guarantee, the Phase 5 RRF
  candidate-pool bug). Fully deterministic, no network, runs in CI.
- **Live tier** (`EvalCase(live=True)`): a real call through `router.chat()`
  using whichever provider is configured in `.env`. These test genuine
  tool-selection judgment — a case that's meaningful specifically *because*
  nothing about the answer was scripted. Skipped automatically
  (`pytest.skip`) when no provider API key is present, via the same
  `os.getenv("GROQ_API_KEY") or os.getenv("GEMINI_API_KEY")` check `.env`
  usage already implies elsewhere in this repo (e.g. the web-search tool's
  `TAVILY_API_KEY` requirement, documented in the README).

## Decision — CI threshold is 100%, not a softer percentage
The spec's Definition of Done asks for "a documented threshold" a PR can
regress below. Since CI only ever runs the deterministic tier (the live
tier always skips there, no keys), and every deterministic case is fully
scripted with no real-world variance, there is no legitimate reason for
any of them to flake — a failure means something genuinely broke. The
threshold is **100%**, enforced by `pytest`'s own exit code (already
CI-gating, no bespoke percentage-checking tooling needed). A future live
tier gated into CI (were API keys ever added as secrets) would warrant a
softer threshold given real model variance — but that's not built here,
since it isn't needed for what's actually CI-gated today.

## Consequences
- `tests/evals/test_evals.py` doubles as an integration test of the
  tracing feature itself (this phase's other deliverable): every case
  asserts against the trace record `agent.run()` just wrote to
  `traces/runs.jsonl`, not against a separate results structure.
- Running the full suite locally with real keys configured (as this repo's
  dev machine has) exercises all 23 cases for real, live tier included —
  the strongest signal, but not what CI checks.
- `recall_memory`'s tool module keeps its own lazily-cached
  `LongTermMemory` singleton, separate from the `long_term` instance
  `agent.run()` is given. Both must point at the same seeded instance for
  a case's `seed_long_term` turns to be visible to the tool when it
  actually runs — `test_evals.py` monkeypatches `recall_tool._memory`
  directly rather than relying on the `long_term=` parameter alone. This
  is a real seam in the Phase 5 code (harmless in production, since both
  default to the same real `data/memory.db` path when neither is
  overridden) that only surfaces when a test wants an isolated DB.
- Case count is 23 (14 deterministic, 9 live), within the spec's 20–30
  range. Not padded to 30 with synthetic filler — the spec's own
  methodology prefers fewer cases that reproduce real bugs over more
  cases that don't.
