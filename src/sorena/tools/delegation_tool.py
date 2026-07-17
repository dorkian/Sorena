"""Cross-agent delegation: one specialist calls another directly as a tool,
without going back through the Orchestrator's classifier
(docs/specs/sorena-multi-agent-plan.md §2, "Researcher... feeds the Coach").
Runs the target specialist's own full agent.run() loop and returns its
final reply as a string.
"""

from sorena.agents import researcher

ASK_RESEARCHER_SCHEMA = {
    "type": "function",
    "function": {
        "name": "ask_researcher",
        "description": (
            "Delegate a research question to the Researcher specialist -- it will web "
            "search and summarize to a few bullets. Use this to pull material on a "
            "learning topic before teaching it."
        ),
        "parameters": {
            "type": "object",
            "properties": {"topic": {"type": "string"}},
            "required": ["topic"],
        },
    },
}


def ask_researcher(topic: str) -> str:
    # deferred: agent.py imports sorena.tools (this package), so a top-level
    # import here would be circular -- see docs/adr/0011.
    from sorena import agent

    return agent.run(
        topic, system_prompt=researcher.SYSTEM_PROMPT, tool_names=researcher.TOOL_NAMES
    )


NOTIFY_COACH_OF_SKILL_GAP_SCHEMA = {
    "type": "function",
    "function": {
        "name": "notify_coach_of_skill_gap",
        "description": (
            "Analyze skill gaps across job postings seen so far (docs/specs/"
            "sorena-multi-agent-plan.md §2, JobScout -> Coach) and delegate to Coach to "
            "schedule a micro-lesson/quiz on the top one. Use when Ash asks to connect "
            "job-search findings to their learning plan."
        ),
        "parameters": {"type": "object", "properties": {}},
    },
}


def notify_coach_of_skill_gap() -> str:
    # deferred for the same reason as ask_researcher's import above --
    # jobscout_tool is a sibling module in this same circularly-imported
    # package, so importing it at module level hits the identical cycle.
    from sorena import agent
    from sorena.agents import coach
    from sorena.tools import jobscout_tool

    gap = jobscout_tool.find_skill_gap()
    if gap is None:
        return "No skill gap to report yet -- not enough posting data."

    skill, count, total = gap
    message = (
        f"JobScout here: across {total} job postings seen so far, '{skill}' -- one of "
        f"Ash's declared learning-list skills -- appeared in {count} of them. That's the "
        "top skill gap right now. Please schedule a micro-lesson and quiz on it."
    )
    return agent.run(message, system_prompt=coach.SYSTEM_PROMPT, tool_names=coach.TOOL_NAMES)
