from sorena.tools import digest_tool


def test_weekly_digest_reports_no_activity_when_everything_empty(monkeypatch):
    monkeypatch.setattr(digest_tool.quiz_tool, "get_recent_quiz_attempts", lambda days: [])
    monkeypatch.setattr(digest_tool.interview_tool, "get_recent_interview_scores", lambda days: [])
    monkeypatch.setattr(digest_tool.jobscout_tool, "get_recent_job_match_scores", lambda days: [])

    result = digest_tool.weekly_digest()

    assert "no attempts this week" in result
    assert "no sessions this week" in result
    assert "no deep-dive scores this week" in result


def test_weekly_digest_quiz_section_computes_accuracy_and_topics(monkeypatch):
    monkeypatch.setattr(
        digest_tool.quiz_tool,
        "get_recent_quiz_attempts",
        lambda days: [
            ("agents", True, "t1"),
            ("agents", False, "t2"),
            ("rag", True, "t3"),
        ],
    )
    monkeypatch.setattr(digest_tool.interview_tool, "get_recent_interview_scores", lambda days: [])
    monkeypatch.setattr(digest_tool.jobscout_tool, "get_recent_job_match_scores", lambda days: [])

    result = digest_tool.weekly_digest()

    assert "2/3 correct (67%)" in result
    assert "agents" in result
    assert "rag" in result


def test_weekly_digest_interview_section_reports_improving_trend(monkeypatch):
    monkeypatch.setattr(digest_tool.quiz_tool, "get_recent_quiz_attempts", lambda days: [])
    monkeypatch.setattr(
        digest_tool.interview_tool,
        "get_recent_interview_scores",
        lambda days: [("t1", 2.0), ("t2", 2.0), ("t3", 4.5), ("t4", 4.5)],
    )
    monkeypatch.setattr(digest_tool.jobscout_tool, "get_recent_job_match_scores", lambda days: [])

    result = digest_tool.weekly_digest()

    assert "4 session(s)" in result
    assert "(improving)" in result


def test_weekly_digest_interview_section_reports_steady_with_one_session(monkeypatch):
    monkeypatch.setattr(digest_tool.quiz_tool, "get_recent_quiz_attempts", lambda days: [])
    monkeypatch.setattr(
        digest_tool.interview_tool, "get_recent_interview_scores", lambda days: [("t1", 3.5)]
    )
    monkeypatch.setattr(digest_tool.jobscout_tool, "get_recent_job_match_scores", lambda days: [])

    result = digest_tool.weekly_digest()

    assert "1 session(s), avg 3.5/5." in result
    assert "improving" not in result
    assert "declining" not in result


def test_weekly_digest_job_match_section_reports_grade_distribution(monkeypatch):
    monkeypatch.setattr(digest_tool.quiz_tool, "get_recent_quiz_attempts", lambda days: [])
    monkeypatch.setattr(digest_tool.interview_tool, "get_recent_interview_scores", lambda days: [])
    monkeypatch.setattr(
        digest_tool.jobscout_tool,
        "get_recent_job_match_scores",
        lambda days: [("t1", "A"), ("t2", "A"), ("t3", "B")],
    )

    result = digest_tool.weekly_digest()

    assert "3 posting(s) scored" in result
    assert "2 A" in result
    assert "1 B" in result
