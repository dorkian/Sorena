import time
from datetime import UTC, datetime

from sorena import router, trace
from sorena.long_term_memory import LongTermMemory
from sorena.memory import ConversationMemory
from sorena.tools import TOOL_SCHEMAS, call_tool
from sorena.tools.registry import UnknownToolError

MAX_HOPS = 8

# Trace step results are truncated before writing to traces/runs.jsonl so a
# single verbose tool result (e.g. a long web-search dump) doesn't balloon
# the trace file -- the full result is still what the LLM sees, just not
# what gets persisted for observability.
TRACE_RESULT_MAX_CHARS = 500


class MaxHopsExceededError(Exception):
    pass


def run(
    user_message: str,
    memory: ConversationMemory | None = None,
    long_term: LongTermMemory | None = None,
    system_prompt: str | None = None,
    tool_names: list[str] | None = None,
    _eval_case: str | None = None,
    _eval_case_type: str | None = None,
) -> str:
    memory = memory or ConversationMemory()
    long_term = long_term or LongTermMemory()
    start = time.perf_counter()
    steps: list[dict] = []

    if system_prompt and not memory.messages:
        memory.add({"role": "system", "content": system_prompt})

    # least-privilege tool scoping: a specialist agent only sees (and can
    # call) the tools listed in tool_names -- omit it to keep today's
    # behavior of exposing every registered tool.
    tool_schemas = TOOL_SCHEMAS
    allowed_tools = None
    if tool_names is not None:
        tool_schemas = [s for s in TOOL_SCHEMAS if s["function"]["name"] in tool_names]
        allowed_tools = set(tool_names)

    def log_trace(final_answer: str | None, hops: int) -> None:
        trace.log_run(
            user_input=user_message,
            steps=steps,
            final_answer=final_answer,
            tokens_total=memory.token_count(),
            latency_ms=(time.perf_counter() - start) * 1000,
            hops=hops,
            eval_case=_eval_case,
            eval_case_type=_eval_case_type,
        )

    memory.add({"role": "user", "content": user_message})
    long_term.add_turn("user", user_message, datetime.now(UTC).isoformat())

    for hop in range(MAX_HOPS):
        response = router.chat(memory.messages, tools=tool_schemas)

        if isinstance(response, str):
            memory.add({"role": "assistant", "content": response})
            long_term.add_turn("assistant", response, datetime.now(UTC).isoformat())
            log_trace(response, hop + 1)
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
            if allowed_tools is not None and name not in allowed_tools:
                result = f"Error: tool '{name}' is not available to this agent"
            else:
                try:
                    result = call_tool(name, tool_call.function.arguments)
                except UnknownToolError as e:
                    result = f"Error: {e}"
                except Exception as e:
                    result = f"Error running tool '{name}': {e}"

            steps.append(
                {
                    "tool": name,
                    "args": tool_call.function.arguments,
                    "result": str(result)[:TRACE_RESULT_MAX_CHARS],
                }
            )
            memory.add(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": str(result),
                }
            )

    log_trace(None, MAX_HOPS)
    raise MaxHopsExceededError(f"Agent did not resolve in {MAX_HOPS} hops")
