# 0002 — Drop Ollama from the Phase 1 provider chain

**Status:** Accepted
**Date:** 2026-07-14

## Context
The roadmap's original provider chain was Groq → Gemini → Ollama (local), with Ollama as the final offline fallback. The dev machine isn't spec'd for running local LLM inference at usable latency/quality.

## Decision
Phase 1 ships with a two-provider chain: Groq → Gemini. `PROVIDER_CHAIN` stays config-driven (`SORENA_PROVIDER_CHAIN` env var), so a local Ollama entry can be appended later on hardware that supports it without touching `router.py`.

## Consequences
- No offline fallback yet — if both Groq and Gemini free tiers are exhausted, `chat()` raises instead of degrading to local inference.
- Re-adding Ollama later is a config change, not a code change, since the router already iterates an arbitrary provider list.
