import shlex
import subprocess

# must be real standalone executables, not shell builtins (echo/dir/date/pwd/ls
# have no standalone .exe on Windows) -- shell=False never invokes cmd.exe, which
# is what keeps this immune to `;`/`&`/`&&` injection.
ALLOWED_COMMANDS = {"whoami", "hostname", "git", "where"}

_ALLOWED_LIST = ", ".join(sorted(ALLOWED_COMMANDS))

SCHEMA = {
    "type": "function",
    "function": {
        "name": "run_shell_command",
        "description": f"Run a shell command. Only these commands are permitted: {_ALLOWED_LIST}.",
        "parameters": {
            "type": "object",
            "properties": {"command": {"type": "string"}},
            "required": ["command"],
        },
    },
}


class DisallowedCommandError(Exception):
    pass


def run(command: str) -> str:
    parts = shlex.split(command)
    if not parts or parts[0] not in ALLOWED_COMMANDS:
        raise DisallowedCommandError(f"Command not on allow-list: {command!r}")

    result = subprocess.run(parts, capture_output=True, text=True, timeout=10)
    return result.stdout or result.stderr or "(no output)"
