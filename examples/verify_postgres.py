"""Phase 7 step 1 (Provision): prove Postgres + pgvector are reachable and
working before any LangChain/LangGraph code touches them -- see
docs/specs/phase-7-jobscout-graph.md's Provision step and Definition of Done.
"""

import psycopg

from sorena.config import POSTGRES_URI


def main() -> None:
    with psycopg.connect(POSTGRES_URI) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            assert cur.fetchone() == (1,)
            print("round-trip SELECT 1: ok")

            cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
            conn.commit()
            cur.execute("SELECT extname FROM pg_extension WHERE extname = 'vector'")
            assert cur.fetchone() == ("vector",)
            print("pgvector extension: enabled")

    print("Postgres provisioning verified.")


if __name__ == "__main__":
    main()
