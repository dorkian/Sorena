# 0014 — JobScout rebuilt on LangGraph; PostgreSQL + pgvector added for job-search vector search and checkpointing

**Status:** Accepted

## Context
Phase 7 (`docs/specs/phase-7-jobscout-graph.md`) rebuilds the `JobScout` specialist's
execution on a LangGraph `StateGraph` and adds retrieval-augmented generation over Ash's
own CV (`cv-optimizer/builder/master.json`) and past job-application verdicts
(`second-brain/01-projects/cv-optimizer/*/analysis.md`), plus a bounded read/write bridge
to Ash's real, already-running job tracker (`ai-job-search-assistant`, `localhost:3131`,
no auth of its own).

This is the first time anything in Sorena reaches for LangChain or LangGraph. That's not
neutral ground — it directly touches two prior decisions:

- `docs/specs/phase-2-agent-loop.md` built the shared tool-calling agent loop by hand and
  says so explicitly: "the spec deliberately avoids the framework so the codebase
  demonstrates first-principles understanding."
- `docs/adr/0008-conversation-turn-as-chunk-unit.md` went further and named the exact
  category of dependency this phase now adds, to reject it: *"SQLite, not a dedicated
  vector DB (Chroma, FAISS, etc.) ... A dedicated vector DB is a real dependency (another
  thing to install, run, back up) for a problem a linear scan solves fine at
  personal-assistant scale."* ADR 0008 chose a hand-rolled `numpy` cosine scan over
  SQLite-stored embeddings, fused with keyword search via reciprocal rank fusion, and it
  works well for that job.

So the honest question this ADR has to answer isn't "should Sorena ever use a framework or
a new data service" — Phase 2 and ADR 0008 already answered that, twice, on their own
merits — it's **why Phase 7 adds not one but two new operational pieces (a framework, and a
brand-new running database service) instead of extending what already exists.**

**Scale doesn't force the decision.** ADR 0008's data-volume argument ("thousands of turns,
not millions") applies just as well to this phase's corpus — CV facts and past application
analyses are on the order of a few hundred chunks, refreshed by an explicit script
(`build_jobscout_index.py`), not written on every turn the way conversational memory is. A
linear scan, or an embedded store, would be plenty fast here too. If this were purely an
engineering decision, ADR 0008's reasoning would still win and this phase should extend the
existing SQLite approach.

**The deciding factor is the explicit goal of this phase, not the data — and that goal
evolved once during scoping, which is itself worth recording.** Ash asked for Sorena to
extend into the job-search domain *and* specifically to get real practice with LangChain,
LangGraph, and vector search. The first draft of this ADR proposed Chroma (an embedded,
zero-service vector database) specifically *because* it required no new running service —
staying closest to ADR 0008's minimalism while still exercising LangChain's retriever
abstraction. Before this ADR was approved, Ash raised a concrete, better-informed
objection: he's seeing **PostgreSQL named directly in real job postings**, and asked
whether Postgres would serve the stated goal better than Chroma. It does — for a reason
independent of the LangChain-practice goal:

- **PostgreSQL + `pgvector` is arguably more production-realistic than a dedicated vector
  database for this use case.** A significant share of real companies run Postgres+pgvector
  for RAG rather than standing up Chroma/Pinecone/Weaviate, precisely because it avoids a
  second storage system. Choosing Postgres here isn't a downgrade from "proper vector DB"
  to "just SQL" — it's arguably the more senior answer to "how would you build this for
  real," and it directly answers a skill Ash has independent evidence is being asked for.
- It's still genuine LangChain vector-search practice: `langchain-postgres`'s `PGVector`
  store is a first-class LangChain integration with the same retriever abstraction Chroma
  would have provided. Nothing is lost on the original goal.
- Once Postgres is in the picture anyway, it can also back the LangGraph checkpointer
  (`langgraph-checkpoint-postgres`) instead of a second, separate SQLite file — one new
  service handles both jobs, rather than "Postgres for vectors, SQLite for checkpoints."

Considered and rejected:
- **Chroma (embedded, zero-service) for the vector store, SQLite for the checkpointer** —
  this ADR's own first draft. Rejected after Ash's Postgres question: it satisfied the
  LangChain-practice goal but not the more specific, better-informed signal that Postgres
  itself is what's actually being asked for, and it would have meant running *two* new
  storage mechanisms in parallel (Chroma + a separate SQLite checkpoint file) instead of
  one.
- **Extend `long_term_memory.py`'s existing SQLite+FTS5+numpy store to also index CV/job
  data.** Zero new dependencies, fully consistent with ADR 0008. Rejected because it
  defeats the actual purpose of this phase — the point isn't retrieval quality (any of
  these approaches works fine at this scale), it's exercising named, in-demand
  technologies, and this option exercises none of them.
- **LangChain's higher-level chains (`RetrievalQA`, LCEL chains) instead of a raw
  retriever.** Rejected as unnecessary indirection — this phase injects retrieved chunks
  into a prompt by hand inside a LangGraph node, which is more explicit, easier to debug,
  and just as valid an answer to "how would you build RAG" in an interview.
- **LangSmith for observability**, since it's LangChain's own product and would come "for
  free" alongside LangGraph. Rejected as the default: it's a hosted/cloud service, and
  turning it on by default would quietly break Sorena's $0/local-first invariant for the
  whole repo over one phase's convenience. Kept as an explicitly opt-in, documented,
  off-by-default path (`SORENA_LANGSMITH`); the default observability path is a small
  LangChain-compatible callback handler writing into the trace sink Phase 6 already built
  (`traces/runs.jsonl`), so this phase's runs show up next to every other agent's.

## Decision
Adopt LangGraph for JobScout's execution graph, and **PostgreSQL 16 with the `pgvector`
extension** (via `langchain-postgres`'s `PGVector` store and `langgraph-checkpoint-postgres`'s
`PostgresSaver`) as one consolidated new service backing both vector search and graph
checkpointing — **scoped to this one specialist**, not the shared agent loop every other
specialist runs through, and not a replacement for Phase 5's SQLite-based conversational
memory (`long_term_memory.py`, governed by ADR 0008, is untouched). This is a deliberate,
narrow, two-part exception to the patterns Phase 2 and ADR 0008 established — a framework
for the execution graph, and a real running database for storage — made for stated,
concrete reasons (practicing named frameworks Ash needs for his job search, and Postgres
specifically because he has direct evidence it's being asked for), not because either was
found technically necessary at this data's scale.

Concretely:
- `src/sorena/agents/jobscout_graph.py` — a LangGraph `StateGraph` with typed (Pydantic)
  state, conditional routing, a `PostgresSaver` checkpointer, and exactly one
  `interrupt()` — before the `deep_dive` scoring node, matching JobScout's existing prompt
  language that deep-dive scoring is "for one posting Ash actually cares about."
- `docker-compose.yml` gains a `postgres` service (`pgvector/pgvector:pg16`), Docker,
  volume at `data/postgres/` (covered by the existing `data/` gitignore rule).
- `src/sorena/jobscout_vectors.py` — `psycopg` + `CREATE EXTENSION IF NOT EXISTS vector` +
  `langchain-postgres`'s `PGVector` store, wrapping the same `all-MiniLM-L6-v2` model Phase
  5 already downloaded and cached, exposed through a LangChain retriever.
- The retrieved chunks are injected directly into `deep_dive`'s judgment prompt (real
  RAG — generation grounded in retrieval), while the cheaper `vector_rank` node on the
  bulk-search path is retrieval-only, so the codebase demonstrates and can explain both.
- `src/sorena/tools/tracker_tool.py` bridges to the real tracker with a narrow, enum-bounded
  write surface (`PUT .../status`, `POST .../events` only — never job creation, scoring, or
  document endpoints), because the tracker itself has no auth and the boundary has to live
  in Sorena's tool code. Independent of the Postgres decision above — the tracker keeps its
  own storage (`better-sqlite3`), untouched.
- `docs/specs/phase-7-jobscout-graph.md` has the full architecture, deliverables, and
  definition of done, including a Provision step (bring up Postgres, prove the extension
  and a round-trip query) before any LangChain/LangGraph code is written against it.

## Consequences
- This is the repo's **first framework dependency for an agent's core execution**
  (`langgraph`, `langchain-core`) and its **first new running database service beyond the
  application's own SQLite files** (`postgres` in Docker) — a real, visible divergence from
  two prior decisions, made twice over in one phase. That divergence is the point of this
  ADR, not an oversight: anyone reading Phase 2, ADR 0008, and this ADR together should be
  able to see that hand-rolling and storage-minimalism were the defaults, and that this was
  a deliberate, scoped, justified exception on both counts — not a change of philosophy, and
  not a decision made blind to the tension (this ADR's own first draft chose the more
  minimal Chroma option before Ash's direct feedback changed it, and that revision is
  recorded above rather than silently overwritten).
- **Two independent long-term-storage mechanisms now exist in Sorena for two different
  jobs**: ADR 0008's SQLite+FTS5+numpy hybrid search remains exactly as-is for
  conversational long-term memory (`long_term_memory.py` is untouched by this phase) — it
  was not judged inadequate. Postgres/pgvector is added alongside it, only for JobScout's
  CV/job-analysis corpus and its own graph checkpoints. Future phases should not assume "we
  now use Postgres project-wide"; the two stores solve different problems for different
  reasons and both are intentional.
- **Sorena's operational footprint grows**: after this phase, running Sorena's full
  capability set means Docker for the tracker (already true, external to Sorena) *and* for
  this new Postgres service — plus, whenever Phase 8 resumes from its current stash, Neo4j
  as a third container. This is a real shift away from "just files on disk" for the phases
  that need it; conversational memory, voice, and the other specialists remain pure
  local-file/no-service as before. Worth naming plainly rather than letting it accumulate
  unnoticed phase by phase.
- New dependencies: `langgraph`, `langgraph-checkpoint-postgres`, `langchain-core`,
  `langchain-postgres`, `psycopg[binary,pool]`, `httpx` (for `tracker_tool.py`) — added
  flat to `pyproject.toml`, matching the repo's existing convention of no
  optional-dependency groups.
- The tracker write boundary (enum-only status/event writes, no other verbs reachable from
  any tool in `tracker_tool.py`) is the only thing standing between an LLM's tool call and
  an unauthenticated write to Ash's real job-application data — this is called out
  explicitly here because it's a security property of the code, not just a design
  preference, and any future change to `tracker_tool.py` should preserve it deliberately,
  not accidentally widen it. It is unaffected by, and independent of, the Postgres decision
  above.
- If a future phase needs vector search over a third kind of Sorena data, this ADR is the
  reference for "which store and why" — the answer depends on whether the goal is retrieval
  quality at scale (lean SQLite/ADR 0008-style), framework practice for a specific named
  technology (as here), or a concrete, evidenced signal about what's actually being asked
  for externally (as the Postgres pivot here was) — not a blanket rule, and not always the
  first idea either.
