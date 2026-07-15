from sorena import router
from sorena.memory import ConversationMemory
from sorena.tools import TOOL_SCHEMAS, call_tool
from sorena.tools.registry import UnknownToolError

MAX_HOPS = 8


class MaxHopsExceededError(Exception):
    pass


def run(user_message: str, memory: ConversationMemory | None = None) -> str:
    memory = memory or ConversationMemory()
    memory.add({"role": "user", "content": user_message})

    for _ in range(MAX_HOPS):
        response = router.chat(memory.messages, tools=TOOL_SCHEMAS)

        if isinstance(response, str):
            memory.add({"role": "assistant", "content": response})
            return response

        # normalize to a plain OpenAI-shape dict before appending -- the raw
        # provider Message object can carry provider-specific fields (e.g.
        # Gemini's `images`) that a *different* provider rejects on the next
        # hop, breaking the provider-agnostic chain.
        memory.add(
            {
                "role": "assistant",
                "content": response.content,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                    }
                    for tc in response.tool_calls
                ],
            }
        )

        for tool_call in response.tool_calls:
            name = tool_call.function.name
            try:
                result = call_tool(name, tool_call.function.arguments)
            except UnknownToolError as e:
                result = f"Error: {e}"
            except Exception as e:
                result = f"Error running tool '{name}': {e}"

            memory.add(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": str(result),
                }
            )

    raise MaxHopsExceededError(f"Agent did not resolve in {MAX_HOPS} hops")
