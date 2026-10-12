"""SubagentStop hook, and PreToolUse hook on SubagentHandback: blocks the
stop, or denies the SubagentHandback call, of an operator subagent where the
result of the last call of `operate.py next` in its own transcript is not
the text of its final reply (`printing.printed_reply`), or prints a
SendMessage call (`printing.printed_send`), which the operator has still to
make, and the reason tells it to run `next` again. An operator launcher
is held the same way to the result of `operate.py relay`
(`context_bound_hook.ACTIONS`), which also lets it stop where that result
is the end of its turn (`printing.printed_end_turn`).

The SubagentHandback call is held to the same condition as the stop, so no
reader of agent signs takes a handback as the operator's end while the stop
would still be blocked.

A blocked stop or a denied call is recorded with the id of the operator's
last call of `next`, in a file named by its agent id under `STOPS` of its
session directory, and neither a stop nor a call is blocked again while
that call is still the last: a fault in `next` then cannot hold the
operator in a loop of blocks, and a handback that passes is followed by a
stop that passes. Where the hook cannot tell the agent type, or the
transcript holds no result of `next`, it lets the stop or the call pass and
says why on stderr."""

import sys
from contextlib import nullcontext
from typing import Any

from hook_entry import not_registered, run_pre_tool_use, run_subagent_stop
from printed_launch_hook import first_at, operator_next

HOOK = "operator_stop_hook"
STOPS = "operator-stops"
PRE_TOOL_USE = "pre-tool-use"


def stop_reason(command: str) -> str:
    from controlled_markdown import mctx

    return mctx(
        "Blocked: the last result of `{command}` is not your final reply. Run "
        "`{command}` again, and make the call it prints."
    ).format(command=command)


def check(hook: dict[str, Any]) -> str | None:
    """The reason to block the stop, or deny the SubagentHandback call,
    `hook` gives where its agent is an operator that `next` has not given
    its final reply, and None otherwise."""
    from operations.printing import printed_end_turn, printed_reply, printed_send

    tool = hook.get("tool_name")
    if tool is not None and tool != "SubagentHandback":
        raise not_registered("SubagentHandback", "tool", tool)
    caller = operator_next(hook, HOOK)
    if caller is None:
        return None
    agent, command, found = caller.agent, caller.command, caller.found
    if found is None:
        print(f"{HOOK}: allowed: the transcript of {agent} holds no result of `next`",
              file=sys.stderr)
        return None
    call, result = found
    if printed_end_turn(result) or (printed_reply(result) and printed_send(result) is None):
        return None
    if not first_at(hook, STOPS, agent, call):
        print(f"{HOOK}: allowed: a stop or a handback was blocked at call {call} of `next`, "
              "and the operator made no call of `next` since", file=sys.stderr)
        return None
    return stop_reason(command)


def main() -> int:
    args = sys.argv[1:]
    if not args:
        return run_subagent_stop(HOOK, check)
    if args == [PRE_TOOL_USE]:
        return run_pre_tool_use(HOOK, check, lambda hook: nullcontext(None))
    raise SystemExit(f"{HOOK}: usage: operator_stop_hook.py [{PRE_TOOL_USE}]")


if __name__ == "__main__":
    sys.exit(main())
