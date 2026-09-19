"""Phase 7: bridges LangChain/LangGraph run events into Sorena's existing
trace.py sink (traces/runs.jsonl) instead of adopting LangSmith (LangChain's
own hosted tracing product) as the default -- see ADR 0014's Observability
row. LangSmith stays available as an explicit, documented opt-in
(SORENA_LANGSMITH=true sets the LANGCHAIN_TRACING_V2 env var LangSmith
itself reads), never the default -- turning it on by default would quietly
send data to a cloud service, breaking Sorena's $0/local-first invariant.
"""

import os
import time

from langchain_core.callbacks import BaseCallbackHandler

from sorena import trace

SORENA_LANGSMITH = os.getenv("SORENA_LANGSMITH", "false").lower() == "true"
if SORENA_LANGSMITH:
    os.environ["LANGCHAIN_TRACING_V2"] = "true"


class TraceCallbackHandler(BaseCallbackHandler):
    """One instance per graph run. Collects a step per LangGraph node
    (on_chain_start/end -- LangGraph wraps every node as a chain run, even
    a plain function) and writes one trace.log_run() record at the end --
    same "one record per whole run" shape Phase 6 already uses for
    sorena.agent.run()."""

    def __init__(self, user_input: str):
        self.user_input = user_input
        self.steps: list[dict] = []
        self._start = time.monotonic()

    def on_chain_start(self, serialized, inputs, **kwargs):
        name = (serialized or {}).get("name") or kwargs.get("name") or "unknown"
        if name not in ("LangGraph", "__start__"):  # skip the graph's own outer wrapper run
            self.steps.append({"type": "node", "name": name})

    def on_retriever_end(self, documents, **kwargs):
        self.steps.append({"type": "retrieval", "hits": len(documents)})

    def finish(self, final_answer: str) -> dict:
        """Call once, after app.invoke() returns, with the final reply."""
        latency_ms = (time.monotonic() - self._start) * 1000
        return trace.log_run(
            user_input=self.user_input,
            steps=self.steps,
            final_answer=final_answer,
            tokens_total=0,  # router.chat() calls litellm directly, not through a
            # LangChain-wrapped LLM -- no on_llm_end fires for it, so no token
            # count is available at this layer (telemetry.py already logs those
            # per-call; this trace is about graph/node flow, not token spend).
            latency_ms=latency_ms,
            hops=len(self.steps),
        )
