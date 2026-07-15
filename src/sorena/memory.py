import litellm

from sorena import router

TOKEN_BUDGET = 4000
KEEP_RECENT_MESSAGES = 4


class ConversationMemory:
    """Rolling message window. Once total tokens exceed the budget, the oldest
    messages are collapsed into one LLM-generated summary, keeping only the
    summary plus the most recent messages."""

    def __init__(self, token_budget: int = TOKEN_BUDGET):
        self.token_budget = token_budget
        self.messages: list[dict] = []

    def add(self, message: dict) -> None:
        self.messages.append(message)
        self._compress_if_needed()

    def token_count(self) -> int:
        return litellm.token_counter(model="gpt-4", messages=self.messages)

    def _compress_if_needed(self) -> None:
        if self.token_count() <= self.token_budget:
            return
        if len(self.messages) <= KEEP_RECENT_MESSAGES:
            return  # nothing old enough to summarize yet

        keep_recent = self.messages[-KEEP_RECENT_MESSAGES:]
        to_summarize = self.messages[:-KEEP_RECENT_MESSAGES]

        transcript = "\n".join(f"{m['role']}: {m.get('content') or ''}" for m in to_summarize)
        prompt = (
            "Summarize this conversation concisely, preserving key facts and decisions:\n\n"
            f"{transcript}"
        )
        summary = router.chat([{"role": "user", "content": prompt}])

        summary_message = {"role": "system", "content": f"Earlier conversation summary: {summary}"}
        self.messages = [summary_message] + keep_recent
