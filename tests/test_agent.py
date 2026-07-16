import numpy as np
import pytest

from sorena import agent
from sorena.long_term_memory import LongTermMemory


class FakeEmbeddingModel:
    """Deterministic stand-in so agent tests don't download a real
    sentence-transformers model or touch the real long-term memory DB."""

    def encode(self, text, normalize_embeddings=True):
        return np.zeros(8, dtype=np.float32)


@pytest.fixture(autouse=True)
def _fake_long_term_memory(tmp_path, monkeypatch):
    monkeypatch.setattr("sorena.long_term_memory._get_model", lambda: FakeEmbeddingModel())
    monkeypatch.setattr(agent, "LongTermMemory", lambda: LongTermMemory(tmp_path / "memory.db"))


class FakeToolCallFunction:
    name = "get_current_time"
    arguments = "{}"


class FakeToolCall:
    id = "call_1"
    function = FakeToolCallFunction()


class FakeToolCallResponse:
    content = None
    tool_calls = [FakeToolCall()]


def test_max_hops_guard_stops_infinite_loop(monkeypatch):
    monkeypatch.setattr(agent.router, "chat", lambda messages, tools=None: FakeToolCallResponse())

    with pytest.raises(agent.MaxHopsExceededError):
        agent.run("loop forever")


def test_run_returns_direct_string_answer(monkeypatch):
    monkeypatch.setattr(
        agent.router, "chat", lambda messages, tools=None: "direct answer, no tool needed"
    )

    result = agent.run("hello")

    assert result == "direct answer, no tool needed"


def test_unknown_tool_call_is_fed_back_as_error_not_raised(monkeypatch):
    class BadToolCallFunction:
        name = "not_a_real_tool"
        arguments = None

    class BadToolCall:
        id = "call_2"
        function = BadToolCallFunction()

    class BadToolCallResponse:
        content = None
        tool_calls = [BadToolCall()]

    calls = {"count": 0}

    def fake_chat(messages, tools=None):
        calls["count"] += 1
        if calls["count"] == 1:
            return BadToolCallResponse()
        assert messages[-1]["role"] == "tool"
        assert "Unknown tool" in messages[-1]["content"]
        return "handled gracefully"

    monkeypatch.setattr(agent.router, "chat", fake_chat)

    result = agent.run("call a fake tool")

    assert result == "handled gracefully"


def test_malformed_tool_arguments_are_fed_back_as_error_not_raised(monkeypatch):
    class MalformedArgsFunction:
        name = "get_current_time"
        arguments = "{not valid json"

    class MalformedArgsToolCall:
        id = "call_3"
        function = MalformedArgsFunction()

    class MalformedArgsResponse:
        content = None
        tool_calls = [MalformedArgsToolCall()]

    calls = {"count": 0}

    def fake_chat(messages, tools=None):
        calls["count"] += 1
        if calls["count"] == 1:
            return MalformedArgsResponse()
        assert messages[-1]["role"] == "tool"
        assert "Could not parse arguments" in messages[-1]["content"]
        return "handled gracefully"

    monkeypatch.setattr(agent.router, "chat", fake_chat)

    result = agent.run("call a tool with garbage args")

    assert result == "handled gracefully"
