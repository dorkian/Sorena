"""Phase 7 step 3 (Retrieve): one-shot script that reads Ash's real CV facts
and past job-application verdicts and loads them into the Postgres/pgvector
store (sorena.jobscout_vectors). Run manually, whenever the source files
change -- not auto-triggered by Sorena itself (see
docs/specs/phase-7-jobscout-graph.md, safety boundaries: Sorena never reads
outside its own repo without an explicit, user-run script).

Mirrors examples/benchmark_memory_recall.py's existing pattern: a plain
script, not a test, meant to be read and run by hand.

Safe to re-run: each document's id is a stable hash of its source path (+
skill/experience id for master.json entries), so re-running upserts in place
(sorena.jobscout_vectors.upsert_documents) instead of duplicating rows --
same idempotency discipline as Phase 5's turn storage (ADR 0008).
"""

import glob
import hashlib
import json
from pathlib import Path

from langchain_core.documents import Document

from sorena.jobscout_vectors import upsert_documents

MASTER_JSON_PATH = Path("/Users/ashkan/Documents/workspace/repos/cv-optimizer/builder/master.json")
ANALYSIS_GLOB = (
    "/Users/ashkan/Documents/workspace/second-brain/01-projects/cv-optimizer/*/analysis.md"
)


def _id(source: str) -> str:
    return hashlib.sha256(source.encode()).hexdigest()[:32]


def _load_master_json_docs() -> list[Document]:
    data = json.loads(MASTER_JSON_PATH.read_text())
    docs = []

    for skill in data.get("skills", []):
        source = f"master.json:skill:{skill['id']}"
        text = (
            f"{skill['category']['en']} ({skill['evidence_level']}): "
            f"{skill['primary_skills']['en']}. "
            f"Also: {skill['secondary_skills']['en']}."
        )
        docs.append(Document(page_content=text, metadata={"id": _id(source), "source": source}))

    for exp in data.get("experience", []):
        source = f"master.json:experience:{exp['id']}"
        text = (
            f"{exp['company']} -- {exp['official_title']['en']}: "
            f"{exp['functional_descriptor']['en']}."
        )
        docs.append(Document(page_content=text, metadata={"id": _id(source), "source": source}))

    for proj in data.get("projects", []):
        source = f"master.json:project:{proj['id']}"
        techs = ", ".join(proj.get("technologies", []))
        text = f"{proj['name']} -- {proj['role']['en']}. Tech: {techs}."
        docs.append(Document(page_content=text, metadata={"id": _id(source), "source": source}))

    return docs


def _load_analysis_docs() -> list[Document]:
    docs = []
    for path_str in glob.glob(ANALYSIS_GLOB):
        path = Path(path_str)
        source = f"analysis:{path.parent.name}"
        text = path.read_text()
        # One file = one chunk, same reasoning as ADR 0008 (Phase 5): each
        # analysis.md is naturally bounded (a few KB, well under the
        # embedding model's input limit) -- splitting it further would
        # fragment retrieval (half a verdict back with no surrounding
        # context) for no benefit.
        docs.append(Document(page_content=text, metadata={"id": _id(source), "source": source}))
    return docs


def main() -> None:
    master_docs = _load_master_json_docs()
    analysis_docs = _load_analysis_docs()
    all_docs = master_docs + analysis_docs

    print(f"master.json: {len(master_docs)} chunks (skills/experience/projects)")
    print(f"analysis.md: {len(analysis_docs)} chunks (past applications)")
    print(f"indexing {len(all_docs)} chunks total...")

    upsert_documents(all_docs)

    print("done.")


if __name__ == "__main__":
    main()
