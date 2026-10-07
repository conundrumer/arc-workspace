"""The entry of a command hook that `.claude/settings.json` registers: it
reads the hook input from stdin as JSON and hands it to the hook's action.

The entry fails open. Where the input is not JSON, or the action raises, it
prints the hook's name, the hook's own message and the exception on stderr,
and exits 0. A hook runs in a fresh process with `scripts/` on the path, so
this module imports only the standard library."""

import json
import sys
from collections.abc import Callable
from typing import Any


def run_hook(hook: str, failure: str,
             act: Callable[[dict[str, Any]], None]) -> int:
    """Hand the hook input on stdin to `act`, and give the exit code: 0.
    Where reading the input or `act` raises, print `<hook>: <failure>:`
    and the exception on stderr."""
    try:
        act(json.loads(sys.stdin.read()))
    except Exception as e:
        print(f"{hook}: {failure}: {type(e).__name__}: {e}", file=sys.stderr)
    return 0
