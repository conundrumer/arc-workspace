"""PreToolUse hook on Agent: gives the caller the diff of its documents
since the commit it read them at (`reader_commits.reader_update`)."""

import sys
from typing import Any

from hook_entry import run_pre_tool_use

HOOK = "reader_update_hook"


def check(hook: dict[str, Any]) -> str | None:
    """No reason to deny the Agent call `hook` gives."""
    return None


def main() -> int:
    from reader_commits import reader_update

    return run_pre_tool_use(HOOK, check, reader_update)


if __name__ == "__main__":
    sys.exit(main())
