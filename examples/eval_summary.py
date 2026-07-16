"""Reads traces/runs.jsonl and reports eval pass rate, tool-selection
accuracy, and latency percentiles. A dashboard is explicitly out of scope
per the spec -- this printed report is the deliverable.

Run `uv run pytest tests/evals/` first to populate eval-tagged trace data,
then:

Run: uv run python examples/eval_summary.py
"""

import json
from pathlib import Path

TRACE_PATH = Path("traces/runs.jsonl")


def _percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    k = (len(s) - 1) * p
    lo, hi = int(k), min(int(k) + 1, len(s) - 1)
    if lo == hi:
        return s[lo]
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def main() -> None:
    if not TRACE_PATH.exists():
        print(f"No trace file at {TRACE_PATH} -- run the app or `pytest tests/evals/` first.")
        return

    records = [json.loads(line) for line in TRACE_PATH.read_text().splitlines() if line.strip()]
    if not records:
        print("Trace file is empty.")
        return

    latencies = [r["latency_ms"] for r in records]
    print(f"=== traces/runs.jsonl summary ({len(records)} runs) ===\n")
    print(
        f"Latency: p50={_percentile(latencies, 0.5):.0f}ms  "
        f"p95={_percentile(latencies, 0.95):.0f}ms  max={max(latencies):.0f}ms"
    )
    print()

    eval_records = [r for r in records if r["eval_case"]]
    if not eval_records:
        print("No eval-tagged runs found. Run `pytest tests/evals/` to populate eval data.")
        return

    passed = sum(1 for r in eval_records if r["eval_passed"])
    total = len(eval_records)
    print(f"Eval pass rate: {passed}/{total} ({passed / total:.0%})")

    tool_selection = [r for r in eval_records if r["eval_case_type"] == "tool_selection"]
    if tool_selection:
        ts_passed = sum(1 for r in tool_selection if r["eval_passed"])
        print(
            f"Tool-selection accuracy (live cases): {ts_passed}/{len(tool_selection)} "
            f"({ts_passed / len(tool_selection):.0%})"
        )

    failed = [r for r in eval_records if not r["eval_passed"]]
    if failed:
        print("\nFailing cases:")
        for r in failed:
            print(f"  - {r['eval_case']} ({r['eval_case_type']})")


if __name__ == "__main__":
    main()
