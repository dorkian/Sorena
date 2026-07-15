import os

import requests

SCHEMA = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": "Search the web for current information.",
        "parameters": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    },
}


def run(query: str) -> str:
    api_key = os.environ["TAVILY_API_KEY"]
    resp = requests.post(
        "https://api.tavily.com/search",
        json={"api_key": api_key, "query": query, "max_results": 3},
        timeout=10,
    )
    resp.raise_for_status()
    results = resp.json()["results"]
    return "\n\n".join(f"{r['title']}: {r['content']}" for r in results)
