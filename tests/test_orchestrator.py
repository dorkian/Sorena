from sorena.agents import orchestrator


def test_classify_routes_to_dayplanner(monkeypatch):
    monkeypatch.setattr(orchestrator.router, "chat", lambda messages, tools=None: "dayplanner")
    assert orchestrator._classify("what's my plan today?") == "dayplanner"


def test_classify_routes_to_scribe(monkeypatch):
    monkeypatch.setattr(orchestrator.router, "chat", lambda messages, tools=None: "scribe")
    assert orchestrator._classify("summarize this session") == "scribe"


def test_classify_tolerates_extra_words_around_the_role(monkeypatch):
    monkeypatch.setattr(
        orchestrator.router, "chat", lambda messages, tools=None: "Role: dayplanner."
    )
    assert orchestrator._classify("what's on today?") == "dayplanner"


def test_classify_routes_to_coach(monkeypatch):
    monkeypatch.setattr(orchestrator.router, "chat", lambda messages, tools=None: "coach")
    assert orchestrator._classify("quiz me on today's topic") == "coach"


def test_classify_routes_to_interviewer(monkeypatch):
    monkeypatch.setattr(orchestrator.router, "chat", lambda messages, tools=None: "interviewer")
    assert orchestrator._classify("give me a mock interview") == "interviewer"


def test_classify_routes_to_researcher(monkeypatch):
    monkeypatch.setattr(orchestrator.router, "chat", lambda messages, tools=None: "researcher")
    assert orchestrator._classify("what's new in agent frameworks?") == "researcher"


def test_classify_routes_to_jobscout(monkeypatch):
    monkeypatch.setattr(orchestrator.router, "chat", lambda messages, tools=None: "jobscout")
    assert orchestrator._classify("find me remote AI engineer jobs") == "jobscout"


def test_classify_falls_back_on_unrecognized_response(monkeypatch):
    monkeypatch.setattr(orchestrator.router, "chat", lambda messages, tools=None: "not a real role")
    assert orchestrator._classify("???") in orchestrator.SPECIALISTS


def test_run_delegates_to_classified_specialist_and_logs_event(monkeypatch):
    monkeypatch.setattr(orchestrator, "_classify", lambda msg: "dayplanner")

    captured = {}

    def fake_agent_run(user_message, system_prompt=None, tool_names=None, model_override=None):
        captured["system_prompt"] = system_prompt
        captured["tool_names"] = tool_names
        captured["model_override"] = model_override
        return "your day looks clear"

    monkeypatch.setattr(orchestrator.agent, "run", fake_agent_run)

    logged = {}
    monkeypatch.setattr(
        orchestrator.bus,
        "log_event",
        lambda agent, event_type, payload: logged.update(
            agent=agent, event_type=event_type, payload=payload
        ),
    )
    monkeypatch.setattr(orchestrator.face, "push_state", lambda *a, **kw: None)

    reply = orchestrator.run("what's my plan today?")

    assert reply == "your day looks clear"
    assert captured["system_prompt"] == orchestrator.dayplanner.SYSTEM_PROMPT
    assert captured["tool_names"] == orchestrator.dayplanner.TOOL_NAMES
    assert logged == {
        "agent": "dayplanner",
        "event_type": "handled_message",
        "payload": "your day looks clear",
    }
    assert captured["model_override"] is None


def test_run_passes_model_override_through_to_agent(monkeypatch):
    monkeypatch.setattr(orchestrator, "_classify", lambda msg: "dayplanner")
    monkeypatch.setattr(orchestrator.bus, "log_event", lambda *a, **kw: None)
    monkeypatch.setattr(orchestrator.face, "push_state", lambda *a, **kw: None)

    captured = {}

    def fake_agent_run(user_message, system_prompt=None, tool_names=None, model_override=None):
        captured["model_override"] = model_override
        return "ok"

    monkeypatch.setattr(orchestrator.agent, "run", fake_agent_run)

    orchestrator.run("what's my plan today?", model_override="openrouter/openai/gpt-oss-120b")

    assert captured["model_override"] == "openrouter/openai/gpt-oss-120b"


def test_run_pushes_the_classified_persona_to_the_face(monkeypatch):
    monkeypatch.setattr(orchestrator, "_classify", lambda msg: "scribe")
    monkeypatch.setattr(orchestrator.agent, "run", lambda *a, **kw: "noted")
    monkeypatch.setattr(orchestrator.bus, "log_event", lambda *a, **kw: None)

    pushed = {}
    monkeypatch.setattr(
        orchestrator.face,
        "push_state",
        lambda state, agent=None: pushed.update(state=state, agent=agent),
    )

    orchestrator.run("write a note about this")

    assert pushed["state"] == "speaking"
    assert pushed["agent"]["name"] == "Dabir"
    assert pushed["agent"]["color"] == "#3FA66A"
