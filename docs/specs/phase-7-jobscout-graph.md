# Phase 7 — JobScout Graph (LangGraph + Vector Search)

**Status:** Not started
**Depends on:** Phase 2 (agent loop — JobScout currently runs through it), Phase 5
(long-term memory — embedding model reused), Phase 6 (eval harness + tracing)
**Target duration:** ~2.5 weeks (8 steps, ~an evening each — one step added to provision
Postgres, see Component choices)
**Release tag:** v1.1.0 (this phase is being built ahead of the already-drafted Phase 8;
Phase 8's spec currently reserves ADR 0014 and tag v1.1.0 for itself — when Phase 8
resumes from its stash, its own doc needs updating to ADR 0015 / v1.2.0. Not touched by
this phase; noted here so it isn't lost.)

## Goal

Rebuild `JobScout` — currently a single-prompt agent running through the generic
tool-calling hop loop — on a real **LangGraph** `StateGraph`: an explicit multi-node
workflow with conditional routing, **Postgres-backed checkpointing**, and one deliberate
human-in-the-loop `interrupt()`. Add genuine **RAG** (retrieval-augmented generation) over
Ash's own CV and job-application history using **Postgres + pgvector** via **LangChain**'s
retriever abstractions — not a toy demo corpus, his actual `master.json` and past
`analysis.md` verdicts. One Postgres instance backs both the vector store and the graph
checkpointer — one new service, not two. Make JobScout **read-aware** of Ash's real,
already-running job tracker
(`ai-job-search-assistant`, `localhost:3131`) so it doesn't resurface jobs he's already
scored or applied to, and give it one narrow, enum-bounded **write** path so Ash can report
application outcomes to Sorena directly and have them land in the real tracker.

The concrete gap this closes: JobScout today only knows what's in a local `profile.yaml`
and whatever it's found on Remotive — it has no idea what Ash has actually already applied
to, no grounding in his real CV language, and can't record an outcome he reports out loud.

This is also the repo's first use of LangChain/LangGraph. Every prior phase — including two
explicit prior decisions (`phase-2-agent-loop.md`'s spec text, and Phase 8's own
not-yet-built spec) — deliberately
hand-rolled instead of reaching for a framework, specifically to prove the fundamentals
first. This phase is a conscious, scoped exception: framework adoption for one specialist's
workflow, not the shared agent loop, justified in full in ADR 0014 before any code is
written.

## Skill learned

LangGraph `StateGraph` construction (nodes, conditional edges, typed state via Pydantic,
checkpointers, `interrupt()`/resume); **PostgreSQL** as both a relational store and, via
**pgvector**, a production-style vector database (schema/extension setup, connection
pooling with `psycopg`, running a stateful service in Docker); LangChain retriever-based
RAG (embeddings wrapper, vector store, prompt-context injection — not just similarity
search); safely bounding an LLM agent's write access to an external system with no auth of
its own (enum-constrained tool inputs, endpoint allow-listing;
[[securing-agentic-ai-tool-invocation]]-style least-privilege tool design); LangChain
callback-based observability bridged into an existing tracing sink instead of adopting a
new cloud dependency by default.

## Architecture

```
User turn ──▶ Orchestrator._classify() ──▶ role == "jobscout"?
                                               │
                                               ▼
                                    jobscout_graph.run() (LangGraph StateGraph,
                                    Postgres checkpointer, replaces the generic
                                    agent.run() hop loop for this one role)

                                    ┌───────────────────────────────────────┐
                                    │              route (LLM)               │
                                    └───────────────────────────────────────┘
                    bulk search ──────┼── deep-dive ──────┼── report outcome ──── skill gap
                         │                    │                    │                  │
                         ▼                    ▼                    ▼                  ▼
                  bulk_search          interrupt() ⏸        status_update      skill_gap
              (search_and_score_jobs)  wait for Ash's            │           (get_skill_gap /
                         │             go-ahead                  ▼          notify_coach_of_
                         ▼                    │            tracker_tool.py    skill_gap)
              dedup_against_tracker           ▼            (PUT status,
              (get_tracked_jobs, fuzzy   deep_dive              POST event)
               company+title match)      1. semantic_match(JD) → Postgres/
                         │                  pgvector retriever → top-k chunks
                         ▼                  from master.json + past analysis.md
                  vector_rank               (RETRIEVAL)
              (semantic_match, cheap    2. inject chunks into judgment
               retrieval-only signal       prompt → LLM scores the posting
               next to score_job())        GROUNDED in Ash's real CV +
                         │                  past verdicts (GENERATION —
                         ▼                  this is the RAG step)
                    final reply         3. save_job_match_score
                                             │
                                             ▼
                                        final reply

Everything (bulk_search, get_cv, save_job_match_score, get_skill_gap,
notify_coach_of_skill_gap, recall_memory) reuses JobScout's existing tools unchanged —
this phase adds nodes and routing around them, not a rewrite of what they do.
```

## Component choices

| Concern | Choice | Rationale |
|---|---|---|
| Agent workflow | LangGraph `StateGraph`, typed state via Pydantic model | The one place in Sorena a framework earns its keep over hand-rolling a third time — checkpointing and `interrupt()` are non-trivial to reimplement correctly, and practicing the framework itself is an explicit goal of this phase. Scoped to JobScout only; the shared `agent.run()` hop loop every other specialist uses is untouched (consistent with Phase 2's reasoning, not a reversal of it). |
| Data store | PostgreSQL 16 + `pgvector` extension, one container (`pgvector/pgvector:pg16` image), Docker, volume at `data/postgres/` (covered by the existing `data/` gitignore rule, same as Phase 8's planned `data/neo4j/`) | Chosen over Chroma specifically because Ash has seen it named directly in real job postings — see ADR 0014 for the full reasoning, including why this is a deliberate divergence from ADR 0008's "avoid a dedicated vector DB" stance. One Postgres instance serves both roles below rather than mixing storage engines. |
| Checkpointer | LangGraph's Postgres checkpointer (`langgraph-checkpoint-postgres`, `PostgresSaver`), same Postgres instance/database as the vector store | Consolidates onto the one new service instead of adding Postgres for vectors while keeping a separate SQLite file for checkpoints — one connection string, one thing to run and back up. Diverges from `bus.py`'s "reuse the existing SQLite file" pattern deliberately, for the same reason as the vector store: production-realistic Postgres experience was the explicit goal, and checkpoint state naturally belongs next to the vector data it's checkpointing decisions about. |
| Vector store | `langchain-postgres`'s `PGVector` store against the same Postgres instance | First-class LangChain integration (same retriever abstraction Chroma would have given), but backed by a database Ash actually needs practice with. `pgvector`'s HNSW/IVFFlat indexing is real production vector-search technique, not a toy. |
| Embeddings | `all-MiniLM-L6-v2`, wrapped via LangChain's HuggingFace embeddings interface | Same model Phase 5 already downloaded and cached for long-term memory — one model, two callers, zero new model weights. |
| Retrieval → generation | LangChain retriever (`vectorstore.as_retriever()`) feeding retrieved chunks directly into the `deep_dive` judgment prompt | This is what makes it RAG rather than "vector search as a feature" — the LLM's scoring reasoning is grounded in retrieved CV/past-verdict text, not just informed by a similarity number next to search results. `vector_rank` (bulk-search annotation) is deliberately kept as the cheaper retrieval-only half, so the codebase can demonstrate and explain both. |
| Tracker integration | Read (`GET /api/jobs`, `GET /api/actions/applications`) + two bounded writes (`PUT .../status`, `POST .../events`), both write tools accepting only a fixed enum, never free text, for status/event_type/outcome | The tracker (`ai-job-search-assistant`, Docker on `localhost:3131`) has no auth at all — the safety boundary has to live in Sorena's own tool code. Enum-only write parameters mean there is no code path from an LLM hallucination to an arbitrary write; job creation, scoring, and document-generation endpoints are simply never called by anything in `tracker_tool.py`. |
| Observability | A custom LangChain `BaseCallbackHandler` writing into the existing `trace.py` → `traces/runs.jsonl` sink | LangSmith (LangChain's own hosted tracing product) was considered and deliberately not wired in by default — it's a cloud service, and enabling it by default would quietly break Sorena's $0/local-first invariant. Documented as an env-var-togglable option for demo purposes, off by default. |
| Dependencies | `langgraph`, `langgraph-checkpoint-postgres`, `langchain-core`, `langchain-postgres`, `psycopg[binary,pool]` added flat to `pyproject.toml` | Matches the repo's existing convention — no `[project.optional-dependencies]` groups exist anywhere yet (voice, memory, and graph deps are all flat too). |

New dependencies: `langgraph`, `langgraph-checkpoint-postgres`, `langchain-core`,
`langchain-postgres`, `psycopg[binary,pool]`. **Unlike every dependency added in Phases 0–6,
this phase requires a new running external service** (Postgres, via Docker) beyond the
tracker (which already runs persistently for the `/job` skill's own use) — this is a real
increase in Sorena's operational footprint, named plainly rather than glossed over, and
covered in full in ADR 0014.

## Deliverables

- **`docker-compose.yml`** — new `postgres` service, `pgvector/pgvector:pg16` image,
  volume at `data/postgres/`, healthcheck (`pg_isready`), exposed on `SORENA_POSTGRES_URI`'s
  configured port (default `5432`; documented override if that port's already taken
  locally). Mirrors Phase 8's planned Neo4j service shape.
- **`src/sorena/jobscout_vectors.py`** — `psycopg` connection + `CREATE EXTENSION IF NOT
  EXISTS vector` bootstrap + `langchain-postgres` `PGVector` store setup + LangChain
  retriever; `semantic_match(job_description, top_k=5) ->
  list[{source, snippet, similarity}]`.
- **`examples/build_jobscout_index.py`** — one-shot indexing script (mirrors
  `examples/benchmark_memory_recall.py`), reads `cv-optimizer/builder/master.json` +
  `second-brain/01-projects/cv-optimizer/*/analysis.md`, embeds and upserts into
  Postgres/pgvector by content hash (idempotent re-run, same discipline as Phase 5's
  `MERGE`-style idempotency — here an `ON CONFLICT ... DO UPDATE`).
- **`src/sorena/tools/tracker_tool.py`** — `get_tracked_jobs()`, `get_tracked_applications()`,
  `update_application_status(job_id, status)`, `log_application_event(job_id, event_type,
  event_date, outcome)`. `httpx`-based, non-fatal on connection failure (mirrors Phase 3's
  "dead server is caught, not fatal" MCP behaviour).
- **`src/sorena/agents/jobscout_graph.py`** — the `StateGraph`: `route`, `bulk_search`,
  `dedup_against_tracker`, `vector_rank`, `deep_dive` (with the single `interrupt()` and the
  RAG-grounded judgment prompt), `status_update`, `skill_gap`; Pydantic-typed graph state;
  `PostgresSaver` checkpointer; `run(user_message, thread_id) -> str` as its external
  interface.
- **`src/sorena/callbacks.py`** — `TraceCallbackHandler(BaseCallbackHandler)` bridging
  LangChain/LangGraph run events into `trace.py`'s existing JSONL sink; `SORENA_LANGSMITH`
  env var (default off) documented as the opt-in path to LangSmith instead.
- **Orchestrator change** — `orchestrator.run()` branches: `role == "jobscout"` calls
  `jobscout_graph.run()` instead of the generic `agent.run()` hop loop. No other specialist
  changes.
- **`src/sorena/tools/jobscout_tool.py`** — fix: `SORENA_CV_PATH`/`SORENA_CV_PATH_FALLBACK`
  defaults updated from the dead Windows path to the current second-brain path on this Mac.
- **Config** (`config.py`): `SORENA_TRACKER_URL` (default `http://localhost:3131`),
  `SORENA_POSTGRES_URI` (default
  `postgresql://sorena:sorena@localhost:5432/sorena_jobscout`), `SORENA_LANGSMITH` (default
  `false`) — added to `.env.example` with comments, same discipline as existing vars
  (mirrors Phase 8's `SORENA_NEO4J_URI/USER/PASSWORD` pattern, one DSN string instead of
  three separate vars since `psycopg`/`langchain-postgres` both take a DSN directly).
- **`docs/adr/0014-jobscout-langgraph-vector-search.md`** — full rationale, including why
  this doesn't contradict Phase 2's / Phase 8's no-framework stance, and the tracker
  write-boundary design.
- **Tests/evals** appended to `tests/evals/cases.py` (both tiers, ADR 0010's pattern):
  - deterministic: each conditional edge in `route` sends the right node; `dedup_against_tracker`
    filters a mocked already-tracked job; `semantic_match` surfaces a CV chunk for a JD with
    no exact keyword overlap; the `interrupt()` actually pauses before `deep_dive` and resumes
    correctly from the checkpoint; `status_update` calls the tracker with an enum-only payload
    for a scripted "I got rejected by X" turn.
  - live: one full bulk-search → dedup → rank turn, skip-gated on missing API key.
- **README** "Demo: JobScout graph" section: a seeded example (bulk search showing dedup +
  semantic-match annotation) and a deep-dive example showing the interrupt/resume, plus the
  ADR link.

## Definition of Done

- [ ] Ash has read and approved this spec, in full, before any code is written
- [ ] Ash has read and approved ADR 0014, in full, before any code is written
- [ ] `SORENA_CV_PATH*` fixed; `get_cv()` returns real content on this machine
- [x] `docker-compose up postgres` brings up a healthy container; `CREATE EXTENSION vector`
      succeeds; a trivial `SELECT 1` round-trips through `psycopg` — proven before any
      LangChain/LangGraph code touches it (`examples/verify_postgres.py`, run 2026-09-17)
- [x] `semantic_match()` proven standalone (script or eval) — a CV/past-verdict chunk
      surfaces for a JD query with no exact keyword overlap, demonstrating retrieval beyond
      the existing keyword-heuristic `score_job()` (verified 2026-09-17: query naming no
      AI/agent-related words surfaced the Akeron role, a past "Agentic Developer" analysis,
      and the Sorena project entry, top 3 by similarity)
- [x] `tracker_tool.py`'s read functions proven against the real running tracker at
      `localhost:3131`; a clear, non-fatal error logged if it's unreachable (verified
      2026-09-17: `get_tracked_jobs`/`get_tracked_applications` returned real data, 94
      tracked applications)
- [x] `tracker_tool.py`'s two write functions accept only enum values for
      status/event_type/outcome — a test asserts an out-of-enum value is rejected before
      any HTTP call is made (verified 2026-09-17, plus a real end-to-end write: EY's
      application status corrected from stale `Saved` to `Applied` using the real `job_id`
      — caught and fixed a mix-up between `applications.id` and `applications.job_id`
      along the way, see tracker_tool.py's docstring)
- [x] `jobscout_graph.py`'s routing sends each of the 4 turn types (bulk search, deep-dive,
      report outcome, skill gap) to the correct node, verified by test cases (1 per route)
      (manually verified 2026-09-19 for all 4; pytest-ized in the Evaluate step)
- [x] `dedup_against_tracker` measurably filters a job already present in a mocked tracker
      response (verified 2026-09-19: a "Bending Spoons" raw result was filtered while an
      unrelated "NewCo" result survived)
- [x] The `interrupt()` before `deep_dive` actually pauses the graph and only proceeds after
      an explicit resume signal — verified in a test, not just by inspection (2026-09-19:
      real posting "Tech Lead Full-Stack Rails Engineer at Mitre Media" paused with
      `__interrupt__` populated and `state.next == ('deep_dive',)`, then resumed via
      `Command(resume=True)` to a real saved score)
- [x] `deep_dive`'s judgment prompt visibly includes retrieved CV/past-verdict chunks (this
      is the RAG assertion — not just that `semantic_match` runs, but that its output reaches
      the LLM's context) — `_judge_posting()`'s `context_block` is built from `semantic_match`
      and interpolated directly into the prompt sent to the LLM
- [x] `status_update` correctly PUTs status and POSTs an event to a mocked tracker for a
      scripted outcome-report turn, and never calls a create/score/document endpoint
      (verified 2026-09-19: "I got rejected by Bending Spoons today" → `update_application_
      status('abc-123', 'Rejected')` + `log_application_event('abc-123', 'rejected',
      today, 'fail')`, both via mocks; also proven through the full `run()` routing path,
      not just the node in isolation)
- [x] Orchestrator routes `jobscout` turns through `jobscout_graph.run()`; all 5 other
      specialists' behaviour is unchanged (existing eval cases for them still pass) —
      verified 2026-09-19: `orchestrator.run()` correctly routed a skill-gap question through
      the new graph, a non-jobscout question through the old hop loop unchanged, and all 11
      existing `test_orchestrator.py` cases still pass
- [x] `PostgresSaver` checkpoint state survives a process restart — a graph paused at the
      `deep_dive` `interrupt()`, then Sorena restarted, still resumes correctly from the
      same checkpoint (this is the concrete "why Postgres/a real checkpointer over an
      in-memory flag" proof) — proven 2026-09-19 across two genuinely separate `uv run
      python` processes (fresh interpreter each time, nothing shared but Postgres)
- [x] Every graph run writes trace events to `traces/runs.jsonl` via `TraceCallbackHandler`
      (verify LangSmith stays off unless `SORENA_LANGSMITH=true` is explicitly set) —
      verified 2026-09-19: a real run wrote a `traces/runs.jsonl` record with the correct
      node sequence (route → bulk_search → dedup_against_tracker → vector_rank), and
      `SORENA_LANGSMITH`/`LANGCHAIN_TRACING_V2` both confirmed off by default
- [x] New eval cases (deterministic + live) pass; deterministic tier green in CI's keyless
      environment — 20 deterministic tests in `tests/test_jobscout_graph.py` (no
      Postgres/network/LLM dependency, CI-safe), plus 3 integration tests in
      `tests/test_jobscout_graph_postgres_integration.py` skip-gated on Postgres
      reachability and/or an API key. **Deliberate deviation from the original plan**:
      these don't live in `tests/evals/cases.py`'s `EvalCase` list — that harness scripts
      `sorena.agent.run()`'s hop loop specifically (see `harness.py`), a different
      execution engine than this LangGraph-based graph, so forcing a fit there would have
      been the wrong abstraction. CI does not provision Postgres for this phase (a
      deliberate, documented choice, not an oversight) — the Postgres-dependent tests are
      meant to run locally (e.g. before tagging a release), not in CI.
- [ ] Full `uv run pytest` green locally (all tiers) and in CI (deterministic only)
- [ ] `docs/adr/0014-jobscout-langgraph-vector-search.md` written and cross-referenced
- [ ] README "Demo: JobScout graph" section added; `docs/specs/README.md` and the README
      roadmap table updated with the Phase 7 row (`v1.1.0`)
- [ ] Repo tagged `v1.1.0`
- [ ] `curl localhost:3131/api/health` still returns 200 after all testing — tracker
      untouched beyond the bounded status/event writes actually exercised on purpose
- [ ] `git stash list` still shows the pre-existing Phase 8 stash untouched

## Build order

0. **Approve.** This spec, read and approved in full. Then ADR 0014, read and approved in
   full. No code before both. *(Gate, not a build step — see Working agreement in the plan
   this spec was drafted from.)*
1. **Provision.** `docker-compose.yml`'s `postgres` service; `config.py`'s
   `SORENA_POSTGRES_URI` + `.env.example`; container up; `CREATE EXTENSION vector`; a
   trivial `psycopg` round-trip green. *New: running and connecting to a stateful Docker
   service — the same category of step Phase 8 planned for Neo4j, done here first.*
2. **Fix + configure.** `SORENA_CV_PATH*` defaults; remaining config vars
   (`SORENA_TRACKER_URL`, `SORENA_LANGSMITH`). *Relearns: the `config.py` flat-constant
   pattern, `.env.example` discipline (Phase 3/8).*
3. **Retrieve.** `jobscout_vectors.py` + `build_jobscout_index.py`; prove `semantic_match()`
   standalone against real indexed data (Ash's actual `master.json` + `analysis.md` files)
   before any graph code exists. *Relearns: embedding reuse from Phase 5, idempotent
   upsert-by-hash from Phase 5's `MERGE` discipline (here, `ON CONFLICT DO UPDATE`); new:
   `pgvector` schema/index setup, `langchain-postgres`'s `PGVector` store.*
4. **Bridge, read then write.** `tracker_tool.py`'s read functions first, proven against
   the real running tracker; then the two enum-bounded write functions, proven against a
   real test record. *Relearns: Phase 3's non-fatal dead-dependency pattern; new: designing
   a minimal write surface against an unauthenticated external service.*
5. **Graph, incrementally.** `route` → `bulk_search` → `dedup_against_tracker` →
   `vector_rank` first, no interrupt, no checkpointer — prove the linear+branching flow
   works. Then add the `PostgresSaver` checkpointer (same Postgres instance from step 1).
   Then add the single `interrupt()` before `deep_dive`, now wired to the RAG-grounded
   judgment prompt — prove it survives a real process restart, not just an in-process pause.
   Then `skill_gap`. Then `status_update`. *Relearns: the recall/tool-registry contract from
   Phase 2/3; new: LangGraph state, conditional edges, Postgres-backed checkpointing,
   `interrupt()`/resume across restarts.*
6. **Observe.** `callbacks.py`'s `TraceCallbackHandler`, wired into the graph, writing to
   the existing `traces/runs.jsonl`; confirm LangSmith stays off by default. *Relearns:
   Phase 6's tracing sink; new: LangChain callback handlers.*
7. **Wire in.** `orchestrator.run()`'s role branch to `jobscout_graph.run()`. *Relearns:
   `orchestrator.py`'s classify-then-delegate shape.*
8. **Evaluate + document.** Tests/evals above; ADR 0014 (already approved at step 0, now
   finalized alongside the shipped code if anything changed during the build); README demo
   section; spec-index + roadmap-table updates; tag `v1.1.0`.

## Efficient Learning Path

- LangGraph's own "Build a basic chatbot" + "Add tools" + "Add memory (checkpointing)" +
  "Human-in-the-loop" tutorial sequence (in that order) — this phase's node/edge/checkpoint/
  interrupt shape follows it directly; do this before writing `jobscout_graph.py`.
- **`pgvector`'s own README** — `CREATE EXTENSION`, the `vector` column type, distance
  operators (`<->` L2, `<=>` cosine), and HNSW vs. IVFFlat indexing (when each makes sense).
  This plus basic `psycopg` usage is the whole storage surface; do this before writing
  `jobscout_vectors.py`.
- LangChain's `langchain-postgres` `PGVector` quickstart — just enough to wire
  `as_retriever()` into a prompt; skip LangChain's higher-level chain abstractions
  (`RetrievalQA`, LCEL chains) — this phase injects retrieved context into a prompt by hand
  inside a graph node, which is more explicit and more useful to be able to explain than a
  pre-built chain.
- LangGraph's Postgres checkpointer docs (`langgraph-checkpoint-postgres`, `PostgresSaver`)
  — setup, and specifically how resume-after-restart differs from the in-memory
  `MemorySaver` used in LangGraph's own tutorials.
- One read on **RAG vs. plain vector search** — the distinction this spec's Architecture
  section draws between `vector_rank` (retrieval-only) and `deep_dive` (retrieval +
  generation grounded in it). Be able to explain both, and why a system might use either
  depending on cost/latency.
- One read on **LangGraph checkpointing + `interrupt()`** specifically — the mechanics of
  pause/resume and why a checkpointer backed by a real database (not just an in-memory flag)
  is what makes resuming reliable across process restarts — this phase actually proves that
  property, not just asserts it.
- One read on **pgvector vs. dedicated vector databases** (Chroma/Pinecone/Weaviate) — the
  real trade-off (one fewer service to run vs. purpose-built ANN performance at large
  scale), so the Postgres choice here can be explained as a judgment call, not "the only
  way."
- Skip: LangChain's agent executors, LCEL expression language beyond what a retriever needs,
  and LangGraph's multi-agent supervisor patterns — none of that is on the build path here
  (Sorena already has its own hand-rolled multi-agent orchestrator; this phase doesn't
  replace it).

**Methodology:** build and prove the vector store in complete isolation first (step 2) —
run `build_jobscout_index.py` against Ash's real files and query it from a plain script
before any LangGraph code exists. Then build the graph with no interrupt/checkpointer and
prove the routing works. Add checkpointing and the interrupt last, once the linear flow is
already trustworthy — debugging a pause/resume bug in a graph whose basic routing is also
unproven is much harder than debugging either one alone.

## Concepts to be able to explain in interview

LangGraph `StateGraph`: nodes, conditional edges, typed state; checkpointing and
`interrupt()`/human-in-the-loop, and why a database-backed checkpointer (not an in-memory
one) is what makes resume-after-restart real; the difference between retrieval-only vector
search and full RAG (context injected into generation); LangChain's retriever abstraction
vs. calling a vector DB directly; **PostgreSQL + pgvector as a production-style vector store
vs. a dedicated vector database (Chroma/Pinecone/Weaviate)** — the actual trade-off, and why
this codebase picked Postgres specifically (see ADR 0014); running a stateful service in
Docker for local development; least-privilege tool design against an unauthenticated
external API (enum-bounded writes, endpoint allow-listing); why a framework was adopted
here specifically after being rejected twice elsewhere in the same codebase, and why this
phase *also* diverges from ADR 0008's storage-minimalism stance specifically (a defensible,
scoped, and named exception, not an inconsistency); LangChain callback-based observability
vs. a hosted tracing product (LangSmith) and the trade-off of defaulting it off.
