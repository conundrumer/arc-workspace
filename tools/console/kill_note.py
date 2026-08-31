"""PreToolUse hook for console workers: answer a shell kill with the way to
stop a background task.

The hook is the boundary: permission mode auto lets a repo-local kill
through. TaskStop's name is deferred, so a session that reaches for the shell
has no reason to look for the tool.
"""
import json
import re
import sys

KILL = re.compile(r"\b(pkill|killall)\b")

NOTE = """Stop a background task with TaskStop and the task ID from its launch result.
TaskStop is deferred: load it first with ToolSearch "select:TaskStop".
A shell kill leaves the harness tracking the task.
Nothing else here is yours to kill: put it in your report instead."""


def main() -> None:
    try:
        ev = json.load(sys.stdin)
    except (ValueError, OSError):
        return
    if ev.get("tool_name") != "Bash":
        return
    if KILL.search(str(ev.get("tool_input", {}).get("command", ""))):
        print(NOTE, file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
