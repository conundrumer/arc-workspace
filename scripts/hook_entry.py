"""The entry of a command hook that `.claude/settings.json` registers: it
reads the hook input from stdin as JSON and hands it to the hook's action.

The entry fails open: where the hook's action raises, it stops nothing,
and it prints the hook's failure text and the error on stderr. A hook runs
in a fresh process with `scripts/` on the path, so this module imports only
the standard library.

A PreToolUse hook runs two parts, each of which fails open alone: its check,
which gives the reason to deny the call or None, and the update of the
caller's documents, which gives the text the caller gets in its context or
None (`reader_commits.reader_update`). Claude Code reads one output of a
hook, and puts its `additionalContext` in the caller's context whether or
not the output denies the call, so the entry prints one output that holds
both parts. The update records the delivery only where its block ends
without an error, after the output is printed.

What the entry runs for every hook stands in this docstring alone, and in no
hook's docstring."""

import json
import sys
from collections.abc import Callable
from contextlib import AbstractContextManager
from typing import Any

type Hook = dict[str, Any]

CHECK_FAILED = "allowed: the check failed"
"""The failure text of a PreToolUse hook, whose call goes ahead where its
check fails."""

UPDATE_FAILED = "gave no update of the caller's documents"
"""The failure text of a PreToolUse hook whose update fails."""


def _failed(hook: str, failure: str, e: Exception) -> None:
    print(f"{hook}: {failure}: {type(e).__name__}: {e}", file=sys.stderr)


def run_part[T](hook: str, failure: str, part: Callable[[], T]) -> T | None:
    """What `part` of the hook `hook` gives, or None where it raises, with
    the failure text `failure` and the error on stderr."""
    try:
        return part()
    except Exception as e:
        _failed(hook, failure, e)
        return None


def run_hook(hook: str, failure: str, act: Callable[[Hook], None]) -> int:
    run_part(hook, failure, lambda: act(json.loads(sys.stdin.read())))
    return 0


def _give(reason: str | None, context: str | None) -> None:
    out: dict[str, str] = {}
    if reason is not None:
        out |= {"permissionDecision": "deny", "permissionDecisionReason": reason}
    if context is not None:
        out["additionalContext"] = context
    if out:
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse", **out}}), flush=True)


def run_pre_tool_use(
        hook: str, check: Callable[[Hook], str | None],
        update: Callable[[Hook], AbstractContextManager[str | None]]) -> int:
    """Run the PreToolUse hook `hook` on the input on stdin: `check` gives
    the reason to deny the call, and `update` the text the caller gets in
    its context, inside a block that the printed output ends."""
    data = run_part(hook, CHECK_FAILED, lambda: json.loads(sys.stdin.read()))
    if data is None:
        return 0
    reason = run_part(hook, CHECK_FAILED, lambda: check(data))
    given = False
    try:
        with update(data) as context:
            given = True
            _give(reason, context)
    except Exception as e:
        _failed(hook, UPDATE_FAILED, e)
        if not given:
            _give(reason, None)
    return 0
