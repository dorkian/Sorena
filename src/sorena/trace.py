"""Per-agent-run trace logging. `telemetry.py` already logs one JSONL record
per *LLM call* (provider, tokens, latency) to `traces/`; this logs one JSONL
record per *agent.run() call* -- the whole hop sequence -- to the same
`traces/` directory, reusing that pattern rather than inventing a second
logging mechanism."""

import json
import time
import uuid
from pathlib import Path

LOG_PATH = Path("traces/runs.jsonl")


def log_run(
    *,
    user_input: str,
    steps: list[dict],
    final_answer: str | None,
    tokens_total: int,
    latency_ms: float,
    hops: int,
    eval_case: str | None = None,
    eval_case_type: str | None = None,
    eval_passed: bool | None = None,
) -> dict:
    """Writes one trace record and returns it. `eval_*` fields are set only
    when the run was triggered by the eval suite (see tests/evals/) -- the
    summary script uses them to compute pass rate and tool-selection
    accuracy without needing a separate results file."""
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "run_id": str(uuid.uuid4()),
        "timestamp": time.time(),
        "input": user_input,
        "steps": steps,
        "final_answer": final_answer,
        "tokens_total": tokens_total,
        "latency_ms": round(latency_ms, 1),
        "hops": hops,
        "eval_case": eval_case,
        "eval_case_type": eval_case_type,
        "eval_passed": eval_passed,
    }
    with LOG_PATH.open("a") as f:
        f.write(json.dumps(record) + "\n")
    return record
