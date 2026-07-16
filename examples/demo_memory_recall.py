"""End-to-end long-term recall demo: seed a past session's turn directly into
long-term memory (with a real "last week" timestamp, simulating a prior
session), then ask the agent a question only `recall_memory` can answer --
no manual intervention, no hint that the tool exists."""

from datetime import UTC, datetime, timedelta

from sorena import agent
from sorena.long_term_memory import LongTermMemory

memory = LongTermMemory()
last_week = (datetime.now(UTC) - timedelta(days=7)).isoformat()
memory.add_turn(
    "user",
    "I need to renew my passport before my trip to Japan in September.",
    last_week,
)
memory.close()

prompt = "What did I ask you about my passport last week?"
print(f"User: {prompt}\n")
reply = agent.run(prompt)
print(f"Agent: {reply}")
