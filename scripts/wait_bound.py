"""The denial `pending_wait_hook` gives a subagent's foreground Bash call
whose `timeout` is over `FOREGROUND_MS` ms, and the match of it in a call's
result that the reads of an operator's calls make."""

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


def bound_denied(result: str) -> bool:
    """Whether `result`, a call's result, holds the reason `bound_reason`
    gives, with any timeout."""
    hole = "\0"
    parts = bound_reason(hole).split(hole)
    return re.search(r"\d+(?:\.\d+)?".join(map(re.escape, parts)), result) is not None
