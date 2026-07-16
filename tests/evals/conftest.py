"""Clears traces/runs.jsonl once at the start of an eval session, so the
summary script (scripts/eval_summary.py) always reflects the latest full
eval run rather than accumulating across every local test iteration."""

from sorena import trace


def pytest_collection_modifyitems(session, config, items):
    if any("tests/evals" in str(item.fspath).replace("\\", "/") for item in items):
        trace.LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        trace.LOG_PATH.write_text("")
