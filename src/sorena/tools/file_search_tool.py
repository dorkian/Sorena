import os
from pathlib import Path

# Default base is the Sorena repo root -- overridable via env var, same
# escape-hatch convention as SORENA_CV_PATH (jobscout_tool.py) and
# SORENA_VAULT_SESSIONS_PATH (vault_tool.py). Without this, search_files
# could enumerate any directory on disk -- real recon surface for a
# tool-calling LLM steered by injected content (see docs/specs/
# security-hardening-2026-07-18.md req 2).
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
BASE_DIR = Path(os.getenv("SORENA_FILE_SEARCH_ROOT", str(_REPO_ROOT))).resolve()

SCHEMA = {
    "type": "function",
    "function": {
        "name": "search_files",
        "description": "Search for files by name (glob pattern) under a root directory.",
        "parameters": {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Glob pattern, e.g. '**/*.py'"},
                "root": {"type": "string", "description": "Root directory to search. Default cwd."},
            },
            "required": ["pattern"],
        },
    },
}


def run(pattern: str, root: str = ".") -> str:
    root_path = Path(root)
    resolved_root = root_path.resolve() if root_path.is_absolute() else (BASE_DIR / root).resolve()
    if not resolved_root.is_relative_to(BASE_DIR):
        return f"Refused: '{root}' resolves outside the allowed search root ({BASE_DIR})."

    matches = [str(p) for p in resolved_root.glob(pattern)]
    if not matches:
        return "No files matched."
    return "\n".join(matches[:50])
