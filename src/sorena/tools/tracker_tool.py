"""Phase 7: read/write bridge to Ash's real, already-running job tracker
(ai-job-search-assistant, Docker on localhost:3131, no auth of its own).

Deliberately narrow: two read functions and two enum-bounded write
functions. Every other endpoint the tracker exposes (job creation, scoring,
document generation) is simply never called by anything in this file -- see
docs/adr/0014-jobscout-langgraph-vector-search.md's safety-boundary section.
The valid status/event_type/outcome values below are copied from the
tracker's own server-side validation (ai-job-search-assistant/server/routes/
actions.js), so a rejected value here matches what the server would reject
anyway -- this file just fails fast, before spending an HTTP round trip.

Called directly by sorena.agents.jobscout_graph's nodes as plain Python
function calls, not registered as LLM-callable JSON tool schemas the way
sorena.tools.jobscout_tool's functions are -- JobScout's graph decides for
itself when to call these, rather than leaving that decision to an LLM
picking from a tool list (see docs/specs/phase-7-jobscout-graph.md).
"""

import os

import httpx

TRACKER_URL = os.getenv("SORENA_TRACKER_URL", "http://localhost:3131")

VALID_STATUSES = {"Saved", "Applied", "Interview", "Offer", "Rejected", "Archive"}
VALID_EVENT_TYPES = {"applied", "initial_contact", "interview", "offer", "rejected", "withdrawn"}
VALID_OUTCOMES = {"pending", "pass", "fail"}

_TIMEOUT = 5.0


def get_tracked_jobs(limit: int = 50) -> list[dict]:
    """GET /api/jobs -- read-only. Returns [] (not an exception) if the
    tracker is unreachable, matching mcp_client.py's "dead server is caught,
    not fatal" convention."""
    try:
        resp = httpx.get(f"{TRACKER_URL}/api/jobs", params={"limit": limit}, timeout=_TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPError as e:
        print(f"[tracker_tool] tracker unreachable, skipping: {e}")
        return []


def get_tracked_applications() -> list[dict]:
    """GET /api/actions/applications -- read-only, same non-fatal behaviour
    as get_tracked_jobs."""
    try:
        resp = httpx.get(f"{TRACKER_URL}/api/actions/applications", timeout=_TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPError as e:
        print(f"[tracker_tool] tracker unreachable, skipping: {e}")
        return []


def update_application_status(job_id: int, status: str) -> bool:
    """PUT /api/actions/applications/{job_id}/status. `status` must be one of
    VALID_STATUSES -- checked here, before any network call, so a bad value
    from an LLM can never even reach the tracker."""
    if status not in VALID_STATUSES:
        raise ValueError(f"status must be one of {sorted(VALID_STATUSES)}, got {status!r}")

    try:
        resp = httpx.put(
            f"{TRACKER_URL}/api/actions/applications/{job_id}/status",
            json={"status": status},
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        return True
    except httpx.HTTPError as e:
        print(f"[tracker_tool] tracker unreachable, skipping: {e}")
        return False


def log_application_event(
    job_id: int, event_type: str, event_date: str, outcome: str = "pending"
) -> bool:
    """POST /api/actions/applications/{job_id}/events. `event_type` and
    `outcome` must be in the sets above -- same fail-fast-before-the-network-
    call rule as update_application_status."""
    if event_type not in VALID_EVENT_TYPES:
        raise ValueError(f"event_type must be one of {sorted(VALID_EVENT_TYPES)}, got {event_type!r}")
    if outcome not in VALID_OUTCOMES:
        raise ValueError(f"outcome must be one of {sorted(VALID_OUTCOMES)}, got {outcome!r}")

    try:
        resp = httpx.post(
            f"{TRACKER_URL}/api/actions/applications/{job_id}/events",
            json={"event_type": event_type, "event_date": event_date, "outcome": outcome},
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        return True
    except httpx.HTTPError as e:
        print(f"[tracker_tool] tracker unreachable, skipping: {e}")
        return False
