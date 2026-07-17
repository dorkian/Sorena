"""Interview rubric scoring + history for Interviewer
(docs/specs/sorena-multi-agent-plan.md §3): each answer gets scored 1-5 on
correctness/depth/structure/communication, stored so progress is trackable
over weeks. One SQLite DB, reusing long_term_memory's DB_PATH.
"""

import sqlite3
from datetime import UTC, datetime, timedelta

from sorena.long_term_memory import DB_PATH

_SCHEMA = """
CREATE TABLE IF NOT EXISTS interview_scores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    question TEXT NOT NULL,
    mode TEXT NOT NULL,
    correctness INTEGER NOT NULL,
    depth INTEGER NOT NULL,
    structure INTEGER NOT NULL,
    communication INTEGER NOT NULL,
    average REAL NOT NULL,
    notes TEXT NOT NULL DEFAULT '',
    timestamp TEXT NOT NULL
);
"""


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(_SCHEMA)
    return conn


SAVE_INTERVIEW_SCORE_SCHEMA = {
    "type": "function",
    "function": {
        "name": "save_interview_score",
        "description": (
            "Save a rubric score (1-5 each) for one interview answer, so progress is "
            "trackable over time."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "question": {"type": "string"},
                "mode": {
                    "type": "string",
                    "description": "technical, behavioral, or system_design",
                },
                "correctness": {"type": "integer", "description": "1-5"},
                "depth": {"type": "integer", "description": "1-5"},
                "structure": {"type": "integer", "description": "1-5"},
                "communication": {"type": "integer", "description": "1-5"},
                "notes": {"type": "string", "description": "Brief feedback on the answer."},
            },
            "required": ["question", "mode", "correctness", "depth", "structure", "communication"],
        },
    },
}


def save_interview_score(
    question: str,
    mode: str,
    correctness: int,
    depth: int,
    structure: int,
    communication: int,
    notes: str = "",
) -> str:
    average = (correctness + depth + structure + communication) / 4
    conn = _connect()
    try:
        conn.execute(
            "INSERT INTO interview_scores "
            "(question, mode, correctness, depth, structure, communication, average, notes, "
            "timestamp) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                question,
                mode,
                correctness,
                depth,
                structure,
                communication,
                average,
                notes,
                datetime.now(UTC).isoformat(),
            ),
        )
        conn.commit()
        return f"Saved. Average score: {average:.1f}/5."
    finally:
        conn.close()


GET_INTERVIEW_HISTORY_SCHEMA = {
    "type": "function",
    "function": {
        "name": "get_interview_history",
        "description": "Get recent interview scores to track progress over time.",
        "parameters": {
            "type": "object",
            "properties": {"limit": {"type": "integer", "description": "Max results. Default 10."}},
        },
    },
}


def get_interview_history(limit: int = 10) -> str:
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT timestamp, mode, average, question FROM interview_scores "
            "ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    finally:
        conn.close()

    if not rows:
        return "No interview history yet."
    return "\n".join(f"{r[0]} [{r[1]}] avg={r[2]:.1f} - {r[3][:60]}" for r in rows)


def get_recent_interview_scores(days: int = 7) -> list[tuple[str, float]]:
    """Raw (timestamp, average) rows from the last `days` days, for
    sorena.tools.digest_tool -- same internal-helper convention as
    quiz_tool.get_recent_quiz_attempts."""
    cutoff = (datetime.now(UTC) - timedelta(days=days)).isoformat()
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT timestamp, average FROM interview_scores WHERE timestamp >= ? "
            "ORDER BY timestamp ASC",
            (cutoff,),
        ).fetchall()
    finally:
        conn.close()
    return [(timestamp, average) for timestamp, average in rows]
