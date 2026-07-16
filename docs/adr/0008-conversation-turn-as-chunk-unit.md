# 0008 — Long-term memory: one turn = one chunk, SQLite FTS5 + RRF for hybrid search

**Status:** Accepted

## Context
Phase 5 needs long-term recall over conversation history: given a query like
"what did I ask about Docker last week", return the actual past turn(s), not
just whatever fits in the current context window (that's what
`memory.ConversationMemory`, Phase 2's rolling window, already does within a
single session).

Two design questions: how to chunk stored content for embedding, and how to
combine keyword and semantic search.

## Decision — chunking
One conversation turn (one user message or one assistant reply) is stored
and embedded as a single, unsplit chunk. No fixed-size or recursive
sub-chunking.

Reasoning: the standard chunking problem (500–1000 token documents that
overflow one embedding's effective context and need splitting with overlap)
doesn't apply to chat turns — a turn is naturally bounded by how much a
person types or an LLM replies in one hop, almost always well under the
embedding model's input limit. Splitting a turn further would only fragment
retrieval (half a sentence back with no surrounding context) for no benefit.
This decision is scoped to conversation turns; indexing long-form documents
(e.g. the Obsidian vault, deferred — see the phase-5 spec's "optional"
deliverable) would need real fixed-size/recursive chunking with overlap,
revisit then.

## Decision — storage and hybrid search
SQLite, not a dedicated vector DB (Chroma, FAISS, etc.): one `turns` table
holds role/content/timestamp/embedding (as a raw float32 BLOB), paired with
an FTS5 virtual table for keyword search. Vector search is a linear
cosine-similarity scan over all stored embeddings via numpy — no ANN index.

Keyword and vector result lists are combined with **reciprocal rank fusion**
(`score = sum(1 / (60 + rank + 1))` across both lists) rather than trying to
normalize and blend BM25 scores with cosine scores directly — RRF only needs
rank position from each list, sidestepping the fact that BM25 and cosine
similarity live on incomparable scales.

Reasoning: SQLite is already the project's storage layer (see the config/
tools), needs no new service to run, and FTS5 ships in Python's stdlib
`sqlite3` build. A dedicated vector DB is a real dependency (another thing
to install, run, back up) for a problem a linear scan solves fine at
personal-assistant scale — thousands of turns, not millions. The linear scan
is marked `# ponytail:` in `long_term_memory.py` with its upgrade path (an
ANN index such as `sqlite-vec`) named directly, for if/when recall latency
actually becomes a problem.

## Consequences
- Adding `sentence-transformers` (MiniLM-class model, ~90MB, downloaded once
  and cached like Piper/faster-whisper's weights) is the one new dependency
  this phase introduces.
- `long_term_memory.py` has zero new runtime services — same "just files on
  disk" deployment story as the rest of Sorena.
- The `data/memory.db` file is local-only (gitignored) — it's a user's real
  conversation history, not example/test fixture data.
- If recall latency or turn volume outgrows a linear scan, replace
  `_vector_search`'s numpy matmul with an ANN index without touching the
  hybrid-fusion or FTS5 layers — they're independent of how the vector side
  finds its candidates.
