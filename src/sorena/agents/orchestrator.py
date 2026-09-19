"""Orchestrator: classifies which specialist should handle a message,
delegates to it, and returns its reply. It never does the work itself
(docs/specs/sorena-multi-agent-plan.md §1) -- classify, delegate, merge.
"""

from sorena import agent, face, router
from sorena.agents import (
    bus,
    coach,
    dayplanner,
    interviewer,
    jobscout,
    jobscout_graph,
    researcher,
    scribe,
)
from sorena.agents.personas import PERSONAS

SPECIALISTS = {
    "dayplanner": dayplanner,
    "scribe": scribe,
    "coach": coach,
    "interviewer": interviewer,
    "researcher": researcher,
    "jobscout": jobscout,
}


def _classify(user_message: str) -> str:
    options = "\n".join(f"- {role}: {PERSONAS[role].why}" for role in SPECIALISTS)
    prompt = (
        "Pick exactly one specialist to handle this message. "
        "Reply with only its key, nothing else.\n\n"
        f"Specialists:\n{options}\n\n"
        f"Message: {user_message}"
    )
    response = router.chat([{"role": "user", "content": prompt}])
    normalized = response.strip().lower()

    for role in SPECIALISTS:
        if role in normalized:
            return role
    return next(iter(SPECIALISTS))  # unrecognized response -- fall back to the first specialist


def run(user_message: str, model_override: str | None = None) -> str:
    role = _classify(user_message)
    specialist = SPECIALISTS[role]
    persona = PERSONAS[role]

    face.push_state(
        "speaking", agent={"name": persona.name, "color": persona.color, "icon": persona.icon}
    )

    if role == "jobscout":
        # Phase 7: JobScout runs on its own LangGraph StateGraph instead of
        # the generic hop loop -- see docs/specs/phase-7-jobscout-graph.md
        # and docs/adr/0014-jobscout-langgraph-vector-search.md. Every other
        # specialist below is completely unaffected by this branch.
        reply = jobscout_graph.run(user_message)
    else:
        reply = agent.run(
            user_message,
            system_prompt=specialist.SYSTEM_PROMPT,
            tool_names=specialist.TOOL_NAMES,
            model_override=model_override,
        )

    bus.log_event(agent=role, event_type="handled_message", payload=reply[:200])

    return reply
