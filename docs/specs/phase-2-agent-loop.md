# Phase 2 — Tool-Calling Agent Loop

**Status:** Complete (v0.2.0)
**Depends on:** Phase 1 (LLM router)
**Target duration:** 1–2 weeks
**Release tag:** v0.2.0

## Goal
Implement the ReAct-style agent loop from first principles — the core mechanic every "AI agent" product is built on — without reaching for a framework. This is the single most interview-relevant phase of the whole project.

## Skill learned
Agent orchestration from first principles. THE core AI-engineer interview topic in 2026.

## Deliverables
- ReAct loop: LLM call → tool call → tool result → LLM call, with a max-hop guard to prevent infinite loops
- Tool registry pattern: each tool is one module exposing a schema + function + its own tests
- 3–4 real tools: time/date, file search, web search (Tavily free tier), shell command execution with a strict allow-list
- Conversation memory: rolling window with automatic summary compression once the window fills
- Validation layer that rejects/handles a hallucinated tool call (unknown tool name, malformed args) gracefully instead of crashing

## Definition of Done
- [x] Given a prompt requiring 2+ sequential tool calls, the loop resolves it end-to-end without manual intervention
- [x] Max-hop guard demonstrably stops a deliberately-induced infinite loop (test case included)
- [x] Each tool has its own unit tests independent of the agent loop
- [x] Shell tool refuses any command not on the allow-list (tested with a deliberately dangerous command)
- [x] Conversation memory compresses correctly when the window overflows — test asserts token count stays bounded across a long simulated conversation
- [x] A malformed/hallucinated tool call from the LLM is caught and fed back as an error observation, not an unhandled exception
- [x] README demo: terminal recording of a multi-step tool-using conversation
- [x] Repo tagged `v0.2.0`

## Efficient Learning Path
- The original ReAct paper (Yao et al., "ReAct: Synergizing Reasoning and Acting in Language Models") — read the abstract + the loop diagram, skip the benchmark tables
- Anthropic's and OpenAI's own "tool use" / "function calling" docs for the exact JSON schema shape you need to emit — this is the part you'll actually copy
- One comparison read on ReAct vs. plan-and-execute (a blog post is enough) so you can articulate the tradeoff in an interview
- Do NOT read LangChain's agent source as your primary reference — the spec deliberately avoids the framework so the codebase demonstrates first-principles understanding

**Methodology:** build the loop with a single hardcoded tool first (e.g. time/date), get one full round-trip working, then generalize into the registry pattern once you've felt the shape of the problem. Designing the registry abstraction before you have two tools to compare is premature.

## Interview topics you can now speak to
Function calling schemas, ReAct vs. plan-and-execute, hallucinated tool calls and validation, context management, guardrails (allow-listed shell).

## Interview line
*"I implemented the agent loop myself, then evaluated frameworks."*
