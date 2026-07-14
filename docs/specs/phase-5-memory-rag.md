# Phase 5 — Memory & RAG

**Status:** Not started
**Depends on:** Phase 2 (agent loop)
**Target duration:** 1–2 weeks
**Release tag:** v0.5.0

## Goal
Give the agent memory that outlives a single conversation: a local vector store for semantic recall of past interactions, and optionally an index over the Obsidian vault so the assistant can answer from personal notes.

## Skill learned
Retrieval-augmented generation. Consistently top-3 most-requested skill in current AI job postings.

## Deliverables
- Long-term memory store: SQLite + local embeddings (sentence-transformers, no paid embedding API)
- Semantic recall: a query like "what did I ask you last week about X" returns relevant past turns, not just the last N messages
- Chunking strategy for stored conversation turns (and vault notes, if included) with a documented rationale
- Hybrid search: keyword (SQLite FTS) + vector similarity, not vector-only
- Optional: index the Obsidian vault (`D:\claude-projects\vault`) so the assistant can answer questions from personal notes
- Retrieval integrated into the Phase 2 agent loop as a tool/context-injection step, not a bolt-on script

## Definition of Done
- [ ] A semantic recall query against a seeded conversation history returns the correct past turn(s), verified against a small hand-built test set (≥10 query/expected-result pairs)
- [ ] Hybrid search demonstrably beats vector-only or keyword-only on at least one test case in the set (e.g. an exact-term query that vector search alone misses)
- [ ] Chunking approach is documented with the reasoning (chunk size, overlap, why)
- [ ] If vault indexing is included: a question answerable only from vault notes gets a correct, cited answer
- [ ] Retrieval latency is measured and reported (embedding + search time for a typical query)
- [ ] README demo: terminal session showing a "what did I ask about X last week" style query resolved correctly
- [ ] Repo tagged `v0.5.0`

## Efficient Learning Path
- sentence-transformers quickstart — pick one small, fast model (e.g. an MiniLM-class model) and move on; don't benchmark every embedding model on the Hub
- SQLite FTS5 docs, "Full-text Index Queries" section — enough to combine with vector search for hybrid retrieval
- One focused read on chunking strategies (fixed-size vs. semantic/recursive chunking) — a single well-known blog post or doc page is enough, this is a solved problem with a few standard answers
- One comparison read on "when RAG beats long context" — you need a defensible interview answer, not a literature review

**Methodology:** build the naive version first — embed every turn, cosine-similarity search, done — get a demo working, then add hybrid search and chunking refinement once you can see where naive retrieval actually fails on your own test set. Don't design the retrieval pipeline around failure modes you haven't observed yet.

## Concepts to be able to explain in interview
Chunking strategies, embedding models, hybrid search (keyword+vector), when RAG beats long context.
