import json
import time
from pathlib import Path

LOG_PATH = Path("traces/telemetry.jsonl")


def log_call(
    *,
    provider: str,
    model: str,
    tokens_in: int,
    tokens_out: int,
    latency_ms: float,
    cost: float,
) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "timestamp": time.time(),
        "provider": provider,
        "model": model,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "latency_ms": round(latency_ms, 1),
        "cost": cost,
    }
    with LOG_PATH.open("a") as f:
        f.write(json.dumps(record) + "\n")
