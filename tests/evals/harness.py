"""Shared scripting utilities for eval cases -- lets a case script exactly
what the LLM "decides" at each hop (a tool call, several tool calls in one
response, or a final answer), so the deterministic eval tier tests the
agent loop's orchestration without a real API call. See docs/adr/0010 for
why the CI-gated tier is scripted rather than live, and cases.py for the
live (real-LLM) tier that tests genuine tool-selection judgment."""

from types import SimpleNamespace


class _ScriptedToolCall:
    def __init__(self, call_id: str, name: str, arguments: str):
        self.id = call_id
        self.function = SimpleNamespace(name=name, arguments=arguments)


class _ScriptedResponse:
    def __init__(self, tool_calls: list[_ScriptedToolCall]):
        self.content = None
        self.tool_calls = tool_calls


def tool_call(name: str, arguments: str = "{}", call_id: str = "call_1"):
    """One hop where the (scripted) model decides to call a single tool."""
    return _ScriptedResponse([_ScriptedToolCall(call_id, name, arguments)])


def tool_calls(*specs: tuple[str, str]):
    """One hop where the (scripted) model decides to call several tools at
    once -- specs is a list of (name, arguments) pairs."""
    calls = [_ScriptedToolCall(f"call_{i}", name, args) for i, (name, args) in enumerate(specs)]
    return _ScriptedResponse(calls)


def final(text: str) -> str:
    """One hop where the (scripted) model answers directly -- matches
    router.chat()'s real contract of returning a plain string for a
    tool-free reply."""
    return text


def scripted_router(monkeypatch, script: list) -> None:
    """Monkeypatches router.chat to pop responses off `script` in order, one
    per call. An exhausted script means the case didn't script enough hops
    for what the agent loop actually needed -- a bug in the case, not the
    agent, so it fails loudly rather than silently returning something."""
    from sorena import agent

    remaining = list(script)

    def fake_chat(messages, tools=None, tool_choice=None, model_override=None):
        if not remaining:
            raise AssertionError("eval case script exhausted -- agent asked for another hop")
        return remaining.pop(0)

    monkeypatch.setattr(agent.router, "chat", fake_chat)
