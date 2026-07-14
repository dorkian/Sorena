# Phase 1 — LLM Router with Fallback

**Status:** Complete (v0.1.0)
**Depends on:** Phase 0 (repo foundation)
**Target duration:** 1 week
**Release tag:** v0.1.0

## Goal
Build a provider-agnostic LLM call layer that survives rate limits and outages by falling back across providers, and that logs enough telemetry to reason about cost and latency. This is the foundation every later phase calls through.

## Skill learned
Multi-provider LLM engineering and rate-limit resilience. Companies are actively struggling with single-provider outages and cost overruns — this is a concrete, demoable answer to "how do you make an LLM app production-resilient?"

## Deliverables
- Provider chain: Groq → Gemini → Ollama (local), unified through LiteLLM
- Retry logic with exponential backoff per provider
- Per-provider rate-limit tracking (RPM/RPD) that trips the fallback before a 429 happens, not just after
- Structured logging of tokens, latency, and cost per call (a small telemetry layer — even a JSONL file is enough)
- Config-driven provider order and model choice (no hardcoded provider names in call sites)
- Unit tests with mocked providers that prove: (a) fallback triggers on simulated failure, (b) rate-limit tracking blocks a provider before real exhaustion, (c) telemetry is recorded per call

## Definition of Done
- [ ] A single `chat(messages) -> response` function is the only entry point the rest of the codebase uses
- [ ] Killing/mocking the primary provider mid-run causes an automatic, logged fallback to the next provider with no caller-visible error
- [ ] Rate-limit tracker can be unit-tested by simulating N calls and asserting the (N+1)th call routes to the next provider
- [ ] Every call produces one telemetry record (provider, model, tokens in/out, latency ms, cost estimate, timestamp)
- [ ] `pytest` covers fallback, rate-limiting, and telemetry with mocked providers (no real API calls in CI)
- [ ] README demo: run one script showing a forced fallback in the terminal output
- [ ] Repo tagged `v0.1.0`

## Efficient Learning Path
- LiteLLM official docs — "Routing" and "Fallbacks" pages specifically; skip the rest of the docs until you need them
- Read the rate-limit section of one major provider's API docs (Groq or Gemini) closely enough to know their actual RPM/RPD free-tier numbers — you need the real numbers, not the general concept
- One blog post or doc page on exponential backoff with jitter (concept is 10 minutes of reading, don't chase a whole resilience-engineering book for this)
- Skim LiteLLM's own source for its fallback implementation if you want to explain "how it works under the hood" in an interview — 15 minutes, not a deep dive

**Methodology:** build the naive version first (try provider A, except → try B, except → try C), get it working end-to-end, then layer in backoff and rate-limit tracking. Don't design the retry/backoff abstraction before you have a failing case to test it against.

## Interview topics you can now speak to
Token budgets, RPM/RPD limits, why routing beats vendor lock-in, temperature/context-window tradeoffs.
