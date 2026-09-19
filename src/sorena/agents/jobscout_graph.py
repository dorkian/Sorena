"""Phase 7: JobScout rebuilt on a LangGraph StateGraph, replacing the
generic tool-calling hop loop (sorena.agent.run()) for this one specialist
only -- see docs/specs/phase-7-jobscout-graph.md and
docs/adr/0014-jobscout-langgraph-vector-search.md.

Build-order note (version 3, feature-complete): all four routes --
bulk_search, deep_dive, skill_gap, status_update -- are now real. The graph
is checkpointed to Postgres and deep_dive has the one interrupt() (see
_get_checkpointer() and deep_dive_node()). Remaining work is formalizing
the manual proofs below into pytest/eval cases and docs (spec's steps 6-8).
"""

import json
import re
from datetime import date

import psycopg
from psycopg.rows import dict_row
from pydantic import BaseModel, Field, ValidationError
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from sorena import router
from sorena.callbacks import TraceCallbackHandler
from sorena.config import POSTGRES_URI
from sorena.tools import delegation_tool, jobscout_tool, tracker_tool
from sorena.jobscout_vectors import semantic_match

_ROUTES = ("bulk_search", "deep_dive", "skill_gap", "status_update")

# status_update_node's outcome vocabulary -- copied from the /job skill's own
# Step 6b table and from tracker_tool.VALID_STATUSES/VALID_EVENT_TYPES/
# VALID_OUTCOMES, so a match here is guaranteed to pass tracker_tool's own
# enum checks. Only the single-status-change cases are handled in this first
# pass -- initial_contact and "interview passed to next round" (which update
# an existing event rather than create one) are the /job skill's richer
# cases, deliberately not built here yet.
_STATUS_EVENT_MAP = {
    "applied": ("Applied", "applied", "pending"),
    "rejected": ("Rejected", "rejected", "fail"),
    "offer": ("Offer", "offer", "pass"),
    "interview": ("Interview", "interview", "pending"),
    "withdrew": ("Archive", "withdrawn", "pending"),
    "withdrawn": ("Archive", "withdrawn", "pending"),
}

# skill_gap_node's split between "just tell me" and "act on it" -- mirrors
# the two-tool split JobScout's own SYSTEM_PROMPT already describes for
# get_skill_gap (report) vs notify_coach_of_skill_gap (delegate to Coach).
_DELEGATE_KEYWORDS = ("schedule", "teach", "lesson", "learning plan")


class JobScoutState(BaseModel):
    """Everything one graph run carries between nodes. A node function
    receives this and returns a dict of just the fields it changed --
    LangGraph merges that dict into the running state for the next node."""

    user_message: str
    route: str = ""
    raw_results: list[dict] = []
    deduped_results: list[dict] = []
    reply: str = ""


class JobMatchJudgment(BaseModel):
    """The LLM's deep-dive rubric judgment, structured and validated instead
    of parsed loosely from free text -- router.chat() has no native
    JSON-schema/tool-calling constraint here (unlike sorena.agent's hop
    loop), so this is "prompt for JSON, then validate with Pydantic,"
    a common real-world structured-output pattern in its own right.
    Field ranges mirror SAVE_JOB_MATCH_SCORE_SCHEMA in jobscout_tool.py."""

    skills_match: int = Field(ge=0, le=30)
    experience_fit: int = Field(ge=0, le=20)
    salary_alignment: int = Field(ge=0, le=15)
    industry_relevance: int = Field(ge=0, le=15)
    location_fit: int = Field(ge=0, le=10)
    growth_potential: int = Field(ge=0, le=10)
    interview_chance: str
    why_match: str
    missing_skills: str = ""
    red_flags: str = ""
    notes: str = ""


def _extract_query_term(message: str) -> str:
    """find_job_posting() does a SQL substring match against company/title,
    so passing it a whole sentence ("score the Mitre Media posting") never
    matches -- only "Mitre Media" would. Heuristic: pull out runs of
    capitalized words (a lightweight stand-in for real named-entity
    recognition) and take the longest one, since a company/product name is
    usually the longest capitalized run in the sentence. Falls back to the
    whole message if nothing capitalized is found."""
    runs = re.findall(r"\b[A-Z][\w&.]*(?:\s+[A-Z][\w&.]*)*\b", message)
    return max(runs, key=len) if runs else message


def _judge_posting(cv_text: str, posting: dict, retrieved_context: list[dict]) -> JobMatchJudgment:
    """RAG step: retrieved_context (from semantic_match) is woven directly
    into the judgment prompt, grounding the score in Ash's actual CV
    language and past verdicts on similar postings -- not just the raw CV
    text and a generic rubric (see ADR 0014's RAG explanation)."""
    context_block = "\n".join(f"- {c['snippet'][:300]}" for c in retrieved_context) or "(none found)"

    prompt = (
        "Score this job posting against the CV, using this rubric: Skills Match /30, "
        "Experience Fit /20, Salary Alignment /15, Industry Relevance /15, "
        "Location/Type /10, Growth Potential /10.\n\n"
        f"Job posting -- {posting['title']} at {posting['company']}:\n{posting['description']}\n\n"
        f"CV:\n{cv_text}\n\n"
        "Relevant excerpts from Ash's CV and past application verdicts on similar "
        f"postings (use these to ground your judgment):\n{context_block}\n\n"
        "Reply with ONLY a JSON object, no markdown fences, no extra text, matching "
        "exactly this shape:\n"
        '{"skills_match": int, "experience_fit": int, "salary_alignment": int, '
        '"industry_relevance": int, "location_fit": int, "growth_potential": int, '
        '"interview_chance": "Low|Medium|Medium-High|High", "why_match": str, '
        '"missing_skills": str, "red_flags": str, "notes": str}'
    )
    response = router.chat([{"role": "user", "content": prompt}])
    payload = json.loads(response.strip().removeprefix("```json").removeprefix("```").removesuffix("```"))
    return JobMatchJudgment.model_validate(payload)


def route_node(state: JobScoutState) -> dict:
    """Classifies the turn into one of _ROUTES, same classify-then-delegate
    shape as orchestrator.py's _classify(), just scoped to JobScout's own
    four intents instead of picking a specialist."""
    prompt = (
        "Classify this message into exactly one category. Reply with only "
        "the category word, nothing else.\n\n"
        "Categories:\n"
        "- bulk_search: find/search for job postings matching some criteria\n"
        "- deep_dive: score or evaluate one specific posting Ash names\n"
        "- skill_gap: what skill should Ash learn next, based on postings seen\n"
        "- status_update: Ash reporting an outcome (applied/rejected/interview/offer)\n\n"
        f"Message: {state.user_message}"
    )
    response = router.chat([{"role": "user", "content": prompt}])
    normalized = response.strip().lower()

    for route in _ROUTES:
        if route in normalized:
            return {"route": route}
    return {"route": "bulk_search"}  # unrecognized reply -- same fallback style as orchestrator.py


def bulk_search_node(state: JobScoutState) -> dict:
    """Real work: wraps jobscout_tool.search_and_score_jobs_raw(), using the
    user's own message as the search query."""
    results = jobscout_tool.search_and_score_jobs_raw(state.user_message)
    return {"raw_results": results}


def dedup_against_tracker_node(state: JobScoutState) -> dict:
    """Cross-references bulk-search results against Ash's real tracker so
    JobScout doesn't resurface something he's already tracked there. Fuzzy
    match: same company AND same title, case-insensitive."""
    tracked = tracker_tool.get_tracked_applications()
    tracked_pairs = {(a.get("company", "").lower(), a.get("title", "").lower()) for a in tracked}

    deduped = [
        job
        for job in state.raw_results
        if (job["company"].lower(), job["title"].lower()) not in tracked_pairs
    ]
    return {"deduped_results": deduped}


def vector_rank_node(state: JobScoutState) -> dict:
    """Retrieval-only half of RAG (see ADR 0014): annotates each deduped
    result with how semantically close it is to Ash's CV/past verdicts,
    as a signal alongside the existing mechanical score -- not a
    replacement for it."""
    lines = []
    for job in state.deduped_results:
        matches = semantic_match(job["description"] or job["title"], top_k=1)
        best = matches[0] if matches else None
        signal = f"semantic match: {best['similarity']:.2f} ({best['source']})" if best else "no semantic match"
        lines.append(
            f"[{job['score']}] {job['title']} at {job['company']} ({job['location']}) "
            f"-- {job['url']} | {signal}"
        )

    reply = "\n".join(lines) if lines else "No new postings found (or all already tracked)."
    return {"reply": reply}


def deep_dive_node(state: JobScoutState) -> dict:
    """The one interrupt() in this graph. Deep-dive scoring is explicitly
    "for one posting Ash actually cares about" (JobScout's own persona
    prompt) -- this makes that boundary a real, framework-enforced pause
    instead of just a line in a prompt an LLM might not honor. Postgres
    checkpointing (see _get_checkpointer()) means this pause survives a
    full Sorena restart, not just an in-memory wait."""
    term = _extract_query_term(state.user_message)
    posting = jobscout_tool.find_job_posting(term)
    if posting is None:
        return {"reply": f"No stored posting matches '{term}'."}

    confirmed = interrupt(
        {
            "question": f"Run a full deep-dive score on {posting['title']} at {posting['company']}?",
            "url": posting["url"],
        }
    )
    if not confirmed:
        return {"reply": "Deep-dive cancelled."}

    cv_text = jobscout_tool.get_cv()
    retrieved = semantic_match(posting["description"], top_k=3)  # RAG retrieval half

    try:
        judgment = _judge_posting(cv_text, posting, retrieved)  # RAG generation half
    except (json.JSONDecodeError, ValidationError) as e:
        return {"reply": f"Deep-dive judgment failed to parse, not saved: {e}"}

    # save_job_match_score computes overall_score/grade itself and includes
    # them in the returned string -- no need to duplicate that math here.
    result = jobscout_tool.save_job_match_score(
        company=posting["company"],
        title=posting["title"],
        url=posting["url"],
        skills_match=judgment.skills_match,
        experience_fit=judgment.experience_fit,
        salary_alignment=judgment.salary_alignment,
        industry_relevance=judgment.industry_relevance,
        location_fit=judgment.location_fit,
        growth_potential=judgment.growth_potential,
        interview_chance=judgment.interview_chance,
        why_match=judgment.why_match,
        missing_skills=judgment.missing_skills,
        red_flags=judgment.red_flags,
        notes=judgment.notes,
    )
    return {"reply": result}


def skill_gap_node(state: JobScoutState) -> dict:
    """A plain question ("what should I learn next") just reports the gap;
    wording that asks for action (schedule/teach/lesson) delegates to Coach
    instead -- both existing tools, just chosen here instead of by an LLM
    picking from a tool list."""
    message = state.user_message.lower()
    if any(kw in message for kw in _DELEGATE_KEYWORDS):
        reply = delegation_tool.notify_coach_of_skill_gap()
    else:
        reply = jobscout_tool.get_skill_gap()
    return {"reply": reply}


def status_update_node(state: JobScoutState) -> dict:
    """Lets Ash report an outcome by voice/text ("I got rejected by X") and
    have it land in the real tracker -- tracker_tool.py's two enum-bounded
    write functions are the only place this graph can write to Ash's real
    application data (see ADR 0014's safety-boundary section)."""
    message = state.user_message.lower()
    mapping = next((v for k, v in _STATUS_EVENT_MAP.items() if k in message), None)
    if mapping is None:
        return {
            "reply": (
                "Couldn't tell what outcome you're reporting -- try naming it plainly "
                "(applied/rejected/interview/offer/withdrew)."
            )
        }
    status, event_type, outcome = mapping

    company_term = _extract_query_term(state.user_message)
    applications = tracker_tool.get_tracked_applications()
    match = next(
        (a for a in applications if company_term.lower() in a.get("company", "").lower()), None
    )
    if match is None:
        return {"reply": f"Couldn't find a tracked application matching '{company_term}'."}

    job_id = match["job_id"]
    status_ok = tracker_tool.update_application_status(job_id, status)
    event_ok = tracker_tool.log_application_event(job_id, event_type, date.today().isoformat(), outcome)

    if status_ok and event_ok:
        return {"reply": f"Tracker updated -- {match['company']}: {status}."}
    return {"reply": f"Tracker update failed for {match['company']} (tracker may be unreachable)."}


def _build_graph() -> StateGraph:
    graph = StateGraph(JobScoutState)

    graph.add_node("route", route_node)
    graph.add_node("bulk_search", bulk_search_node)
    graph.add_node("dedup_against_tracker", dedup_against_tracker_node)
    graph.add_node("vector_rank", vector_rank_node)
    graph.add_node("deep_dive", deep_dive_node)
    graph.add_node("skill_gap", skill_gap_node)
    graph.add_node("status_update", status_update_node)

    graph.add_edge(START, "route")
    graph.add_conditional_edges(
        "route",
        lambda state: state.route,
        {
            "bulk_search": "bulk_search",
            "deep_dive": "deep_dive",
            "skill_gap": "skill_gap",
            "status_update": "status_update",
        },
    )
    graph.add_edge("bulk_search", "dedup_against_tracker")
    graph.add_edge("dedup_against_tracker", "vector_rank")
    graph.add_edge("vector_rank", END)
    graph.add_edge("deep_dive", END)
    graph.add_edge("skill_gap", END)
    graph.add_edge("status_update", END)

    return graph


_checkpointer: PostgresSaver | None = None
_compiled_app = None


def _get_checkpointer() -> PostgresSaver:
    """Lazy singleton, same pattern as long_term_memory._get_model(): one
    real Postgres connection reused across calls, instead of reconnecting
    on every single graph run. autocommit=True and row_factory=dict_row are
    PostgresSaver's own documented requirements, not stylistic choices."""
    global _checkpointer
    if _checkpointer is None:
        conn = psycopg.connect(POSTGRES_URI, autocommit=True, row_factory=dict_row)
        _checkpointer = PostgresSaver(conn)
        _checkpointer.setup()  # creates the checkpoint tables if they don't exist yet; safe to re-run
    return _checkpointer


def _get_app():
    global _compiled_app
    if _compiled_app is None:
        _compiled_app = _build_graph().compile(checkpointer=_get_checkpointer())
    return _compiled_app


def run(user_message: str, thread_id: str = "default") -> str:
    """External interface, called by orchestrator.py instead of the generic
    agent.run() hop loop when the routed specialist is jobscout.

    thread_id identifies which conversation's checkpoint history to use --
    every call with the same thread_id shares state/history in Postgres.
    Sorena is single-user, so "default" is fine unless a caller needs
    separate parallel JobScout conversations."""
    app = _get_app()
    handler = TraceCallbackHandler(user_input=user_message)
    config = {"configurable": {"thread_id": thread_id}, "callbacks": [handler]}
    final_state = app.invoke(JobScoutState(user_message=user_message), config=config)
    reply = final_state.get("reply", "")
    handler.finish(reply)
    return reply
