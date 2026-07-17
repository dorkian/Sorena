"""Quiz item storage + a simple spaced-repetition scheduler for Coach
(docs/specs/sorena-multi-agent-plan.md §2): wrong answers come back in 2
days, correct answers push the next review further out each time. One
SQLite DB, reusing long_term_memory's DB_PATH -- same convention as
sorena.agents.bus.
"""

import sqlite3
from datetime import UTC, datetime, timedelta

from sorena.long_term_memory import DB_PATH

WRONG_INTERVAL_DAYS = 2
# ponytail: doubling backoff capped at 30 days -- swap for a real SM-2
# algorithm if recall-quality data ever justifies the complexity.
MAX_CORRECT_INTERVAL_DAYS = 30

_SCHEMA = """
CREATE TABLE IF NOT EXISTS quiz_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic TEXT NOT NULL,
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    review_count INTEGER NOT NULL DEFAULT 0,
    next_review TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS quiz_attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id INTEGER NOT NULL,
    topic TEXT NOT NULL,
    correct INTEGER NOT NULL,
    attempted_at TEXT NOT NULL
);
"""


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(_SCHEMA)
    return conn


def _today() -> str:
    return datetime.now(UTC).date().isoformat()


ADD_QUIZ_ITEM_SCHEMA = {
    "type": "function",
    "function": {
        "name": "add_quiz_item",
        "description": (
            "Save a new quiz question for spaced-repetition review. It's due immediately (today)."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "topic": {"type": "string", "description": "Learning topic this question covers."},
                "question": {"type": "string"},
                "answer": {"type": "string", "description": "The correct answer, for grading."},
            },
            "required": ["topic", "question", "answer"],
        },
    },
}


def add_quiz_item(topic: str, question: str, answer: str) -> str:
    conn = _connect()
    try:
        cur = conn.execute(
            "INSERT INTO quiz_items (topic, question, answer, next_review, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (topic, question, answer, _today(), datetime.now(UTC).isoformat()),
        )
        conn.commit()
        return f"Saved quiz item id={cur.lastrowid}, due today."
    finally:
        conn.close()


GET_DUE_QUIZ_ITEMS_SCHEMA = {
    "type": "function",
    "function": {
        "name": "get_due_quiz_items",
        "description": (
            "Get quiz questions due for review today (new ones plus any spaced-repetition "
            "repeats). Includes the answer for grading -- ask the question first, don't "
            "reveal the answer to the user before they respond."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Max items to return. Default 3."},
            },
        },
    },
}


def get_due_quiz_items(limit: int = 3) -> str:
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT id, topic, question, answer FROM quiz_items "
            "WHERE next_review <= ? ORDER BY next_review ASC LIMIT ?",
            (_today(), limit),
        ).fetchall()
    finally:
        conn.close()

    if not rows:
        return "No quiz items due for review."
    return "\n".join(f"[id={r[0]}] topic={r[1]} question={r[2]} answer={r[3]}" for r in rows)


RECORD_QUIZ_RESULT_SCHEMA = {
    "type": "function",
    "function": {
        "name": "record_quiz_result",
        "description": (
            "Record whether the user answered a quiz item correctly. Schedules its next "
            "review: 2 days if wrong, further out each time if right."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "item_id": {"type": "integer"},
                "correct": {"type": "boolean"},
            },
            "required": ["item_id", "correct"],
        },
    },
}


def record_quiz_result(item_id: int, correct: bool) -> str:
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT topic, review_count FROM quiz_items WHERE id = ?", (item_id,)
        ).fetchone()
        if row is None:
            return f"No quiz item with id {item_id}."
        topic, current_review_count = row

        if correct:
            review_count = current_review_count + 1
            interval_days = min(2**review_count, MAX_CORRECT_INTERVAL_DAYS)
        else:
            review_count = 0
            interval_days = WRONG_INTERVAL_DAYS

        next_review = (datetime.now(UTC) + timedelta(days=interval_days)).date().isoformat()
        conn.execute(
            "UPDATE quiz_items SET review_count = ?, next_review = ? WHERE id = ?",
            (review_count, next_review, item_id),
        )
        # Scheduling state (above) only tracks what's due next -- it can't
        # answer "how did this week go," since a wrong answer resets
        # review_count rather than preserving history. This log is what
        # the weekly digest (docs/specs/sorena-multi-agent-plan.md §5 step
        # 8) actually reads for a real accuracy trend.
        conn.execute(
            "INSERT INTO quiz_attempts (item_id, topic, correct, attempted_at) VALUES (?, ?, ?, ?)",
            (item_id, topic, int(correct), datetime.now(UTC).isoformat()),
        )
        conn.commit()
        return f"Recorded. Next review in {interval_days} day(s) ({next_review})."
    finally:
        conn.close()


def get_recent_quiz_attempts(days: int = 7) -> list[tuple[str, bool, str]]:
    """Raw (topic, correct, attempted_at) rows from the last `days` days,
    for sorena.tools.digest_tool to aggregate -- kept dumb on purpose, this
    module owns the data, digest_tool owns the aggregation/formatting."""
    cutoff = (datetime.now(UTC) - timedelta(days=days)).isoformat()
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT topic, correct, attempted_at FROM quiz_attempts WHERE attempted_at >= ? "
            "ORDER BY attempted_at ASC",
            (cutoff,),
        ).fetchall()
    finally:
        conn.close()
    return [(topic, bool(correct), attempted_at) for topic, correct, attempted_at in rows]
