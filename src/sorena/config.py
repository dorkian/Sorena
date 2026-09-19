import os

from dotenv import load_dotenv

# Must run before the os.getenv() calls below, at import time -- callers that
# reach this module first (e.g. face.py's on-connect config message) can't
# rely on litellm's own load_dotenv() side effect happening earlier, the way
# router.py (which imports litellm before this module) accidentally does.
load_dotenv()

_DEFAULT_CHAIN = "groq/llama-3.3-70b-versatile,gemini/gemini-3.1-flash-lite"
_DEFAULT_LIMITS = "groq/llama-3.3-70b-versatile:30,gemini/gemini-3.1-flash-lite:15"


def _parse_chain(raw: str) -> list[str]:
    return [m.strip() for m in raw.split(",") if m.strip()]


def _parse_limits(raw: str) -> dict[str, int]:
    limits = {}
    for pair in raw.split(","):
        model, rpm = pair.split(":")
        limits[model.strip()] = int(rpm)
    return limits


PROVIDER_CHAIN = _parse_chain(os.getenv("SORENA_PROVIDER_CHAIN", _DEFAULT_CHAIN))
RATE_LIMITS_RPM = _parse_limits(os.getenv("SORENA_RATE_LIMITS_RPM", _DEFAULT_LIMITS))

# Phase 7 (JobScout graph): one Postgres instance (docker-compose.yml's
# `postgres` service) backs both the pgvector store and the LangGraph
# checkpointer -- see docs/adr/0014-jobscout-langgraph-vector-search.md.
# Shared by jobscout_vectors.py and jobscout_graph.py, so it lives here
# rather than in either module alone.
# Plain libpq-style DSN (what psycopg.connect() and pg_isready expect).
# SQLAlchemy-based consumers (jobscout_vectors.py's PGVector store) need the
# driver named explicitly ("+psycopg") in the URL -- see
# jobscout_vectors.py's _sqlalchemy_uri() for why that's adapted there
# instead of changing this one shared constant's format.
POSTGRES_URI = os.getenv(
    "SORENA_POSTGRES_URI", "postgresql://sorena:sorena@localhost:5432/sorena_jobscout"
)
