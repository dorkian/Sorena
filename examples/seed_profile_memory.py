"""Seed long-term memory with Ash's profile facts so every agent's
recall_memory tool already knows them -- "search a job for me" or "what
should I learn next" should hit these without Ash re-explaining.

Rerunnable: each fact is skipped if its exact content is already stored.

    uv run python examples/seed_profile_memory.py
"""

from datetime import datetime

from sorena.long_term_memory import LongTermMemory

FACTS = [
    # -- job search (JobScout) --
    "My target roles are AI Engineer, AI-Native Developer, and Tech Lead.",
    "I am based in Italy. Remote work is preferred, hybrid is acceptable, and "
    "a fully onsite role outside Italy is a dealbreaker.",
    "I speak English and Italian.",
    "My strongest skills are Python, FastAPI, React, TypeScript, n8n automation, "
    "MCP development, agent systems, RAG, LLM evals, Docker, and PostgreSQL.",
    "I built Sorena, a local-first voice AI assistant: a hand-written ReAct agent "
    "loop, MCP client and server, a hybrid RAG memory (SQLite FTS5 plus embeddings "
    "with reciprocal rank fusion), a full voice pipeline (openWakeWord, "
    "faster-whisper, silero-vad, Piper), a two-tier eval suite with tracing, and a "
    "multi-agent orchestrator with six specialists.",
    "I published code-graph-mcp, an MCP server that indexes codebases into a knowledge graph.",
    "I run side businesses: a real-estate lead tool, an n8n workflow template "
    "business, and an affiliate site. I am also building toward being a "
    "creator/influencer.",
    # -- working preferences (all agents) --
    "I am cost-conscious: prefer free and open-source tools, minimize API spend, "
    "and flag when a paid service is the only option.",
    "I prefer local, self-hosted, privacy-first solutions over cloud services.",
    "I prefer automation over manual steps, and concise explanations without filler.",
    "My knowledge base is an Obsidian vault; session notes and learnings go there.",
    "My dev machine runs Windows 11 and is not spec'd for local LLM inference, "
    "which is why Sorena uses Groq and Gemini free tiers instead of Ollama.",
    # -- learning path (Coach) --
    "My learning path: currently learning LangGraph, improving wake-word model "
    "training (my custom hey_sorena model has weak recall, 0.468, and needs "
    "retraining with more samples and steps), and AI governance and security as "
    "the next planned Sorena phase.",
    "My learning style: spec-first, build from scratch before adopting frameworks, "
    "learn by shipping a working project per topic, and write an ADR when "
    "something breaks.",
    "Skills I have already learned by building Sorena, phase by phase: modern "
    "Python project setup (uv, ruff, pytest, CI), multi-provider LLM routing with "
    "fallback and rate-limit handling, ReAct agent loops and tool registries, MCP "
    "on both the client and server side, voice pipelines, hybrid RAG retrieval, "
    "and LLM eval suites with regression tracing.",
]


def main() -> None:
    memory = LongTermMemory()
    existing = {row[0] for row in memory.conn.execute("SELECT content FROM turns").fetchall()}
    added = 0
    for fact in FACTS:
        if fact in existing:
            continue
        memory.add_turn("user", fact, datetime.now().isoformat())
        added += 1
    print(f"Seeded {added} new facts ({len(FACTS) - added} already present).")

    for query in ("search a job for me", "what should I learn next"):
        hits = memory.search(query, top_k=3)
        print(f"\nrecall check -- {query!r}:")
        for h in hits:
            print(f"  - {h['content'][:90]}")
    memory.close()


if __name__ == "__main__":
    main()
