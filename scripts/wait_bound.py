"""The denial `pending_wait_hook` gives a subagent's foreground Bash call
whose `timeout` is outside the foreground bounds, and the match of the
upper bound denial in a call's result that the reads of an operator's
calls make."""

import re

from operations.constants import FOREGROUND_MS


def bound_reason(timeout: str) -> str:
    """The reason the hook gives where a call's timeout, `timeout`, is over
    `FOREGROUND_MS`."""
    from controlled_markdown import mctx

    return "\n".join([
        mctx("Blocked: this foreground Bash call has a timeout of {timeout} ms, over the "
             "bound of {bound} ms."),
        mctx("Run the same call again with a timeout of at most {bound} ms."),
    ]).format(timeout=timeout, bound=FOREGROUND_MS)


def short_reason(action: str, timeout: str | None) -> str:
    """The denial for an operation whose foreground timeout is too short."""
    from controlled_markdown import mctx
    from operations.constants import LIMIT_SECONDS

    given = mctx("not set") if timeout is None else mctx("{timeout} ms").format(timeout=timeout)
    return "\n".join([
        mctx("Blocked: this foreground Bash call runs `scripts/operate.py {action}`, "
             "which can block for up to {seconds} s, and its timeout is {given}, so "
             "the harness can move the call to the background before it ends."),
        mctx("Run the same call again with a timeout of {bound} ms."),
    ]).format(action=action, seconds=LIMIT_SECONDS, given=given, bound=FOREGROUND_MS)


def bound_denied(result: str) -> bool:
    """Whether `result`, a call's result, holds the reason `bound_reason`
    gives, with any timeout."""
    hole = "\0"
    parts = bound_reason(hole).split(hole)
    return re.search(r"\d+(?:\.\d+)?".join(map(re.escape, parts)), result) is not None
