from sorena.agents import interviewer


def test_system_prompt_instructs_switching_to_italian():
    assert "Italian" in interviewer.SYSTEM_PROMPT
