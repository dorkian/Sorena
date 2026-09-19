"""JobScout: pulls postings from Remotive (free, no API key), dedupes
against SQLite, and scores each against data/profile.yaml
(docs/specs/sorena-multi-agent-plan.md §2). One source for now -- Adzuna,
HN "Who is Hiring", and Tavily searches are the next sources to add,
tracked separately, not built here.

Two scoring tiers, deliberately kept separate:
- `score_job` (cheap, mechanical, runs on every Remotive result) for bulk
  triage across dozens of postings per search.
- `save_job_match_score` (the real rubric from Ash's cv-optimizer /job
  skill -- 6 weighted dimensions judged against the actual CV) for a
  deliberate deep-dive on one posting Ash wants a real read on. Running
  the rubric on every bulk result would mean an LLM judgment call per
  posting for postings nobody's going to apply to -- the two-tier split
  is what keeps this affordable.
"""

import hashlib
import os
import sqlite3
from pathlib import Path

import requests
import yaml

from sorena.long_term_memory import DB_PATH

PROFILE_PATH = Path(__file__).resolve().parent.parent.parent.parent / "data" / "profile.yaml"
REMOTIVE_API = "https://remotive.com/api/remote-jobs"

# Ash's real CV lives in a separate second-brain project (cv-optimizer), not
# this repo -- same "points at Ash's real personal data" precedent as the
# Google Calendar integration. Overridable since the path is specific to this
# machine. Defaults updated 2026-09-17 (Phase 7) from the pre-migration
# Windows vault path (D:/claude-projects/vault/...), which was dead on this
# Mac and silently broke get_cv() -- see docs/specs/phase-7-jobscout-graph.md,
# Deliverables, "Fix a pre-existing blocker".
CV_PATH = Path(
    os.getenv(
        "SORENA_CV_PATH",
        "/Users/ashkan/Documents/workspace/second-brain/01-projects/cv-optimizer/cv-en-optimized.md",
    )
)
CV_PATH_FALLBACK = Path(
    os.getenv(
        "SORENA_CV_PATH_FALLBACK",
        "/Users/ashkan/Documents/workspace/second-brain/01-projects/cv-optimizer/cv-en.md",
    )
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS job_postings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dedupe_hash TEXT NOT NULL UNIQUE,
    company TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    location TEXT NOT NULL,
    url TEXT NOT NULL,
    score INTEGER NOT NULL,
    seen_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS job_match_scores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company TEXT NOT NULL,
    title TEXT NOT NULL,
    url TEXT NOT NULL DEFAULT '',
    skills_match INTEGER NOT NULL,
    experience_fit INTEGER NOT NULL,
    salary_alignment INTEGER NOT NULL,
    industry_relevance INTEGER NOT NULL,
    location_fit INTEGER NOT NULL,
    growth_potential INTEGER NOT NULL,
    overall_score INTEGER NOT NULL,
    grade TEXT NOT NULL,
    interview_chance TEXT NOT NULL,
    why_match TEXT NOT NULL DEFAULT '',
    missing_skills TEXT NOT NULL DEFAULT '',
    red_flags TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT '',
    scored_at TEXT NOT NULL
);
"""


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(_SCHEMA)
    try:
        conn.execute("ALTER TABLE job_postings ADD COLUMN description TEXT NOT NULL DEFAULT ''")
    except sqlite3.OperationalError:
        pass  # column already exists -- ALTER TABLE has no "IF NOT EXISTS" in SQLite
    return conn


def _dedupe_hash(company: str, title: str, location: str) -> str:
    key = f"{company.strip().lower()}|{title.strip().lower()}|{location.strip().lower()}"
    return hashlib.sha256(key.encode()).hexdigest()


def load_profile() -> dict:
    if not PROFILE_PATH.exists():
        raise FileNotFoundError(
            f"Missing {PROFILE_PATH} -- see docs/specs/sorena-multi-agent-plan.md §2 for the shape."
        )
    return yaml.safe_load(PROFILE_PATH.read_text())


def score_job(job: dict, profile: dict) -> int:
    """0-100 heuristic: keyword overlap between the posting and the
    profile's skills/target roles, plus a location-fit bonus/penalty.
    Ponytail: simple and transparent, not the multi-dimensional scorer from
    Ash's other job-search project -- porting that logic is future work
    once this pipeline itself is proven (docs/specs/sorena-multi-agent-plan.md
    §2 says port it, don't rewrite it, but that source isn't in this repo).
    """
    text = f"{job.get('title', '')} {job.get('description', '')}".lower()

    skills = profile.get("skills", {})
    strong = skills.get("strong", [])
    learning = skills.get("learning", [])
    role_hits = sum(1 for role in profile.get("target_roles", []) if role.lower() in text)
    strong_hits = sum(1 for s in strong if s.lower() in text)
    learning_hits = sum(1 for s in learning if s.lower() in text)

    score = role_hits * 20 + strong_hits * 8 + learning_hits * 4

    location = profile.get("location", {})
    job_type = (job.get("job_type") or "").lower()
    candidate_office = (job.get("candidate_required_location") or "").lower()
    if location.get("remote") == "preferred" and "remote" in (job.get("title", "") + job_type):
        score += 10
    dealbreakers = [d.lower() for d in profile.get("dealbreakers", [])]
    if any(d in candidate_office for d in dealbreakers):
        score -= 50

    return max(0, min(100, score))


SEARCH_AND_SCORE_JOBS_SCHEMA = {
    "type": "function",
    "function": {
        "name": "search_and_score_jobs",
        "description": (
            "Search Remotive for job postings matching a query, score each against Ash's "
            "profile.yaml, skip postings already seen, and save new ones."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "e.g. 'AI engineer'"},
                "limit": {
                    "type": "integer",
                    "description": "Max top-scored postings to report. Default 10.",
                },
            },
            "required": ["query"],
        },
    },
}


def search_and_score_jobs_raw(query: str, limit: int = 10) -> list[dict]:
    """Structured version of search_and_score_jobs, for callers that need
    real fields (company/title/score/...) instead of a pre-formatted string
    -- same split as find_skill_gap() (structured) vs get_skill_gap()
    (string). Added in Phase 7 for jobscout_graph.py's bulk_search node,
    which needs real fields to run dedup_against_tracker's fuzzy matching
    and vector_rank's semantic annotation against. search_and_score_jobs()
    below is now a thin formatting wrapper around this -- its own behavior
    (including the exact string it returns) is unchanged."""
    profile = load_profile()
    resp = requests.get(REMOTIVE_API, params={"search": query, "limit": limit}, timeout=10)
    resp.raise_for_status()
    # Remotive's API silently ignores a `limit` query param -- it always
    # returns every match. Every result still gets deduped/scored/stored
    # below; `limit` only caps what's reported back (applied after sorting
    # by score, further down), so "top N" is actually top-scored, not just
    # the first N raw results.
    jobs = resp.json().get("jobs", [])

    conn = _connect()
    try:
        new_matches = []
        for job in jobs:
            company = job.get("company_name", "unknown")
            title = job.get("title", "untitled")
            location = job.get("candidate_required_location", "unspecified")
            dedupe_hash = _dedupe_hash(company, title, location)

            existing = conn.execute(
                "SELECT id FROM job_postings WHERE dedupe_hash = ?", (dedupe_hash,)
            ).fetchone()
            if existing:
                continue

            score = score_job(job, profile)
            conn.execute(
                "INSERT INTO job_postings "
                "(dedupe_hash, company, title, description, location, url, score, seen_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))",
                (
                    dedupe_hash,
                    company,
                    title,
                    job.get("description", ""),
                    location,
                    job.get("url", ""),
                    score,
                ),
            )
            new_matches.append(
                {
                    "score": score,
                    "company": company,
                    "title": title,
                    "description": job.get("description", ""),
                    "location": location,
                    "url": job.get("url", ""),
                }
            )
        conn.commit()
    finally:
        conn.close()

    new_matches.sort(key=lambda m: m["score"], reverse=True)
    return new_matches[:limit]


def search_and_score_jobs(query: str, limit: int = 10) -> str:
    top = search_and_score_jobs_raw(query, limit)

    if not top:
        return "No new postings found (either none matched, or all were already seen)."

    # Remotive's terms require linking back to their listing URL when
    # relaying jobs found through their API -- keep the url in every line.
    lines = [
        f"[{m['score']}] {m['title']}: {m['description']} at {m['company']} "
        f"({m['location']}) -- {m['url']} (via Remotive)"
        for m in top
    ]
    return "\n".join(lines)


def find_skill_gap() -> tuple[str, int, int] | None:
    """Returns (skill, mention_count, total_postings), or None if there's
    nothing to analyze yet or no gap stands out.

    Only checks profile.skills.learning -- a skill already in `strong`
    isn't a gap by definition. A skill that mentions in zero stored
    postings doesn't get to "win" just for being first in the list; that's
    not a gap signal, that's no data.
    """
    profile = load_profile()
    learning_skills = profile.get("skills", {}).get("learning", [])
    if not learning_skills:
        return None

    conn = _connect()
    try:
        rows = conn.execute("SELECT title, description FROM job_postings").fetchall()
    finally:
        conn.close()

    total = len(rows)
    if total == 0:
        return None

    texts = [f"{title} {description}".lower() for title, description in rows]
    best_skill, best_count = None, 0
    for skill in learning_skills:
        needle = skill.lower()
        count = sum(1 for text in texts if needle in text)
        if count > best_count:
            best_skill, best_count = skill, count

    if best_skill is None:
        return None
    return best_skill, best_count, total


GET_SKILL_GAP_SCHEMA = {
    "type": "function",
    "function": {
        "name": "get_skill_gap",
        "description": (
            "Find which of Ash's learning-list skills shows up most often across job "
            "postings seen so far -- the strongest signal for what to prioritize learning."
        ),
        "parameters": {"type": "object", "properties": {}},
    },
}


def get_skill_gap() -> str:
    gap = find_skill_gap()
    if gap is None:
        return "Not enough posting data yet to identify a skill gap."
    skill, count, total = gap
    return f"{skill} appeared in {count} of {total} postings seen so far -- your top gap."


GET_CV_SCHEMA = {
    "type": "function",
    "function": {
        "name": "get_cv",
        "description": "Read Ash's current CV/resume text, for matching against a job posting.",
        "parameters": {"type": "object", "properties": {}},
    },
}


def get_cv() -> str:
    for path in (CV_PATH, CV_PATH_FALLBACK):
        if path.exists():
            return path.read_text(encoding="utf-8")
    return (
        f"No CV file found at {CV_PATH} or {CV_PATH_FALLBACK} -- "
        "ask Ash where their CV/resume lives, or set SORENA_CV_PATH."
    )


GET_JOB_POSTING_SCHEMA = {
    "type": "function",
    "function": {
        "name": "get_job_posting",
        "description": (
            "Look up a previously-seen job posting by company or title (substring match) "
            "and return its full description -- e.g. to build interview questions from it."
        ),
        "parameters": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    },
}


def find_job_posting(query: str) -> dict | None:
    """Structured version of get_job_posting, for callers (jobscout_graph.py's
    deep_dive node) that need real fields instead of a formatted string --
    same split as search_and_score_jobs_raw/search_and_score_jobs."""
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT company, title, description, url FROM job_postings "
            "WHERE company LIKE ? OR title LIKE ? ORDER BY seen_at DESC LIMIT 1",
            (f"%{query}%", f"%{query}%"),
        ).fetchone()
    finally:
        conn.close()

    if row is None:
        return None
    company, title, description, url = row
    return {"company": company, "title": title, "description": description, "url": url}


def get_job_posting(query: str) -> str:
    posting = find_job_posting(query)
    if posting is None:
        return f"No stored posting matches '{query}'."
    return f"{posting['title']} at {posting['company']} ({posting['url']}):\n{posting['description']}"


def _grade_for(overall_score: int) -> str:
    if overall_score >= 90:
        return "A"
    if overall_score >= 80:
        return "B"
    if overall_score >= 70:
        return "C"
    if overall_score >= 60:
        return "D"
    return "F"


SAVE_JOB_MATCH_SCORE_SCHEMA = {
    "type": "function",
    "function": {
        "name": "save_job_match_score",
        "description": (
            "Save a full multi-dimensional match score for a job posting against Ash's real "
            "CV (call get_cv first) -- the same rubric as the /job skill: Skills Match /30, "
            "Experience Fit /20, Salary Alignment /15, Industry Relevance /15, Location/Type "
            "/10, Growth Potential /10. Use this for a deliberate deep-dive on one posting, "
            "not for bulk-scoring search results."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "company": {"type": "string"},
                "title": {"type": "string"},
                "url": {"type": "string"},
                "skills_match": {"type": "integer", "description": "0-30"},
                "experience_fit": {"type": "integer", "description": "0-20"},
                "salary_alignment": {"type": "integer", "description": "0-15"},
                "industry_relevance": {"type": "integer", "description": "0-15"},
                "location_fit": {"type": "integer", "description": "0-10"},
                "growth_potential": {"type": "integer", "description": "0-10"},
                "interview_chance": {
                    "type": "string",
                    "description": "Low, Medium, Medium-High, or High",
                },
                "why_match": {"type": "string", "description": "Comma-separated key match points."},
                "missing_skills": {
                    "type": "string",
                    "description": "Comma-separated missing skills, or empty.",
                },
                "red_flags": {
                    "type": "string",
                    "description": "Comma-separated red flags, or empty.",
                },
                "notes": {"type": "string"},
            },
            "required": [
                "company",
                "title",
                "skills_match",
                "experience_fit",
                "salary_alignment",
                "industry_relevance",
                "location_fit",
                "growth_potential",
                "interview_chance",
            ],
        },
    },
}


def save_job_match_score(
    company: str,
    title: str,
    skills_match: int,
    experience_fit: int,
    salary_alignment: int,
    industry_relevance: int,
    location_fit: int,
    growth_potential: int,
    interview_chance: str,
    url: str = "",
    why_match: str = "",
    missing_skills: str = "",
    red_flags: str = "",
    notes: str = "",
) -> str:
    # Grade is derived from the component scores, not trusted as a separate
    # LLM-supplied field -- keeps the total and the letter grade from ever
    # disagreeing with each other (same reasoning as interview_tool's
    # server-computed average).
    overall_score = (
        skills_match
        + experience_fit
        + salary_alignment
        + industry_relevance
        + location_fit
        + growth_potential
    )
    grade = _grade_for(overall_score)

    conn = _connect()
    try:
        conn.execute(
            "INSERT INTO job_match_scores "
            "(company, title, url, skills_match, experience_fit, salary_alignment, "
            "industry_relevance, location_fit, growth_potential, overall_score, grade, "
            "interview_chance, why_match, missing_skills, red_flags, notes, scored_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))",
            (
                company,
                title,
                url,
                skills_match,
                experience_fit,
                salary_alignment,
                industry_relevance,
                location_fit,
                growth_potential,
                overall_score,
                grade,
                interview_chance,
                why_match,
                missing_skills,
                red_flags,
                notes,
            ),
        )
        conn.commit()
        return f"Saved: grade {grade}, {overall_score}/100 for {title} at {company}."
    finally:
        conn.close()


GET_JOB_MATCH_HISTORY_SCHEMA = {
    "type": "function",
    "function": {
        "name": "get_job_match_history",
        "description": "Get recent deep-dive match scores, most recent first.",
        "parameters": {
            "type": "object",
            "properties": {"limit": {"type": "integer", "description": "Default 10."}},
        },
    },
}


def get_job_match_history(limit: int = 10) -> str:
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT scored_at, grade, overall_score, title, company FROM job_match_scores "
            "ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    finally:
        conn.close()

    if not rows:
        return "No match scores saved yet."
    return "\n".join(
        f"{scored_at} [{grade}] {overall_score}/100 - {title} at {company}"
        for scored_at, grade, overall_score, title, company in rows
    )


def get_recent_job_match_scores(days: int = 7) -> list[tuple[str, str]]:
    """Raw (scored_at, grade) rows from the last `days` days, for
    sorena.tools.digest_tool -- same internal-helper convention as
    quiz_tool.get_recent_quiz_attempts.

    `scored_at` is stored via SQLite's own `datetime('now')` (space-
    separated, e.g. "2026-07-17 12:00:00"), not Python's
    `datetime.now(UTC).isoformat()` (T-separated, with a timezone suffix) --
    those two formats sort inconsistently against each other as plain
    strings (' ' < 'T' in ASCII, so a same-instant row would wrongly
    compare as "before" an isoformat cutoff). The cutoff is computed with
    SQLite's own `datetime('now', ?)` instead, so both sides of the
    comparison are in the same format.
    """
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT scored_at, grade FROM job_match_scores "
            "WHERE scored_at >= datetime('now', ?) ORDER BY scored_at ASC",
            (f"-{days} days",),
        ).fetchall()
    finally:
        conn.close()
    return [(scored_at, grade) for scored_at, grade in rows]
