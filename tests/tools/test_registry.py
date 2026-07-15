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


def test_register_mcp_tools_merges_into_existing_registry(monkeypatch):
    from sorena.tools import registry

    monkeypatch.setattr(registry, "TOOLS", dict(registry.TOOLS))
    monkeypatch.setattr(registry, "TOOL_SCHEMAS", list(registry.TOOL_SCHEMAS))

    fake_schema = {
        "type": "function",
        "function": {"name": "mcp_x_y", "description": "", "parameters": {}},
    }
    registry.register_mcp_tools({"mcp_x_y": lambda: "z"}, [fake_schema])

    assert "mcp_x_y" in registry.TOOLS
    assert fake_schema in registry.TOOL_SCHEMAS
    assert call_tool("mcp_x_y", None) == "z"
