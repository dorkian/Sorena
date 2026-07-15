import json

from sorena import mcp_client


class FakeTool:
    def __init__(self, name, description="", input_schema=None):
        self.name = name
        self.description = description
        self.inputSchema = input_schema or {"type": "object", "properties": {}}


class FakeListToolsResult:
    def __init__(self, tools):
        self.tools = tools


class FakeContentPart:
    def __init__(self, text):
        self.text = text


class FakeCallToolResult:
    def __init__(self, text):
        self.content = [FakeContentPart(text)]


class FakeSession:
    def __init__(self, tools, call_results=None):
        self._tools = tools
        self._call_results = call_results or {}

    async def list_tools(self):
        return FakeListToolsResult(self._tools)

    async def call_tool(self, name, arguments):
        return FakeCallToolResult(self._call_results.get(name, "ok"))


def write_config(tmp_path, servers):
    path = tmp_path / "mcp_servers.json"
    path.write_text(json.dumps({"servers": servers}))
    return path


def test_connect_all_converts_tools_to_openai_shape(tmp_path, monkeypatch):
    fake_session = FakeSession(
        [FakeTool("search", "desc", {"type": "object", "properties": {"q": {"type": "string"}}})]
    )

    async def fake_connect_one(self, server):
        return fake_session

    monkeypatch.setattr(mcp_client.MCPBridge, "_connect_one", fake_connect_one)

    config_path = write_config(tmp_path, [{"name": "test-server", "command": "fake", "args": []}])
    bridge = mcp_client.MCPBridge()
    tools, schemas = bridge.connect_all(config_path)

    assert "mcp_test-server_search" in tools
    schema = schemas[0]
    assert schema["type"] == "function"
    assert schema["function"]["name"] == "mcp_test-server_search"
    assert schema["function"]["parameters"] == {
        "type": "object",
        "properties": {"q": {"type": "string"}},
    }


def test_one_dead_server_does_not_block_others(tmp_path, monkeypatch):
    fake_session = FakeSession([FakeTool("ok_tool")])

    async def fake_connect_one(self, server):
        if server["name"] == "dead":
            raise ConnectionError("boom")
        return fake_session

    monkeypatch.setattr(mcp_client.MCPBridge, "_connect_one", fake_connect_one)

    config_path = write_config(
        tmp_path, [{"name": "dead", "command": "fake"}, {"name": "alive", "command": "fake"}]
    )
    bridge = mcp_client.MCPBridge()
    tools, schemas = bridge.connect_all(config_path)

    assert "mcp_alive_ok_tool" in tools
    assert not any("dead" in name for name in tools)


def test_call_dispatches_to_correct_session(tmp_path, monkeypatch):
    fake_session = FakeSession([FakeTool("echo")], call_results={"echo": "hello from mcp"})

    async def fake_connect_one(self, server):
        return fake_session

    monkeypatch.setattr(mcp_client.MCPBridge, "_connect_one", fake_connect_one)

    config_path = write_config(tmp_path, [{"name": "s", "command": "fake"}])
    bridge = mcp_client.MCPBridge()
    tools, _ = bridge.connect_all(config_path)

    assert tools["mcp_s_echo"](arg1="x") == "hello from mcp"
