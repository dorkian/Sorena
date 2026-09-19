"""Phase 7: vector search (RAG retrieval half) over Ash's own CV
(cv-optimizer/builder/master.json) and past job-application verdicts
(second-brain/01-projects/cv-optimizer/*/analysis.md), stored in Postgres via
pgvector and retrieved through LangChain's retriever abstraction.

See docs/specs/phase-7-jobscout-graph.md and
docs/adr/0014-jobscout-langgraph-vector-search.md for the full design and why
Postgres was chosen over an embedded vector DB.
"""

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_postgres import PGVector

from sorena.config import POSTGRES_URI
from sorena.long_term_memory import _get_model

COLLECTION_NAME = "jobscout"


class SharedSentenceTransformerEmbeddings(Embeddings):
    """Adapts sorena.long_term_memory's cached all-MiniLM-L6-v2 singleton to
    LangChain's Embeddings interface, so this module doesn't load a second
    copy of the same model (see ADR 0014, Component choices: Embeddings)."""

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return _get_model().encode(texts, normalize_embeddings=True).tolist()

    def embed_query(self, text: str) -> list[float]:
        return _get_model().encode(text, normalize_embeddings=True).tolist()


def _sqlalchemy_uri() -> str:
    """PGVector connects via SQLAlchemy, which needs the driver named
    explicitly in the URL scheme (postgresql+psycopg://...) -- plain
    postgresql:// defaults to the older psycopg2, which isn't installed
    here (Phase 7 uses psycopg v3 throughout). config.POSTGRES_URI stays in
    plain libpq form since other callers (psycopg.connect() directly, e.g.
    examples/verify_postgres.py) expect that instead."""
    return POSTGRES_URI.replace("postgresql://", "postgresql+psycopg://", 1)


def _get_store() -> PGVector:
    return PGVector(
        embeddings=SharedSentenceTransformerEmbeddings(),
        connection=_sqlalchemy_uri(),
        collection_name=COLLECTION_NAME,
        use_jsonb=True,
    )


def upsert_documents(docs: list[Document]) -> None:
    """Idempotent by id: re-running with the same (source, chunk) ids updates
    existing rows in place instead of duplicating them (see
    examples/build_jobscout_index.py for how ids are derived)."""
    store = _get_store()
    ids = [doc.metadata["id"] for doc in docs]
    store.add_documents(docs, ids=ids)


def semantic_match(job_description: str, top_k: int = 5) -> list[dict]:
    """Retrieval half of RAG: returns the top_k chunks (from Ash's CV and past
    application verdicts) most semantically similar to job_description, each
    with a 0-1 similarity score. Used two ways downstream (see the Phase 7
    spec's Architecture diagram):
    - vector_rank: shown as a cheap signal next to bulk-search results
      (retrieval only).
    - deep_dive: the returned snippets are injected into the LLM's judgment
      prompt, grounding its scoring in Ash's real CV language and past
      verdicts (retrieval + generation = full RAG).
    """
    store = _get_store()
    results = store.similarity_search_with_relevance_scores(job_description, k=top_k)
    return [
        {
            "source": doc.metadata.get("source", "unknown"),
            "snippet": doc.page_content,
            "similarity": round(score, 4),
        }
        for doc, score in results
    ]
