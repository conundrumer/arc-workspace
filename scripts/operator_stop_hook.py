"""SubagentStop hook: blocks the stop of an operator subagent where the
result of the last call of `operate.py next` in its own transcript is not
the text of its final reply (`printing.printed_reply`), or prints a
SendMessage call (`printing.printed_send`), which the operator has still to
make, and the reason tells it to run `next` again. An operator launcher
is held the same way to the result of `operate.py relay`
(`printed_launch_hook.ACTIONS`).

A blocked stop is recorded with the id of the operator's last call of
`next`, in a file named by its agent id under `STOPS` of its session
directory, and a stop is not blocked again while that call is still the
last: a fault in `next` then cannot hold the operator in a loop of blocks.
Where the hook cannot tell the agent type, or the transcript holds no
result of `next`, it lets the stop pass and says why on stderr."""

import sys
from typing import Any

from hook_entry import run_subagent_stop
from printed_launch_hook import operator_next

HOOK = "operator_stop_hook"
STOPS = "operator-stops"


def stop_reason(command: str) -> str:
    from controlled_markdown import mctx

    return mctx(
        "Blocked: the last result of `{command}` is not your final reply. Run "
        "`{command}` again, and make the call it prints."
    ).format(command=command)


def check(hook: dict[str, Any]) -> str | None:
    """The reason to block the stop `hook` gives where its agent is an
    operator that `next` has not given its final reply, and None
    otherwise."""
    from operations.printing import printed_reply, printed_send
    from run_reads import hook_session

    caller = operator_next(hook, HOOK)
    if caller is None:
        return None
    agent, command, found = caller
    if found is None:
        print(f"{HOOK}: allowed: the transcript of {agent} holds no result of `next`",
              file=sys.stderr)
        return None
    call, result = found
    if printed_reply(result) and printed_send(result) is None:
        return None
    record = hook_session(hook) / STOPS / agent
    if record.exists() and record.read_text() == call:
        print(f"{HOOK}: allowed: the stop was blocked at call {call} of `next`, "
              "and the operator made no call of `next` since", file=sys.stderr)
        return None
    record.parent.mkdir(parents=True, exist_ok=True)
    record.write_text(call)
    return stop_reason(command)


def main() -> int:
    return run_subagent_stop(HOOK, check)


if __name__ == "__main__":
    sys.exit(main())
