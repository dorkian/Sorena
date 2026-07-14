# Phase 6 — Evaluation & Observability

**Status:** Not started
**Depends on:** Phase 2 (agent loop); benefits from Phases 3–5 being in place to have more to evaluate
**Target duration:** 1 week
**Release tag:** v1.0.0

## Goal
Close the loop on quality: a small eval suite that runs in CI and catches regressions in tool selection/answer correctness, plus structured trace logging for every agent run. This is what turns "a demo" into "an engineered system," and it's the phase that marks v1.0.0.

## Skill learned
LLM evals. The skill that currently separates senior from junior AI engineers, and the one interviewers probe hardest for.

## Deliverables
- Eval suite: 20–30 test cases covering "did the agent pick the right tool?" and "was the final answer correct?", run automatically in CI
- Trace logging: every agent run dumps a structured trace (steps taken, tools called, tokens used, latency per step) to `traces/`
- A summary script that reads `traces/` and reports pass/fail rate, tool-selection accuracy, and latency stats — a dashboard is optional, the folder + script is sufficient
- CI gate: a PR that regresses eval pass rate below a documented threshold fails the build
- Regression detection demo: a deliberately introduced bug (e.g. broken tool schema) causes a specific, named eval case to fail

## Definition of Done
- [ ] Eval suite has 20–30 cases, each with a documented expected outcome (right tool, right answer, or both)
- [ ] Eval suite runs via a single command (`pytest` target or dedicated script) and produces a pass/fail report
- [ ] Eval suite is wired into GitHub Actions CI and runs on every PR
- [ ] Every agent run (in eval or manual use) produces a trace file with steps/tools/tokens/latency
- [ ] Summary script produces a readable report from `traces/` (tool-selection accuracy %, pass rate, latency percentiles)
- [ ] A deliberately broken change (e.g. mangled tool schema) is caught by a specific failing eval case, demonstrated in README or a linked CI run
- [ ] README documents how to add a new eval case
- [ ] Repo tagged `v1.0.0`

## Efficient Learning Path
- OpenAI's or Anthropic's own "evals" documentation for the basic taxonomy (exact-match, LLM-as-judge, tool-selection accuracy) — read just enough to pick the right eval type per test case, not the full framework docs
- One short read on "LLM-as-judge" pitfalls (bias, cost, when to prefer deterministic checks) before defaulting to it for every case — most of your 20–30 cases should be deterministic (did it call tool X, does output contain Y), reserve LLM-as-judge for genuinely open-ended answers
- Skim your own Phase 1 telemetry code and Phase 2 tool registry before designing traces — the trace format should reuse what you already log, not invent a second logging system

**Methodology:** write the eval cases from your own real usage and the bugs you've already hit in Phases 1–5, not from a generic template — a case that reproduces a real bug you fixed is worth more than five synthetic ones. Deterministic checks (tool called, keyword present, schema valid) before LLM-as-judge; only reach for judge-based scoring when correctness genuinely can't be checked mechanically.

## Interview line
*"Every PR runs an eval suite against the agent — I can show regression detection on tool selection."* This alone gets follow-up questions in interviews.
