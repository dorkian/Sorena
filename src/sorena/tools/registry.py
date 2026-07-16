import json

from sorena.tools import file_search_tool, recall_tool, shell_tool, time_tool, web_search_tool

TOOLS = {
    "get_current_time": time_tool.run,
    "search_files": file_search_tool.run,
    "web_search": web_search_tool.run,
    "run_shell_command": shell_tool.run,
    "recall_memory": recall_tool.run,
}

TOOL_SCHEMAS = [
    time_tool.SCHEMA,
    file_search_tool.SCHEMA,
    web_search_tool.SCHEMA,
    shell_tool.SCHEMA,
    recall_tool.SCHEMA,
]


class UnknownToolError(Exception):
    pass


class MalformedArgumentsError(Exception):
    pass


def call_tool(name: str, arguments_json: str | None) -> str:
    if name not in TOOLS:
        raise UnknownToolError(f"Unknown tool: {name}")

    try:
        args = json.loads(arguments_json) if arguments_json else {}
    except json.JSONDecodeError as e:
        raise MalformedArgumentsError(f"Could not parse arguments for '{name}': {e}") from e

    if not isinstance(args, dict):
        args = {}

    try:
        return TOOLS[name](**args)
    except TypeError as e:
        raise MalformedArgumentsError(f"Invalid arguments for '{name}': {e}") from e


def register_mcp_tools(tools: dict, schemas: list[dict]) -> None:
    TOOLS.update(tools)
    TOOL_SCHEMAS.extend(schemas)
