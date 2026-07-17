"""Identity for each agent in the multi-agent system (docs/specs/sorena-multi-agent-plan.md):
a name, brand color, icon, and the one-line reason for that name. Drives both
the system prompt framing and the orb face color (see face.push_state).

Icons/colors are fixed as each agent is actually built, not pre-assigned --
see PERSONAS below for which ones exist so far.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Persona:
    name: str
    color: str
    icon: str
    why: str


PERSONAS: dict[str, Persona] = {
    "orchestrator": Persona(
        name="Sorena",
        color="#F2B33D",
        icon="orchestrator.svg",
        why="the general who commands the others",
    ),
    "dayplanner": Persona(
        name="Jamshid",
        color="#4A90D9",
        icon="dayplanner.svg",  # your call
        why="mythical king who ordered the world and founded Nowruz — literally the calendar guy",
    ),
    "scribe": Persona(
        name="Dabir",
        color="#3FA66A",
        icon="scribe.svg",
        why="the actual Middle Persian word for royal scribe",
    ),
    "coach": Persona(
        name="Bozorgmehr",
        color="#7C5CE0",
        icon="coach.svg",
        why="the legendary sage-vizier famous for teaching and solving puzzles",
    ),
    "interviewer": Persona(
        name="Rostam",
        color="#D9534F",
        icon="interviewer.svg",
        why="the hero of the Seven Labours — the one who tests you",
    ),
    "researcher": Persona(
        name="Simurgh",
        color="#2FD4C8",
        icon="researcher.svg",
        why="the all-seeing wise bird, keeper of knowledge",
    ),
    "jobscout": Persona(
        name="Arash",
        color="#E8792B",
        icon="jobscout.svg",
        why="the archer whose single far shot found the target",
    ),
}
