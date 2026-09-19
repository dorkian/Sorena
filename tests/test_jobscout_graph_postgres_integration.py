"""Phase 7: integration tests that need a real, reachable Postgres instance
(the one docker-compose.yml's `postgres` service provides). semantic_match
needs a populated pgvector index; the checkpointer test proves real
persistence, not just in-memory behaviour that would pass even with a bug.

Skipped automatically (not failed) when Postgres isn't reachable, the same
"don't fail CI over a missing dependency" spirit as ADR 0010's live-tier
skip-gating on a missing API key -- just gated on infrastructure instead.
CI does not provision Postgres for this phase (a deliberate, documented
choice -- see docs/specs/phase-7-jobscout-graph.md), so these never run
there; run them locally (`docker compose up -d postgres` first).

router.chat is mocked in the first two tests -- those are about proving
Postgres persistence, not LLM judgment quality, so the LLM dependency is
removed rather than left as an unrelated second reason to fail. The last
test (test_live_bulk_search_full_turn) is the exception: it deliberately
needs a real LLM call (for routing) *and* real Postgres (for vector_rank),
so it doesn't fit tests/evals/cases.py's EvalCase harness -- that harness
scripts sorena.agent.run()'s hop loop specifically (see harness.py), a
different execution engine than this graph. Skip-gated on both an API key
and Postgres, same "don't fail CI over a missing dependency" spirit as
ADR 0010, just with two dependencies instead of one.
"""

import os

import psycopg
import pytest
from langgraph.types import Command

from sorena.config import POSTGRES_URI


def _postgres_reachable() -> bool:
    try:
        with psycopg.connect(POSTGRES_URI, connect_timeout=2):
            return True
    except Exception:
        return False


def _has_real_api_key() -> bool:
    return bool(os.getenv("GROQ_API_KEY") or os.getenv("GEMINI_API_KEY"))


pytestmark = pytest.mark.skipif(
    not _postgres_reachable(),
    reason="Postgres not reachable at SORENA_POSTGRES_URI -- run `docker compose up -d postgres`",
)


def test_semantic_match_finds_relevant_chunk_without_keyword_overlap():
    from sorena.jobscout_vectors import semantic_match

    results = semantic_match(
        "We need an engineer who can build autonomous software that plans its own "
        "steps and calls outside tools to get things done.",
        top_k=3,
    )
    if not results:
        pytest.skip("jobscout vector index is empty -- run examples/build_jobscout_index.py first")

    sources = [r["source"].lower() for r in results]
    assert any("akeron" in s or "sorena" in s for s in sources), (
        f"expected the Akeron role or Sorena project to surface by meaning alone, got: {sources}"
    )


def test_interrupt_pauses_and_resumes_via_real_postgres_checkpointer(monkeypatch, tmp_path):
    """Proves the property ADR 0014 exists to justify: pause state survives
    somewhere other than the compiled graph object's own memory. A fresh
    compiled graph (not the cached module singleton) resumes correctly
    using only the thread_id, which is only possible if Postgres -- not
    Python-process memory -- is really the source of truth. The strongest
    version of this claim (two genuinely separate OS processes) was proven
    manually and is recorded with a timestamp in the Phase 7 spec's
    Definition of Done; this automated test proves the same property at
    "fresh compiled graph, shared DB connection" granularity."""
    from sorena.agents import jobscout_graph
    from sorena.tools import jobscout_tool

    monkeypatch.setattr(jobscout_tool, "DB_PATH", tmp_path / "test_jobs.db")
    conn = jobscout_tool._connect()
    conn.execute(
        "INSERT INTO job_postings (dedupe_hash, company, title, description, location, url, score, seen_at) "
        "VALUES ('test-hash-1', 'TestCorp', 'Test Engineer', 'a test posting', 'Remote', "
        "'https://example.com/job', 50, datetime('now'))"
    )
    conn.commit()
    conn.close()

    # Only the route-classification call actually happens in this path --
    # resuming with confirmed=False short-circuits deep_dive_node before it
    # would call router.chat again for the judgment.
    monkeypatch.setattr(jobscout_graph.router, "chat", lambda messages, **kwargs: "deep_dive")

    thread_id = "pg-integration-test"
    app_a = jobscout_graph._build_graph().compile(checkpointer=jobscout_graph._get_checkpointer())
    from sorena.agents.jobscout_graph import JobScoutState

    result = app_a.invoke(
        JobScoutState(user_message="score the TestCorp posting"),
        config={"configurable": {"thread_id": thread_id}},
    )
    assert "__interrupt__" in result

    # A brand-new compiled graph object -- proves nothing in app_a's own
    # memory was needed to resume, only Postgres + the thread_id.
    app_b = jobscout_graph._build_graph().compile(checkpointer=jobscout_graph._get_checkpointer())
    final = app_b.invoke(Command(resume=False), config={"configurable": {"thread_id": thread_id}})
    assert final["reply"] == "Deep-dive cancelled."


@pytest.mark.skipif(not _has_real_api_key(), reason="no LLM provider API key configured")
def test_live_bulk_search_full_turn():
    """The one "live" case the Phase 7 spec calls for: a real bulk-search
    turn through route -> bulk_search -> dedup_against_tracker ->
    vector_rank, exercising real routing judgment and real semantic
    ranking together -- not just each piece in isolation. The tracker is
    mocked to empty so this never depends on (or is thrown off by) Ash's
    real, constantly-changing tracked-applications list."""
    from unittest.mock import patch

    from sorena.agents import jobscout_graph

    with patch.object(jobscout_graph.tracker_tool, "get_tracked_applications", return_value=[]):
        reply = jobscout_graph.run("find me remote AI engineer jobs", thread_id="live-bulk-search-test")

    assert reply  # real Remotive + real routing + real vector_rank all produced *something*
    assert "not implemented" not in reply  # would mean it got misrouted to a stub node
