"""Multi-step tool-calling demo: one prompt requiring two sequential tool calls,
resolved end-to-end by the ReAct loop with no manual intervention."""

from sorena import agent

prompt = (
    "What is the current UTC time, and search the web for who won the most "
    "recent Super Bowl? Use tools for both, then summarize both answers."
)

print(f"User: {prompt}\n")
reply = agent.run(prompt)
print(f"Agent: {reply}")
