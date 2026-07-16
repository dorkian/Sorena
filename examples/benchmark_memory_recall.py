"""Phase 5 recall benchmark: seeds a small conversation history, then checks
that hybrid (keyword + vector) search returns the right past turn for a set
of realistic queries -- and reports whether hybrid beats vector-only search
on any of them. Uses the real sentence-transformers model (downloads once,
cached after that).

Run: uv run python examples/benchmark_memory_recall.py
"""

import tempfile
import time
from pathlib import Path

from sorena.long_term_memory import LongTermMemory

TURNS = [
    (
        "user",
        "I need to renew my passport before my trip to Japan in September.",
        "2026-06-20T09:00:00",
    ),
    (
        "user",
        "What's the best way to convert a pandas DataFrame to a numpy array?",
        "2026-06-21T14:00:00",
    ),
    (
        "user",
        "Docker build is failing with exit code 137, probably OOM killed.",
        "2026-06-22T11:30:00",
    ),
    (
        "user",
        "Docker build is failing with exit code 1 because of a Dockerfile syntax error.",
        "2026-06-22T11:45:00",
    ),
    ("user", "PIN for the storage locker is 7734.", "2026-06-22T18:00:00"),
    ("user", "PIN for the bike lock is 4821.", "2026-06-22T18:05:00"),
    ("user", "My dentist appointment is next Tuesday at 3pm.", "2026-06-23T08:00:00"),
    (
        "user",
        "Can you explain how reciprocal rank fusion works for combining search results?",
        "2026-06-24T16:00:00",
    ),
    (
        "user",
        "I'm thinking about switching from Poetry to uv for Python packaging.",
        "2026-06-25T10:00:00",
    ),
    (
        "user",
        "The wake word threshold that worked on my hardware was 0.3, not the default 0.5.",
        "2026-06-26T13:00:00",
    ),
    (
        "user",
        "What's a good local embedding model that doesn't need a paid API?",
        "2026-06-27T15:00:00",
    ),
    (
        "user",
        "I want to set a reminder to renew my car insurance next month.",
        "2026-06-28T09:30:00",
    ),
    (
        "user",
        "Silero VAD ships a real Windows wheel, unlike webrtcvad which needs a C compiler.",
        "2026-06-29T12:00:00",
    ),
]

QUERIES = [
    ("what did I say about my Japan trip", "passport"),
    ("how do I turn a dataframe into a numpy array", "pandas DataFrame"),
    ("137", "Docker build"),
    ("when is my dentist appointment", "dentist"),
    ("what search fusion technique did we discuss", "reciprocal rank fusion"),
    ("uv vs poetry", "Poetry to uv"),
    ("what wake word threshold worked", "0.3"),
    ("free local embedding model", "embedding model"),
    ("car insurance reminder", "car insurance"),
    ("does silero vad need a windows build step", "Silero VAD"),
]


def _content_for(memory: LongTermMemory, turn_id: int) -> str:
    row = memory.conn.execute("SELECT content FROM turns WHERE id = ?", (turn_id,)).fetchone()
    return row[0] if row else ""


def main() -> None:
    db_path = Path(tempfile.mkdtemp()) / "benchmark.db"
    memory = LongTermMemory(db_path)
    for role, content, ts in TURNS:
        memory.add_turn(role, content, ts)

    hybrid_hits = 0
    vector_only_hits = 0
    latencies_ms = []

    for query, expected_substring in QUERIES:
        start = time.perf_counter()
        hybrid_results = memory.search(query, top_k=1)
        latencies_ms.append((time.perf_counter() - start) * 1000)

        vector_only_ids = memory._vector_search(query, top_k=1)
        vector_only_content = _content_for(memory, vector_only_ids[0]) if vector_only_ids else ""

        hybrid_content = hybrid_results[0]["content"] if hybrid_results else ""
        hybrid_ok = expected_substring.lower() in hybrid_content.lower()
        vector_only_ok = expected_substring.lower() in vector_only_content.lower()

        hybrid_hits += hybrid_ok
        vector_only_hits += vector_only_ok

        marker = "OK  " if hybrid_ok else "MISS"
        note = (
            " <- hybrid caught what vector-only missed" if hybrid_ok and not vector_only_ok else ""
        )
        print(f"[{marker}] '{query}' -> {hybrid_content[:65]}{note}")

    print()
    print(f"hybrid:      {hybrid_hits}/{len(QUERIES)} correct")
    print(f"vector-only: {vector_only_hits}/{len(QUERIES)} correct")
    print(f"avg recall latency: {sum(latencies_ms) / len(latencies_ms):.1f} ms")

    memory.close()


if __name__ == "__main__":
    main()
