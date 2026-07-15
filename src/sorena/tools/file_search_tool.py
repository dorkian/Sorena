from pathlib import Path

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
    matches = [str(p) for p in Path(root).glob(pattern)]
    if not matches:
        return "No files matched."
    return "\n".join(matches[:50])
