"""Runs every case in cases.py through the real agent loop (sorena.agent.run)
and checks it against the resulting trace record in traces/runs.jsonl -- so
this suite also doubles as an integration test of the tracing feature
itself (Phase 6's other deliverable), not just of tool selection.

See cases.py for what a case is and how to add one, and
docs/adr/0010-eval-suite-scripted-plus-live-tiers.md for why the CI-gated
tier scripts the LLM's decisions instead of calling a real model.
"""

import json
import os

import numpy as np
import pytest

from sorena import agent, trace
from sorena.long_term_memory import LongTermMemory
from sorena.memory import ConversationMemory
from sorena.tools import recall_tool
from sorena.tools import registry as tool_registry

from .cases import ALL_CASES
from .harness import scripted_router


class _FakeEmbeddingModel:
    """Deterministic stand-in so eval cases don't download a real
    sentence-transformers model -- recall_memory's own dispatch/fusion logic
    is what's under test here, not embedding quality (that's Phase 5's own
    benchmark, examples/benchmark_memory_recall.py)."""

    def encode(self, text, normalize_embeddings=True):
        return np.zeros(8, dtype=np.float32)


def _has_real_api_key() -> bool:
    return bool(os.getenv("GROQ_API_KEY") or os.getenv("GEMINI_API_KEY"))


def _last_trace_record() -> dict:
    lines = trace.LOG_PATH.read_text().splitlines()
    return json.loads(lines[-1])


def _mark_last_trace(case_name: str, passed: bool) -> None:
    """Marks the current case's own trace record as passed/failed. Only
    mutates the last line if it actually belongs to this case -- if
    agent.run() crashed before logging its own trace (e.g. an exhausted
    provider chain, which happens for real under free-tier rate limits),
    the last line belongs to a different, already-completed case, and
    blindly touching it would corrupt that case's recorded outcome."""
    lines = trace.LOG_PATH.read_text().splitlines()
    if not lines:
        return
    record = json.loads(lines[-1])
    if record.get("eval_case") != case_name:
        return
    record["eval_passed"] = passed
    lines[-1] = json.dumps(record)
    trace.LOG_PATH.write_text("\n".join(lines) + "\n")


@pytest.fixture(autouse=True)
def _isolated_long_term_memory(monkeypatch):
    monkeypatch.setattr("sorena.long_term_memory._get_model", lambda: _FakeEmbeddingModel())
    # recall_memory's own module-level singleton is separate from the
    # `long_term` instance passed to agent.run() -- both must point at the
    # same seeded instance or a case's seed_long_term is invisible to the
    # tool when it actually runs
    monkeypatch.setattr(recall_tool, "_memory", None)


@pytest.mark.parametrize("case", ALL_CASES, ids=lambda c: c.name)
def test_eval_case(case, tmp_path, monkeypatch):
    if case.live and not _has_real_api_key():
        pytest.skip("no LLM provider API key configured -- live eval case skipped")

    long_term = LongTermMemory(tmp_path / "memory.db")
    for role, content, timestamp in case.seed_long_term:
        long_term.add_turn(role, content, timestamp)
    monkeypatch.setattr(recall_tool, "_memory", long_term)

    if not case.live:
        scripted_router(monkeypatch, case.script)

    if case.mock_web_search is not None:
        monkeypatch.setitem(tool_registry.TOOLS, "web_search", lambda query: case.mock_web_search)

    if case.name == "mcp_tool_dispatches_through_same_registry":
        monkeypatch.setattr(tool_registry, "TOOLS", dict(tool_registry.TOOLS))
        tool_registry.register_mcp_tools({"mcp_test_server_ping": lambda: "pong received."}, [])

    memory = ConversationMemory()
    passed = False
    try:
        if case.expect_exception:
            with pytest.raises(case.expect_exception):
                agent.run(
                    case.user_message,
                    memory=memory,
                    long_term=long_term,
                    _eval_case=case.name,
                    _eval_case_type=case.case_type,
                )
            passed = True
            return

        try:
            answer = agent.run(
                case.user_message,
                memory=memory,
                long_term=long_term,
                _eval_case=case.name,
                _eval_case_type=case.case_type,
            )
        except Exception as e:
            # an exception here means agent.run() crashed before logging
            # its own trace record (e.g. router.chat() exhausting the
            # provider chain) -- fail explicitly rather than let it fall
            # through to `finally` silently
            pytest.fail(f"agent.run() raised unexpectedly: {e!r}")

        record = _last_trace_record()
        called_tools = [s["tool"] for s in record["steps"]]

        if case.expect_tool_called:
            expected = (
                [case.expect_tool_called]
                if isinstance(case.expect_tool_called, str)
                else case.expect_tool_called
            )
            for tool_name in expected:
                assert tool_name in called_tools, (
                    f"expected {tool_name!r} to be called, got {called_tools}"
                )

        if case.expect_no_tool_called:
            assert called_tools == [], f"expected no tool call, got {called_tools}"

        if case.expect_answer_contains:
            assert case.expect_answer_contains.lower() in answer.lower(), (
                f"expected answer to contain {case.expect_answer_contains!r}, got: {answer!r}"
            )

        if case.expect_step_result_contains or case.expect_step_succeeds:
            matching = [s for s in record["steps"] if s["tool"] == case.expect_tool_called]
            assert matching, f"no step found for tool {case.expect_tool_called!r}"

        if case.expect_step_result_contains:
            assert case.expect_step_result_contains.lower() in matching[-1]["result"].lower(), (
                f"expected step result to contain {case.expect_step_result_contains!r}, "
                f"got: {matching[-1]['result']!r}"
            )

        if case.expect_step_succeeds:
            # agent.py prefixes every caught tool exception with "Error" --
            # see its `except UnknownToolError` / `except Exception` handlers
            assert not matching[-1]["result"].startswith("Error"), (
                f"expected the tool call to succeed, but it errored: {matching[-1]['result']!r}"
            )

        passed = True
    finally:
        _mark_last_trace(case.name, passed)
