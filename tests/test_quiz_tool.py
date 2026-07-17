from datetime import UTC, datetime, timedelta

from sorena.tools import quiz_tool


def test_new_item_is_due_today(tmp_path, monkeypatch):
    monkeypatch.setattr(quiz_tool, "DB_PATH", tmp_path / "test_quiz.db")

    quiz_tool.add_quiz_item("agents", "What is a ReAct loop?", "reason+act interleaved")

    due = quiz_tool.get_due_quiz_items()
    assert "ReAct loop" in due
    assert "reason+act interleaved" in due


def test_wrong_answer_comes_back_in_two_days(tmp_path, monkeypatch):
    monkeypatch.setattr(quiz_tool, "DB_PATH", tmp_path / "test_quiz.db")
    quiz_tool.add_quiz_item("agents", "Q", "A")
    item_id = 1

    result = quiz_tool.record_quiz_result(item_id, correct=False)

    expected_date = (datetime.now(UTC) + timedelta(days=2)).date().isoformat()
    assert expected_date in result
    # not due again today
    assert "No quiz items due" in quiz_tool.get_due_quiz_items()


def test_correct_answer_pushes_review_further_each_time(tmp_path, monkeypatch):
    monkeypatch.setattr(quiz_tool, "DB_PATH", tmp_path / "test_quiz.db")
    quiz_tool.add_quiz_item("agents", "Q", "A")
    item_id = 1

    first = quiz_tool.record_quiz_result(item_id, correct=True)
    assert "2 day(s)" in first  # 2**1

    # force it due again to answer correctly a second time
    conn = quiz_tool._connect()
    conn.execute("UPDATE quiz_items SET next_review = ? WHERE id = ?", ("2000-01-01", item_id))
    conn.commit()
    conn.close()

    second = quiz_tool.record_quiz_result(item_id, correct=True)
    assert "4 day(s)" in second  # 2**2


def test_wrong_answer_resets_review_count(tmp_path, monkeypatch):
    monkeypatch.setattr(quiz_tool, "DB_PATH", tmp_path / "test_quiz.db")
    quiz_tool.add_quiz_item("agents", "Q", "A")
    item_id = 1

    quiz_tool.record_quiz_result(item_id, correct=True)  # review_count -> 1
    result = quiz_tool.record_quiz_result(item_id, correct=False)  # resets to 0

    assert "2 day(s)" in result


def test_record_result_for_unknown_item_id_is_reported_not_raised(tmp_path, monkeypatch):
    monkeypatch.setattr(quiz_tool, "DB_PATH", tmp_path / "test_quiz.db")

    result = quiz_tool.record_quiz_result(999, correct=True)

    assert "No quiz item with id 999" in result


def test_get_due_quiz_items_respects_limit(tmp_path, monkeypatch):
    monkeypatch.setattr(quiz_tool, "DB_PATH", tmp_path / "test_quiz.db")
    for i in range(5):
        quiz_tool.add_quiz_item("agents", f"Q{i}", f"A{i}")

    due = quiz_tool.get_due_quiz_items(limit=2)

    assert due.count("[id=") == 2


def test_record_quiz_result_logs_an_attempt(tmp_path, monkeypatch):
    monkeypatch.setattr(quiz_tool, "DB_PATH", tmp_path / "test_quiz.db")
    quiz_tool.add_quiz_item("agents", "Q", "A")

    quiz_tool.record_quiz_result(1, correct=True)
    quiz_tool.record_quiz_result(1, correct=False)

    attempts = quiz_tool.get_recent_quiz_attempts(days=7)
    assert len(attempts) == 2
    assert attempts[0] == ("agents", True, attempts[0][2])
    assert attempts[1] == ("agents", False, attempts[1][2])


def test_get_recent_quiz_attempts_excludes_older_than_window(tmp_path, monkeypatch):
    monkeypatch.setattr(quiz_tool, "DB_PATH", tmp_path / "test_quiz.db")
    quiz_tool.add_quiz_item("agents", "Q", "A")
    quiz_tool.record_quiz_result(1, correct=True)

    # backdate the only attempt to well outside the 7-day window
    conn = quiz_tool._connect()
    old_timestamp = (datetime.now(UTC) - timedelta(days=30)).isoformat()
    conn.execute("UPDATE quiz_attempts SET attempted_at = ?", (old_timestamp,))
    conn.commit()
    conn.close()

    assert quiz_tool.get_recent_quiz_attempts(days=7) == []


def test_get_recent_quiz_attempts_empty_when_none_logged(tmp_path, monkeypatch):
    monkeypatch.setattr(quiz_tool, "DB_PATH", tmp_path / "test_quiz.db")

    assert quiz_tool.get_recent_quiz_attempts() == []
