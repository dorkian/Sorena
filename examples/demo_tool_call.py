"""One hardcoded tool, one manual round-trip: prove the tool-calling mechanic
before building the loop."""

from datetime import UTC, datetime

from sorena import router

TIME_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "get_current_time",
        "description": "Get the current UTC date and time.",
        "parameters": {"type": "object", "properties": {}},
    },
}


def get_current_time() -> str:
    return datetime.now(UTC).isoformat()


messages = [{"role": "user", "content": "What is the current UTC time? Use the tool."}]

response = router.chat(messages, tools=[TIME_TOOL_SCHEMA])

if isinstance(response, str):
    print(f"Model answered directly (no tool call): {response}")
else:
    tool_call = response.tool_calls[0]
    print(f"Model requested tool: {tool_call.function.name}({tool_call.function.arguments})")

    result = get_current_time()

    messages.append(response)
    messages.append(
        {
            "role": "tool",
            "tool_call_id": tool_call.id,
            "content": result,
        }
    )

    final = router.chat(messages)
    print(f"\nFinal answer: {final}")
