from sorena.long_term_memory import LongTermMemory

SCHEMA = {
    "type": "function",
    "function": {
        "name": "recall_memory",
        "description": (
            "Search past conversation history across all sessions for relevant prior turns, "
            "e.g. 'what did I ask about Docker last week'. Hybrid keyword + semantic search."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "What to search for"},
                "top_k": {"type": "integer", "description": "Max results to return. Default 5."},
            },
            "required": ["query"],
        },
    },
}

_memory: LongTermMemory | None = None


def _get_memory() -> LongTermMemory:
    global _memory
    if _memory is None:
        _memory = LongTermMemory()
    return _memory


def run(query: str, top_k: int = 5) -> str:
    results = _get_memory().search(query, top_k=top_k)
    if not results:
        return "No relevant past turns found."
    return "\n".join(f"[{r['timestamp']}] {r['role']}: {r['content']}" for r in results)
