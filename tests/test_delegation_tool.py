from sorena import agent
from sorena.agents import coach, researcher
from sorena.tools import delegation_tool, jobscout_tool


def test_ask_researcher_delegates_to_researchers_own_agent_run(monkeypatch):
    captured = {}

    def fake_agent_run(topic, system_prompt=None, tool_names=None):
        captured["topic"] = topic
        captured["system_prompt"] = system_prompt
        captured["tool_names"] = tool_names
        return "5 bullets about the topic"

    monkeypatch.setattr(agent, "run", fake_agent_run)

    result = delegation_tool.ask_researcher("agent frameworks this week")

    assert result == "5 bullets about the topic"
    assert captured["topic"] == "agent frameworks this week"
    assert captured["system_prompt"] == researcher.SYSTEM_PROMPT
    assert captured["tool_names"] == researcher.TOOL_NAMES


def test_notify_coach_of_skill_gap_delegates_when_gap_found(monkeypatch):
    monkeypatch.setattr(jobscout_tool, "find_skill_gap", lambda: ("LangGraph", 7, 12))

    captured = {}

    def fake_agent_run(message, system_prompt=None, tool_names=None):
        captured["message"] = message
        captured["system_prompt"] = system_prompt
        captured["tool_names"] = tool_names
        return "Scheduled a LangGraph lesson."

    monkeypatch.setattr(agent, "run", fake_agent_run)

    result = delegation_tool.notify_coach_of_skill_gap()

    assert result == "Scheduled a LangGraph lesson."
    assert "LangGraph" in captured["message"]
    assert "7" in captured["message"] and "12" in captured["message"]
    assert captured["system_prompt"] == coach.SYSTEM_PROMPT
    assert captured["tool_names"] == coach.TOOL_NAMES


def test_notify_coach_of_skill_gap_skips_delegation_when_no_gap(monkeypatch):
    monkeypatch.setattr(jobscout_tool, "find_skill_gap", lambda: None)

    def fail_agent_run(*a, **kw):
        raise AssertionError("should not delegate when there's no gap to report")

    monkeypatch.setattr(agent, "run", fail_agent_run)

    result = delegation_tool.notify_coach_of_skill_gap()

    assert "No skill gap to report yet" in result
