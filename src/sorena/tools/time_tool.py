from datetime import UTC, datetime

SCHEMA = {
    "type": "function",
    "function": {
        "name": "get_current_time",
        "description": "Get the current UTC date and time.",
        "parameters": {"type": "object", "properties": {}},
    },
}


def run() -> str:
    return datetime.now(UTC).isoformat()
