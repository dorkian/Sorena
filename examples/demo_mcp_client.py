from sorena import agent
from sorena.mcp_client import load_mcp_tools
from sorena.tools.registry import register_mcp_tools

register_mcp_tools(*load_mcp_tools())

prompt = (
    "Use the code-graph tool to summarize the Sorena repo -- how many files "
    "and packages does it contain?"
)

print(f"User: {prompt}\n")
reply = agent.run(prompt)
print(f"Agent: {reply}")
