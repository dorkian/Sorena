"""Shared event bus: specialists write what they did, the Orchestrator reads
recent events for cross-agent context without agents talking to each other
directly (docs/specs/sorena-multi-agent-plan.md §1, "Shared memory bus").
One SQLite DB, not a new file -- reuses long_term_memory's DB_PATH.
"""

import sqlite3
from datetime import UTC, datetime

from sorena.long_term_memory import DB_PATH

_SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent TEXT NOT NULL,
    event_type TEXT NOT NULL,
    payload TEXT NOT NULL,
    timestamp TEXT NOT NULL
);
"""


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(_SCHEMA)
    return conn


def log_event(agent: str, event_type: str, payload: str) -> None:
    conn = _connect()
    try:
        conn.execute(
            "INSERT INTO events (agent, event_type, payload, timestamp) VALUES (?, ?, ?, ?)",
            (agent, event_type, payload, datetime.now(UTC).isoformat()),
        )
        conn.commit()
    finally:
        conn.close()


def recent_events(limit: int = 10) -> list[dict]:
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT agent, event_type, payload, timestamp FROM events ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    finally:
        conn.close()
    return [{"agent": r[0], "event_type": r[1], "payload": r[2], "timestamp": r[3]} for r in rows]
