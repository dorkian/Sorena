# 0011 — Cross-agent delegation tool imports `agent` lazily, not at module load

**Status:** Accepted

## Context
`sorena.tools.delegation_tool.ask_researcher()` lets one specialist (Coach)
call another (Researcher) as a tool, running Researcher's own `agent.run()`
loop and returning its reply (docs/specs/sorena-multi-agent-plan.md §2). That
function needs `sorena.agent`.

But `sorena/agent.py` itself does `from sorena.tools import TOOL_SCHEMAS,
call_tool` to build its tool-calling loop, and `sorena/tools/registry.py`
imports every tool module -- including `delegation_tool` -- to register it.
A top-level `from sorena import agent` in `delegation_tool.py` closes that
loop: `agent` -> `tools` -> `registry` -> `delegation_tool` -> `agent`.

Whether this actually raises `ImportError` depends on which module some
other code imports *first* -- if `sorena.agent` happens to finish loading
before anything reaches `sorena.tools`, the partially-initialized module is
already complete by the time it's needed and nothing breaks; if `sorena.tools`
is the first thing imported, `sorena.tools.TOOL_SCHEMAS` doesn't exist yet
when `agent.py` asks for it, and the import fails. That's exactly what
happened: `sorena.agents.orchestrator` (which imports `agent` before any
specialist) worked fine, but a test importing `sorena.tools.delegation_tool`
directly did not.

## Decision
`delegation_tool.py` imports `sorena.agent` inside `ask_researcher()`, not at
module level. By the time the function actually runs, both modules have long
since finished importing, so the deferred import always succeeds regardless
of which module a caller reaches first.

## Consequences
- Import order no longer matters for this module -- the previous behavior
  (working or not depending on the entry point) was a latent bug, not
  something to preserve.
- Any future "specialist calls another specialist as a tool" function should
  follow the same pattern: import `sorena.agent` inside the function body,
  not at the top of the tool module.
- The alternative -- restructuring `agent.py` to not need `sorena.tools` at
  import time -- would remove the cycle at its root, but touches the whole
  tool-loading path for a problem the one-line deferred import already
  solves completely.
