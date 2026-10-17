"""The entry of a command hook that `.claude/settings.json` registers: it
reads the hook input from stdin as JSON and hands it to the hook's action.

The entry fails open: where the hook's action raises, it stops nothing,
and it prints the hook's failure text and the error on stderr. A hook runs
in a fresh process with `scripts/` on the path, so this module imports only
the standard library.

A PreToolUse hook runs two parts, each of which fails open alone: its check,
which gives the reason to deny the call or None, and the update of the
caller's documents, which gives the text the caller gets in its context or
None (`reader_delivery.reader_update`). Claude Code reads one output of a
hook, and puts its `additionalContext` in the caller's context whether or
not the output denies the call, so the entry prints one output that holds
both parts. Claude Code puts that text in the caller's context after the
call has run, so a call that gets an update is denied, with the update's
reason after the check's, and the caller makes it again by its updated
documents.

A PostToolUse, a PostToolUseFailure or a UserPromptSubmit hook runs the
update alone (`run_context`), and prints its text with no decision. Claude
Code puts that text in the caller's context with the call's result, or
with the user's prompt or a task notification. `reader_delivery` gives
what a PreToolUse hook gives after such a delivery.

The update records the delivery only where its block ends without an
error, after the output is printed.

What the entry runs for every hook stands in this docstring alone, and in no
hook's docstring."""

import json
import sys
import time
from collections.abc import Callable
from contextlib import AbstractContextManager, nullcontext
from typing import Any, NamedTuple

type Hook = dict[str, Any]

STARTED = time.time()
"""The time this process imported the entry, which each hook script does
before its other imports and its check."""


class Update(NamedTuple):
    """The text the caller of a hook gets in its context, empty where it gets
    none, and the reason a PreToolUse hook denies its call for it."""

    text: str
    reason: str

CHECK_FAILED = "allowed: the check failed"
"""The failure text of a PreToolUse or a SubagentStop hook, whose call or
stop goes ahead where its check fails."""

UPDATE_FAILED = "gave no update of the caller's documents"
"""The failure text of a hook whose update fails."""


def not_registered(on: str, kind: str, given: object) -> ValueError:
    """The error a hook registered on `on` raises on input whose `kind`,
    `tool` or `event`, is `given`."""
    return ValueError(f"the hook is registered on {on}, and the input "
                      f"gives {kind} `{given}`")


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


def run_subagent_stop(hook: str, check: Callable[[Hook], str | None]) -> int:
    """Run the SubagentStop hook `hook` on the input on stdin: `check` gives
    the reason to block the stop, or None to let it pass."""
    reason = run_part(hook, CHECK_FAILED, lambda: check(json.loads(sys.stdin.read())))
    if reason is not None:
        print(json.dumps({"decision": "block", "reason": reason}), flush=True)
    return 0


def _give(reason: str | None, update: Update | None) -> None:
    out: dict[str, str] = {}
    if update is not None:
        reason = update.reason if reason is None else f"{reason}\n{update.reason}"
        if update.text:
            out["additionalContext"] = update.text
    if reason is not None:
        out |= {"permissionDecision": "deny", "permissionDecisionReason": reason}
    if out:
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse", **out}}), flush=True)


def no_update(_: Hook) -> AbstractContextManager[Update | None]:
    return nullcontext(None)


def run_pre_tool_use(
        hook: str, check: Callable[[Hook], str | None],
        update: Callable[[Hook], AbstractContextManager[Update | None]] = no_update) -> int:
    """Run the PreToolUse hook `hook` on the input on stdin: `check` gives
    the reason to deny the call, and `update` the caller's update, inside a
    block that the printed output ends."""
    data = run_part(hook, CHECK_FAILED, lambda: json.loads(sys.stdin.read()))
    if data is None:
        return 0
    reason = run_part(hook, CHECK_FAILED, lambda: check(data))
    given = False
    try:
        with update(data) as given_update:
            given = True
            _give(reason, given_update)
    except Exception as e:
        _failed(hook, UPDATE_FAILED, e)
        if not given:
            _give(reason, None)
    return 0


def run_context(
        hook: str,
        update: Callable[[Hook], AbstractContextManager[Update | None]]) -> int:
    """Run the hook `hook`, on an event whose output gives context with no
    decision, on the input on stdin: `update` gives the caller's update,
    inside a block that the printed output ends."""
    data = run_part(hook, UPDATE_FAILED, lambda: json.loads(sys.stdin.read()))
    if data is None:
        return 0
    try:
        with update(data) as given:
            if given is not None:
                print(json.dumps({"hookSpecificOutput": {
                    "hookEventName": data["hook_event_name"],
                    "additionalContext": given.text}}), flush=True)
    except Exception as e:
        _failed(hook, UPDATE_FAILED, e)
    return 0
