import pytest

from sorena.tools.registry import MalformedArgumentsError, UnknownToolError, call_tool


def test_call_tool_dispatches_by_name():
    result = call_tool("get_current_time", None)
    assert "T" in result


def test_call_tool_parses_json_args():
    result = call_tool("get_current_time", "{}")
    assert "T" in result


def test_call_tool_raises_on_unknown_name():
    with pytest.raises(UnknownToolError):
        call_tool("not_a_real_tool", None)


def test_call_tool_handles_json_null_arguments():
    # some providers send the literal JSON string "null" for no-arg tools,
    # which json.loads() turns into Python None -- must not be unpacked as **None
    result = call_tool("get_current_time", "null")
    assert "T" in result


def test_call_tool_raises_malformed_on_bad_json():
    with pytest.raises(MalformedArgumentsError):
        call_tool("get_current_time", "{not valid json")


def test_call_tool_raises_malformed_on_unexpected_argument():
    with pytest.raises(MalformedArgumentsError):
        call_tool("get_current_time", '{"nonexistent_arg": "value"}')
