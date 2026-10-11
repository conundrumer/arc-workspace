"""PreToolUse hook on SendMessage: denies the SendMessage call of an
operator subagent where the result of the last call of `operate.py next` in
its own transcript prints no message (`printing.printed_send`), or prints
one to another recipient, or where the call's message, without its fence
lines, does not open with the printed message. Free text may follow the
printed message, and keys of the call other than `to` and `message` are
not compared. An operator launcher is held the same way to the result of
`operate.py relay` (`context_bound_hook.ACTIONS`). Where the hook cannot
tell the caller's agent type, it allows the call and says why on stderr."""

import sys
from contextlib import nullcontext
from typing import Any

from hook_entry import not_registered, run_pre_tool_use
from printed_launch_hook import operator_next

HOOK = "printed_send_hook"


def no_send_reason(command: str) -> str:
    from controlled_markdown import mctx

    return mctx(
        "Blocked: the last result of `{command}` gives no whole SendMessage "
        "call. Send only the message that `next` prints, and run `next` with "
        "no pipe."
    ).format(command=command)


def differ_reason(command: str, to: str, message: str) -> str:
    from controlled_markdown import mctx
    from operations.printing import send_text

    head = mctx(
        "Blocked: this SendMessage call differs from the one the last result "
        "of `{command}` prints. Make the call again with the printed `to`, "
        "and a message that opens with the printed message:"
    ).format(command=command)
    return "\n".join([head, send_text(to, message)])


def check(hook: dict[str, Any]) -> str | None:
    """The reason to deny the SendMessage call `hook` gives where its caller
    is an operator and the call is not the message `next` last printed to
    it, and None otherwise."""
    from operations.printing import printed_send, unfenced

    tool, inp = hook["tool_name"], hook["tool_input"]
    if tool != "SendMessage":
        raise not_registered("SendMessage", "tool", tool)
    caller = operator_next(hook, HOOK)
    if caller is None:
        return None
    _, command, found = caller
    printed = None if found is None else printed_send(found[1])
    if printed is None:
        return no_send_reason(command)
    to, message = printed
    if inp.get("to") == to and unfenced(str(inp.get("message", ""))).startswith(message):
        return None
    return differ_reason(command, to, message)


def main() -> int:
    return run_pre_tool_use(HOOK, check, lambda hook: nullcontext(None))


if __name__ == "__main__":
    sys.exit(main())
