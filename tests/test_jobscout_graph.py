"""Phase 7: deterministic, mocked tests for jobscout_graph.py -- no real
Postgres/network/LLM calls, so these run in CI's keyless environment (ADR
0010's tier split). Postgres-dependent behavior (semantic_match, the real
interrupt()/PostgresSaver restart-survival proof) is covered separately in
tests/test_jobscout_graph_postgres_integration.py, skipped when Postgres
isn't reachable -- see that file's module docstring and
docs/specs/phase-7-jobscout-graph.md for why CI doesn't provision Postgres
in this phase (a deliberately deferred choice, not an oversight).

Per the "prove both the node AND the dispatch" rule: the *_node tests below
call each node function directly (proving the node's own logic in
isolation); test_route_dispatches_to_correct_node proves separately that
the compiled graph's conditional edge actually reaches that node for a
matching message -- either proof alone could hide a bug the other catches.
"""

from unittest.mock import patch

import pytest
from pydantic import ValidationError

from sorena.agents import jobscout_graph
from sorena.agents.jobscout_graph import (
    JobMatchJudgment,
    JobScoutState,
    _extract_query_term,
    dedup_against_tracker_node,
    route_node,
    skill_gap_node,
    status_update_node,
)


def _mock_router(monkeypatch, reply: str):
    monkeypatch.setattr(jobscout_graph.router, "chat", lambda messages, **kwargs: reply)


@pytest.mark.parametrize(
    "llm_reply,expected_route",
    [
        ("bulk_search", "bulk_search"),
        ("deep_dive", "deep_dive"),
        ("skill_gap", "skill_gap"),
        ("status_update", "status_update"),
    ],
)
def test_route_node_classifies_each_intent(monkeypatch, llm_reply, expected_route):
    _mock_router(monkeypatch, llm_reply)
    result = route_node(JobScoutState(user_message="anything"))
    assert result["route"] == expected_route


def test_route_node_falls_back_to_bulk_search_on_unrecognized_reply(monkeypatch):
    _mock_router(monkeypatch, "I'm not sure what you mean")
    result = route_node(JobScoutState(user_message="anything"))
    assert result["route"] == "bulk_search"


@pytest.mark.parametrize(
    "route",
    ["bulk_search", "deep_dive", "skill_gap", "status_update"],
)
def test_route_dispatches_to_correct_node(monkeypatch, route):
    """The dispatch half of the proof: patches every downstream node to a
    sentinel and confirms the compiled graph actually reaches the one
    matching `route`, not just that route_node's own return value looks
    right in isolation."""
    _mock_router(monkeypatch, route)
    reached = {}

    def _make_sentinel(name):
        def sentinel(state):
            reached[name] = True
            return {"reply": name}

        return sentinel

    for name in ("bulk_search", "deep_dive", "skill_gap", "status_update"):
        monkeypatch.setattr(jobscout_graph, f"{name}_node", _make_sentinel(name))
    # dedup_against_tracker/vector_rank only sit after bulk_search in the
    # real graph; bulk_search_node is patched above so they still run but
    # against whatever (empty) state the patched node returns.
    monkeypatch.setattr(
        jobscout_graph, "dedup_against_tracker_node", lambda state: {"deduped_results": []}
    )
    monkeypatch.setattr(jobscout_graph, "vector_rank_node", lambda state: {"reply": "bulk_search"})

    app = jobscout_graph._build_graph().compile()
    app.invoke(JobScoutState(user_message="anything"))

    assert reached.get(route), f"expected {route}_node to run, only saw {list(reached)}"


def test_extract_query_term_pulls_capitalized_company_name():
    assert _extract_query_term("score the Mitre Media posting") == "Mitre Media"


def test_extract_query_term_falls_back_to_whole_message_if_nothing_capitalized():
    assert _extract_query_term("score that one from earlier") == "score that one from earlier"


def test_dedup_against_tracker_node_filters_already_tracked_job():
    raw = [
        {
            "company": "Bending Spoons",
            "title": "Senior Engineer",
            "score": 80,
            "description": "",
            "location": "",
            "url": "",
        },
        {
            "company": "NewCo",
            "title": "AI Engineer",
            "score": 70,
            "description": "",
            "location": "",
            "url": "",
        },
    ]
    tracked = [{"company": "Bending Spoons", "title": "Senior Engineer"}]

    with patch.object(
        jobscout_graph.tracker_tool, "get_tracked_applications", return_value=tracked
    ):
        result = dedup_against_tracker_node(JobScoutState(user_message="x", raw_results=raw))

    companies = [j["company"] for j in result["deduped_results"]]
    assert companies == ["NewCo"]


def test_dedup_against_tracker_node_keeps_everything_when_tracker_empty():
    raw = [
        {
            "company": "NewCo",
            "title": "AI Engineer",
            "score": 70,
            "description": "",
            "location": "",
            "url": "",
        }
    ]

    with patch.object(jobscout_graph.tracker_tool, "get_tracked_applications", return_value=[]):
        result = dedup_against_tracker_node(JobScoutState(user_message="x", raw_results=raw))

    assert len(result["deduped_results"]) == 1


def test_status_update_node_maps_rejected_and_calls_tracker_correctly():
    apps = [{"job_id": "abc-123", "company": "Bending Spoons", "status": "Applied"}]
    message = "I got rejected by Bending Spoons today"
    with (
        patch.object(jobscout_graph.tracker_tool, "get_tracked_applications", return_value=apps),
        patch.object(
            jobscout_graph.tracker_tool, "update_application_status", return_value=True
        ) as mock_status,
        patch.object(
            jobscout_graph.tracker_tool, "log_application_event", return_value=True
        ) as mock_event,
    ):
        result = status_update_node(JobScoutState(user_message=message))

    assert "Rejected" in result["reply"]
    mock_status.assert_called_once_with("abc-123", "Rejected")
    assert mock_event.call_args[0][0] == "abc-123"
    assert mock_event.call_args[0][1] == "rejected"
    assert mock_event.call_args[0][3] == "fail"


def test_status_update_node_no_matching_application_does_not_call_tracker():
    with (
        patch.object(jobscout_graph.tracker_tool, "get_tracked_applications", return_value=[]),
        patch.object(jobscout_graph.tracker_tool, "update_application_status") as mock_status,
    ):
        message = "I got rejected by Nobody Inc today"
        result = status_update_node(JobScoutState(user_message=message))

    assert "Couldn't find" in result["reply"]
    mock_status.assert_not_called()


def test_status_update_node_unrecognized_outcome_does_not_call_tracker():
    with patch.object(jobscout_graph.tracker_tool, "get_tracked_applications") as mock_get:
        result = status_update_node(JobScoutState(user_message="something happened, not sure what"))

    assert "Couldn't tell" in result["reply"]
    mock_get.assert_not_called()  # never even looks up applications without a recognized outcome


def test_skill_gap_node_reports_without_delegate_keyword():
    with (
        patch.object(
            jobscout_graph.jobscout_tool, "get_skill_gap", return_value="LangGraph is your top gap"
        ) as mock_report,
        patch.object(jobscout_graph.delegation_tool, "notify_coach_of_skill_gap") as mock_delegate,
    ):
        result = skill_gap_node(JobScoutState(user_message="what should I learn next"))

    assert result["reply"] == "LangGraph is your top gap"
    mock_report.assert_called_once()
    mock_delegate.assert_not_called()


def test_skill_gap_node_delegates_with_action_keyword():
    with (
        patch.object(jobscout_graph.jobscout_tool, "get_skill_gap") as mock_report,
        patch.object(
            jobscout_graph.delegation_tool, "notify_coach_of_skill_gap", return_value="scheduled"
        ) as mock_delegate,
    ):
        result = skill_gap_node(JobScoutState(user_message="schedule a lesson on my top gap"))

    assert result["reply"] == "scheduled"
    mock_delegate.assert_called_once()
    mock_report.assert_not_called()


def test_job_match_judgment_rejects_out_of_range_score():
    payload = dict(
        skills_match=45,  # rubric max is 30 -- must be rejected, not silently clamped
        experience_fit=10,
        salary_alignment=10,
        industry_relevance=10,
        location_fit=5,
        growth_potential=5,
        interview_chance="Medium",
        why_match="x",
    )
    with pytest.raises(ValidationError):
        JobMatchJudgment.model_validate(payload)


def test_job_match_judgment_accepts_valid_payload():
    payload = dict(
        skills_match=25,
        experience_fit=15,
        salary_alignment=10,
        industry_relevance=10,
        location_fit=8,
        growth_potential=7,
        interview_chance="High",
        why_match="strong Python/AI overlap",
    )
    judgment = JobMatchJudgment.model_validate(payload)
    assert judgment.skills_match == 25
    assert judgment.missing_skills == ""  # optional field defaults to empty, not required
