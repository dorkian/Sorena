# Sorena — Implementation & Learning Roadmap
*(personal AI assistant, named after the Parthian general known for cunning, decisive action)*

Goal: build a Jarvis-style local-first agent at $0/month, structured so that **each phase teaches one interview-ready skill** and ends with something demoable. Total: ~6 phases, each 1–2 weeks at limited hours.

---

## Phase 0 — Repo foundation (½ week)
**Skill learned: professional open-source project setup** (asked about in every senior/lead interview: "how do you structure a project?")

Deliverables:
- `pyproject.toml` with `uv` or `poetry` (modern Python packaging — mention this in interviews, pip+requirements.txt looks dated)
- `ruff` (lint+format), `pytest`, `pre-commit` hooks
- GitHub Actions CI: lint + test on every PR
- `README.md` with architecture diagram (Mermaid), quickstart, and a GIF demo placeholder
- `docs/spec/` folder — write the spec first (your existing workflow, and it interviews well: "I work spec-first")
- MIT license, `CONTRIBUTING.md`, issue templates

Interview line you earn: *"I set up CI, linting, and spec-first docs before writing feature code."*

---

## Phase 1 — LLM router with fallback (1 week)
**Skill learned: multi-provider LLM engineering, rate-limit resilience** (very hot: companies all struggle with provider outages/costs)

Build:
- Provider chain: Groq → Gemini → Ollama (local), via LiteLLM
- Retry with exponential backoff, per-provider rate-limit tracking
- Structured logging of tokens/latency per call (a tiny cost/telemetry layer)
- Unit tests with mocked providers proving fallback triggers

Concepts to be able to explain in interview: token budgets, RPM/RPD limits, why routing beats vendor lock-in, temperature/context-window tradeoffs.

---

## Phase 2 — Tool-calling agent loop (1–2 weeks)
**Skill learned: agent orchestration from first principles** (THE core AI-engineer interview topic in 2026)

Build:
- ReAct loop: LLM → tool call → result → LLM, with max-hop guard
- Tool registry pattern: each tool = one module with schema + function + tests
- 3–4 real tools: time/date, file search, web search (Tavily free tier), shell command with allow-list
- Conversation memory: rolling window + summary compression when context grows

Interview topics you can now speak to: function calling schemas, ReAct vs plan-and-execute, hallucinated tool calls and validation, context management, guardrails (allow-listed shell).

**Do NOT use LangChain here.** Building raw first is the differentiator — "I implemented the agent loop myself, then evaluated frameworks" is a strong interview answer.

---

## Phase 3 — MCP integration (1 week)
**Skill learned: Model Context Protocol** (rapidly becoming the standard; you already have credibility via code-graph-mcp)

Build:
- MCP *client* inside the agent: discover and call tools from any MCP server
- Connect your own `code-graph-mcp` as the first server — instant dogfooding story
- Expose the agent's native tools as an MCP *server* too (so Claude Desktop/Code can use your assistant's tools)

Interview line: *"I've built both sides of MCP — servers (code-graph-mcp, published) and a client in my agent."* Very few candidates can say this.

---

## Phase 4 — Voice pipeline (1–2 weeks)
**Skill learned: real-time audio + local inference** (differentiator for edge/embedded AI roles, and the demo factor is huge)

Build:
- STT: whisper.cpp (or faster-whisper) on CPU
- TTS: Piper
- Wake word: openWakeWord
- Streaming: start TTS on first sentence instead of waiting for full response (latency engineering — great interview material)

Concepts: VAD, audio buffering, latency budgets, local vs cloud inference tradeoffs.

---

## Phase 5 — Memory & RAG (1–2 weeks)
**Skill learned: retrieval-augmented generation** (top-3 most-requested skill in AI job posts)

Build:
- Long-term memory: SQLite + embeddings (sentence-transformers locally, free)
- Semantic recall: "what did I ask you last week about X"
- Optional: index your Obsidian vault so the assistant answers from your notes

Concepts: chunking strategies, embedding models, hybrid search (keyword+vector), when RAG beats long context.

---

## Phase 6 — Evaluation & observability (1 week)
**Skill learned: LLM evals** (the skill that separates seniors from juniors right now)

Build:
- A small eval suite: 20–30 test cases (did the agent pick the right tool? correct answer?) run in CI
- Trace logging: every agent run dumps a structured trace (steps, tools, tokens, latency)
- Simple dashboard or just a `traces/` folder of JSON + a summary script

Interview line: *"Every PR runs an eval suite against the agent — I can show regression detection on tool selection."* This alone gets follow-up questions in interviews.

---

## Phase 7 — AI Governance, Security & Responsible AI (½–1 week)
**Skill learned: AI governance, security, and responsible-AI practices** (now a standard line item in AI-native job descriptions, not just a nice-to-have)

Build:
- Threat model the agent: prompt injection via tool results/web content (you already enforce an instruction-source boundary in the system prompt — document it), tool-permission scoping, PII handling in `traces/telemetry.jsonl`
- `docs/SECURITY.md`: what gets logged, what's redacted, per-provider data-retention notes for each link in the Groq/Gemini chain
- Output guardrails: refuse-categories + PII scrubbing before anything hits `traces/`
- One paragraph per provider model documenting known limitations/bias caveats for your use case — not a full audit, just proof you understand the concept

Interview topics you can now speak to: OWASP LLM Top 10 (prompt injection, insecure output handling, excessive agency), EU AI Act risk tiers (where a personal assistant sits vs. high-risk systems), responsible-AI principles (transparency, human oversight, accountability), the difference between AI governance (org policy) and AI security (technical controls).

---

## ML & GenAI Foundations (study alongside all phases, no dedicated build)
Not a build phase — this project is agent/LLM-focused, not a classical-ML project, so don't invent a fake phase for it. Study these as you go and be ready to explain them in interviews:
- **Classical ML**: supervised vs. unsupervised, train/test/val splits, overfitting, common metrics (precision/recall/F1, RMSE) — enough to not get filtered out by an "ML fundamentals" screening question
- **Generative AI & LLM architecture**: transformer basics (attention, tokenization), pretraining vs. fine-tuning vs. RLHF, context windows, why decoder-only dominates chat models
- **Prompt engineering**: few-shot vs. zero-shot, chain-of-thought, system/user/assistant role design (you're already doing this in Phase 1/2 — name it explicitly in interviews)
- **Agentic workflows**: ReAct vs. plan-and-execute vs. multi-agent orchestration (Phase 2/3 gives you the hands-on version of this)

---

## Repo best practices checklist (public repo)
- One concept per module, docstrings on every public function
- Type hints everywhere + `mypy` or `pyright` in CI
- Each phase = one milestone/tagged release (v0.1 router, v0.2 agent loop…) — shows progression in commit history, which recruiters DO look at
- Architecture Decision Records (`docs/adr/`) — short markdown files explaining *why* you chose e.g. LiteLLM over raw SDKs. Interviewers love candidates who document decisions.
- Demo GIF/video in README (asciinema for terminal, short screen recording for voice)
- Write one short blog/LinkedIn post per phase — turns the repo into visible personal-brand content

## Skill → job-market mapping (summary)
| Phase | Skill | Job-post keyword |
|---|---|---|
| 0 | Project engineering | CI/CD, code quality |
| 1 | LLM routing | "LLM integration", cost optimization |
| 2 | Agent loop | "AI agents", function calling, orchestration |
| 3 | MCP | "MCP", tool ecosystems |
| 4 | Voice | multimodal, edge AI, latency |
| 5 | RAG | "RAG", embeddings, vector search |
| 6 | Evals | "LLM evaluation", observability |
| 7 | Governance/Security | "AI governance", "Responsible AI", "AI security" |
| — | ML/GenAI Foundations | "ML principles", "prompt engineering", "agentic workflow", "generative AI/LLM architectures" |
