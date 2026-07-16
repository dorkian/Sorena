import json

from sorena import trace


def test_log_run_writes_one_jsonl_record(tmp_path, monkeypatch):
    monkeypatch.setattr(trace, "LOG_PATH", tmp_path / "runs.jsonl")

    record = trace.log_run(
        user_input="what time is it",
        steps=[{"tool": "get_current_time", "args": "{}", "result": "2026-01-01T00:00:00"}],
        final_answer="It is midnight.",
        tokens_total=42,
        latency_ms=123.456,
        hops=1,
    )

    lines = trace.LOG_PATH.read_text().splitlines()
    assert len(lines) == 1
    written = json.loads(lines[0])
    assert written["input"] == "what time is it"
    assert written["hops"] == 1
    assert written["latency_ms"] == 123.5
    assert written["eval_case"] is None
    assert record == written


def test_log_run_appends_across_multiple_runs(tmp_path, monkeypatch):
    monkeypatch.setattr(trace, "LOG_PATH", tmp_path / "runs.jsonl")

    trace.log_run(
        user_input="a", steps=[], final_answer="1", tokens_total=1, latency_ms=1.0, hops=1
    )
    trace.log_run(
        user_input="b", steps=[], final_answer="2", tokens_total=1, latency_ms=1.0, hops=1
    )

    assert len(trace.LOG_PATH.read_text().splitlines()) == 2


def test_log_run_records_eval_metadata(tmp_path, monkeypatch):
    monkeypatch.setattr(trace, "LOG_PATH", tmp_path / "runs.jsonl")

    record = trace.log_run(
        user_input="a",
        steps=[],
        final_answer="1",
        tokens_total=1,
        latency_ms=1.0,
        hops=1,
        eval_case="time_question_calls_time_tool",
        eval_case_type="tool_selection",
        eval_passed=True,
    )

    assert record["eval_case"] == "time_question_calls_time_tool"
    assert record["eval_case_type"] == "tool_selection"
    assert record["eval_passed"] is True
