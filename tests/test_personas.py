import re

from sorena.agents.personas import PERSONAS, Persona

HEX_COLOR = re.compile(r"^#[0-9A-Fa-f]{6}$")


def test_every_persona_has_a_valid_hex_color():
    for role, persona in PERSONAS.items():
        assert isinstance(persona, Persona)
        assert HEX_COLOR.match(persona.color), f"{role} has an invalid color: {persona.color!r}"


def test_orchestrator_persona_is_sorena():
    assert PERSONAS["orchestrator"].name == "Sorena"
