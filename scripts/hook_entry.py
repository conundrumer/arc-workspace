"""The entry of a command hook that `.claude/settings.json` registers: it
reads the hook input from stdin as JSON and hands it to the hook's action.

The entry fails open: where the hook's action raises, it stops nothing,
and it prints the hook's failure text and the error on stderr. A hook runs
in a fresh process with `scripts/` on the path, so this module imports only
the standard library."""

import json
import sys
from collections.abc import Callable
from typing import Any

CHECK_FAILED = "allowed: the check failed"
"""The failure text of a PreToolUse hook, whose call goes ahead where its
check fails."""


def run_hook(hook: str, failure: str,
             act: Callable[[dict[str, Any]], None]) -> int:
    try:
        act(json.loads(sys.stdin.read()))
    except Exception as e:
        print(f"{hook}: {failure}: {type(e).__name__}: {e}", file=sys.stderr)
    return 0
