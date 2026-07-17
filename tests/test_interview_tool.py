from datetime import UTC, datetime, timedelta

from sorena.tools import interview_tool


def test_save_interview_score_computes_average(tmp_path, monkeypatch):
    monkeypatch.setattr(interview_tool, "DB_PATH", tmp_path / "test_interview.db")

    result = interview_tool.save_interview_score(
        question="Explain the ReAct pattern.",
        mode="technical",
        correctness=4,
        depth=3,
        structure=5,
        communication=4,
        notes="Solid, a bit rushed on depth.",
    )

    assert "4.0/5" in result


def test_get_interview_history_returns_most_recent_first(tmp_path, monkeypatch):
    monkeypatch.setattr(interview_tool, "DB_PATH", tmp_path / "test_interview.db")

    interview_tool.save_interview_score("Q1", "technical", 3, 3, 3, 3)
    interview_tool.save_interview_score("Q2", "behavioral", 5, 5, 5, 5)

    history = interview_tool.get_interview_history()

    lines = history.splitlines()
    assert "Q2" in lines[0]
    assert "avg=5.0" in lines[0]
    assert "Q1" in lines[1]


def test_get_interview_history_respects_limit(tmp_path, monkeypatch):
    monkeypatch.setattr(interview_tool, "DB_PATH", tmp_path / "test_interview.db")
    for i in range(5):
        interview_tool.save_interview_score(f"Q{i}", "technical", 3, 3, 3, 3)

    history = interview_tool.get_interview_history(limit=2)

    assert len(history.splitlines()) == 2


def test_get_interview_history_empty_db(tmp_path, monkeypatch):
    monkeypatch.setattr(interview_tool, "DB_PATH", tmp_path / "test_interview.db")

    assert interview_tool.get_interview_history() == "No interview history yet."


def test_get_recent_interview_scores_within_window(tmp_path, monkeypatch):
    monkeypatch.setattr(interview_tool, "DB_PATH", tmp_path / "test_interview.db")
    interview_tool.save_interview_score("Q1", "technical", 4, 4, 4, 4)  # avg 4.0

    scores = interview_tool.get_recent_interview_scores(days=7)

    assert len(scores) == 1
    assert scores[0][1] == 4.0


def test_get_recent_interview_scores_excludes_older_than_window(tmp_path, monkeypatch):
    monkeypatch.setattr(interview_tool, "DB_PATH", tmp_path / "test_interview.db")
    interview_tool.save_interview_score("Q1", "technical", 3, 3, 3, 3)

    conn = interview_tool._connect()
    old_timestamp = (datetime.now(UTC) - timedelta(days=30)).isoformat()
    conn.execute("UPDATE interview_scores SET timestamp = ?", (old_timestamp,))
    conn.commit()
    conn.close()

    assert interview_tool.get_recent_interview_scores(days=7) == []


def test_get_recent_interview_scores_empty_when_none_saved(tmp_path, monkeypatch):
    monkeypatch.setattr(interview_tool, "DB_PATH", tmp_path / "test_interview.db")

    assert interview_tool.get_recent_interview_scores() == []
