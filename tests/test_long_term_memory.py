import numpy as np
import pytest

from sorena.long_term_memory import LongTermMemory


class ScriptedEmbeddingModel:
    """Maps known text to hand-picked vectors so a test can deterministically
    control what vector-only search would rank first, without a real model."""

    def __init__(self, vectors: dict[str, list[float]]):
        self.vectors = vectors

    def encode(self, text, normalize_embeddings=True):
        vec = np.array(self.vectors.get(text, [0.0, 0.0]), dtype=np.float32)
        norm = np.linalg.norm(vec)
        return vec / norm if norm else vec


@pytest.fixture
def memory(tmp_path):
    mem = LongTermMemory(tmp_path / "test.db")
    yield mem
    mem.close()


def _patch_model(monkeypatch, vectors):
    monkeypatch.setattr(
        "sorena.long_term_memory._get_model", lambda: ScriptedEmbeddingModel(vectors)
    )


def test_add_and_recall_round_trip(memory, monkeypatch):
    _patch_model(
        monkeypatch,
        {
            "The capital of France is Paris.": [1.0, 0.0],
            "capital of France": [1.0, 0.0],
        },
    )
    memory.add_turn("assistant", "The capital of France is Paris.", "2026-07-01T00:00:00")

    results = memory.search("capital of France")

    assert results[0]["content"] == "The capital of France is Paris."


def test_hybrid_search_finds_exact_term_vector_search_misses(memory, monkeypatch):
    # The query's scripted embedding points at the *wrong* turn -- standing in
    # for a real failure mode: a rare exact token (an error code, a product
    # name) that doesn't move a real embedding enough to win on cosine
    # similarity alone. Only the keyword layer can rescue the right turn here.
    _patch_model(
        monkeypatch,
        {
            "Docker build is failing with exit code 137.": [0.0, 1.0],
            "I need to renew my passport before the trip.": [1.0, 0.0],
            "exit code 137": [1.0, 0.0],
        },
    )
    memory.add_turn("user", "Docker build is failing with exit code 137.", "t1")
    memory.add_turn("user", "I need to renew my passport before the trip.", "t2")

    vector_only_top_id = memory._vector_search("exit code 137", top_k=1)[0]
    vector_only_top_content = memory.conn.execute(
        "SELECT content FROM turns WHERE id = ?", (vector_only_top_id,)
    ).fetchone()[0]
    # sanity check: confirm the scripted setup actually reproduces the failure
    # mode being tested (vector-only search picks the wrong turn)
    assert vector_only_top_content == "I need to renew my passport before the trip."

    hybrid_results = memory.search("exit code 137", top_k=1)
    assert hybrid_results[0]["content"] == "Docker build is failing with exit code 137."


def test_search_on_empty_store_returns_no_results(memory, monkeypatch):
    _patch_model(monkeypatch, {})
    assert memory.search("anything") == []


def test_add_turn_ignores_blank_content(memory, monkeypatch):
    _patch_model(monkeypatch, {})
    memory.add_turn("user", "   ", "t1")
    assert memory.conn.execute("SELECT COUNT(*) FROM turns").fetchone()[0] == 0


def test_search_handles_punctuation_without_fts_syntax_error(memory, monkeypatch):
    _patch_model(
        monkeypatch,
        {
            "What's the deal with C++ vs C#?": [1.0, 0.0],
        },
    )
    memory.add_turn("user", "What's the deal with C++ vs C#?", "t1")

    # must not raise sqlite3.OperationalError on FTS5 special characters
    results = memory.search("What's the deal with C++ vs C#? (again)")

    assert len(results) == 1
