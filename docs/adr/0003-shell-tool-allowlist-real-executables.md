# 0003 — Shell tool allow-list uses real executables, not shell builtins

**Status:** Accepted
**Date:** 2026-07-15

## Context
The agent's shell tool (`src/sorena/tools/shell_tool.py`) needs a strict allow-list of permitted commands, and must never invoke a real shell (`subprocess.run(..., shell=True)`) — doing so would let a model-supplied argument string smuggle in `;`, `&`, `&&`, or `|` and execute arbitrary chained commands, defeating the allow-list entirely.

The initial allow-list (`ls`, `dir`, `pwd`, `echo`, `date`, `whoami`, `git`) was written without checking the target OS. On Windows, `echo`, `dir`, `date`, and `pwd` are cmd.exe *builtins* with no standalone `.exe` — `subprocess.run([...], shell=False)` fails with `FileNotFoundError: [WinError 2]` because there is no file to execute. `ls` doesn't exist on Windows at all outside PowerShell aliases.

## Decision
The allow-list is restricted to commands that are real, standalone executables reachable on PATH without invoking a shell: `whoami`, `hostname`, `git`, `where`. Verified via `where <cmd>` before adding each one. `shell=False` stays non-negotiable — that's what makes the allow-list a real security boundary rather than a false sense of one.

## Consequences
- The tool is Windows-specific as shipped (matches the dev machine). Porting to Linux/macOS would need to re-verify the list, since `ls`/`pwd`/`date` *are* real executables there — but the allow-list should still be re-derived per-OS with `where`/`which`, not assumed.
- Rejected the alternative of wrapping builtins via `cmd /c <command>`: `cmd.exe` itself parses `&`/`&&`/`|` once invoked, which reopens exactly the injection surface `shell=False` was chosen to close. Real executables only was the simpler and strictly safer choice.
