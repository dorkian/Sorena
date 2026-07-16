"""Long-term memory: persists conversation turns across sessions (unlike
`memory.ConversationMemory`, which only holds the current session and
eventually summarizes old turns away) and recalls them by hybrid search.

Chunking: one turn = one chunk, no sub-splitting — see docs/adr/0008.
"""

import re
import sqlite3
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer

DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "memory.db"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
RRF_K = 60  # standard reciprocal-rank-fusion damping constant

_SCHEMA = """
CREATE TABLE IF NOT EXISTS turns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    embedding BLOB NOT NULL
);
CREATE VIRTUAL TABLE IF NOT EXISTS turns_fts USING fts5(
    content, content='turns', content_rowid='id'
);
CREATE TRIGGER IF NOT EXISTS turns_ai AFTER INSERT ON turns BEGIN
    INSERT INTO turns_fts(rowid, content) VALUES (new.id, new.content);
END;
"""

_model: SentenceTransformer | None = None


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer(EMBEDDING_MODEL)
    return _model


def _fts_query(text: str) -> str:
    """Quote each token as its own OR'd phrase so free-form text can't trip
    FTS5's query-syntax parser (bare `?`, `-`, `"` etc. are otherwise a
    MATCH syntax error, not just a non-match)."""
    tokens = re.findall(r"\w+", text)
    if not tokens:
        return '""'
    return " OR ".join(f'"{t}"' for t in tokens)


class LongTermMemory:
    """SQLite-backed store of conversation turns with hybrid (FTS5 keyword +
    embedding cosine similarity) recall, fused via reciprocal rank fusion."""

    def __init__(self, db_path: Path | str = DB_PATH):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.executescript(_SCHEMA)
        self.conn.commit()

    def add_turn(self, role: str, content: str, timestamp: str) -> None:
        if not content.strip():
            return
        embedding = _get_model().encode(content, normalize_embeddings=True)
        self.conn.execute(
            "INSERT INTO turns (role, content, timestamp, embedding) VALUES (?, ?, ?, ?)",
            (role, content, timestamp, embedding.astype(np.float32).tobytes()),
        )
        self.conn.commit()

    def _vector_search(self, query: str, top_k: int) -> list[int]:
        # ponytail: linear scan over every stored embedding. Fine at
        # personal-assistant scale (thousands of turns); upgrade to an ANN
        # index (e.g. sqlite-vec) if recall latency stops being fine.
        rows = self.conn.execute("SELECT id, embedding FROM turns").fetchall()
        if not rows:
            return []
        query_embedding = _get_model().encode(query, normalize_embeddings=True)
        ids = np.array([r[0] for r in rows])
        matrix = np.stack([np.frombuffer(r[1], dtype=np.float32) for r in rows])
        scores = matrix @ query_embedding  # both sides pre-normalized -> cosine similarity
        order = np.argsort(-scores)[:top_k]
        return [int(ids[i]) for i in order]

    def _keyword_search(self, query: str, top_k: int) -> list[int]:
        rows = self.conn.execute(
            "SELECT rowid FROM turns_fts WHERE turns_fts MATCH ? ORDER BY bm25(turns_fts) LIMIT ?",
            (_fts_query(query), top_k),
        ).fetchall()
        return [row[0] for row in rows]

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        """Hybrid recall: vector similarity finds paraphrases/semantic
        matches, FTS5 keyword search catches exact terms embeddings blur
        past (e.g. an exact product name or short code). Reciprocal rank
        fusion combines the two ranked lists without needing to calibrate
        BM25 scores against cosine scores directly."""
        # Candidate pool per branch must be deep enough that a turn ranked
        # low by one side (but rank-1 on the other) still gets pulled in --
        # top_k*2 was too shallow: a turn keyword search nailed at rank 0
        # lost a tie to a turn vector search ranked 0 but keyword ranked N/A,
        # simply because it never entered vector's shortlist.
        candidate_pool = max(top_k * 4, 20)
        vector_hits = self._vector_search(query, candidate_pool)
        keyword_hits = self._keyword_search(query, candidate_pool)

        fused: dict[int, float] = {}
        for rank, turn_id in enumerate(vector_hits):
            fused[turn_id] = fused.get(turn_id, 0.0) + 1 / (RRF_K + rank + 1)
        for rank, turn_id in enumerate(keyword_hits):
            fused[turn_id] = fused.get(turn_id, 0.0) + 1 / (RRF_K + rank + 1)

        top_ids = sorted(fused, key=lambda i: fused[i], reverse=True)[:top_k]
        if not top_ids:
            return []
        placeholders = ",".join("?" * len(top_ids))
        rows = self.conn.execute(
            f"SELECT id, role, content, timestamp FROM turns WHERE id IN ({placeholders})",
            top_ids,
        ).fetchall()
        by_id = {r[0]: r for r in rows}
        return [
            {"role": by_id[i][1], "content": by_id[i][2], "timestamp": by_id[i][3]}
            for i in top_ids
            if i in by_id
        ]

    def close(self) -> None:
        self.conn.close()
