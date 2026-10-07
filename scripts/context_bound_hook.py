"""PreToolUse hook on Agent: denies the Agent call of an operator subagent
whose context is past `CONTEXT_BOUND` tokens, other than the launch of a
reply-only agent, a `general-purpose` agent on `haiku`. `past_bound` is the
test of the bound, which `profile_runs.py --running` marks on its listing as
well.

The context is read from the end of the caller's own transcript. Where the
hook cannot tell the caller's agent type or context, it allows the call and
says why on stderr."""

import sys
from typing import Any

from hook_entry import CHECK_FAILED, run_hook
from pending_wait_hook import deny

HOOK = "context_bound_hook"
OPERATOR = "operator"
CONTEXT_BOUND = 200_000
REPLY_ONLY_TYPE = "general-purpose"
REPLY_ONLY_MODEL = "haiku"


def bounded(agent_type: str) -> bool:
    return agent_type == OPERATOR


def past_bound(context: int | None) -> bool:
    return context is not None and context > CONTEXT_BOUND


def reply_only(inp: dict[str, Any]) -> bool:
    """Whether the Agent call input `inp` launches a `general-purpose` agent,
    the type a call that gives none launches, on `haiku`."""
    return (inp.get("subagent_type") or REPLY_ONLY_TYPE) == REPLY_ONLY_TYPE \
        and inp.get("model") == REPLY_ONLY_MODEL


def deny_past(context: int) -> None:
    from controlled_markdown import mctx

    deny(mctx(
        "Blocked: your context is {context:,} tokens, past the operator's "
        "bound of {bound:,} tokens. Past that bound you end as your "
        "documents give for your context."
    ).format(context=context, bound=CONTEXT_BOUND))


def check(hook: dict[str, Any]) -> None:
    from run_reads import UNKNOWN_TYPE, agent_type, caller_transcript, context_size
    from transcripts import entries_back

    tool, inp = hook["tool_name"], hook["tool_input"]
    if tool != "Agent":
        raise ValueError(f"the hook is registered on Agent, and the input "
                         f"gives tool `{tool}`")
    if reply_only(inp):
        return
    path = caller_transcript(hook)
    kind = agent_type(path)
    if kind is None:
        print(f"{HOOK}: allowed: {UNKNOWN_TYPE.format(path=path)}",
              file=sys.stderr)
        return
    if not bounded(kind):
        return
    context = context_size(entries_back(path))
    if context is None:
        print(f"{HOOK}: allowed: no assistant entry of {path} gives usage, so "
              "the context is unknown", file=sys.stderr)
        return
    if past_bound(context):
        deny_past(context)


def main() -> int:
    return run_hook(HOOK, CHECK_FAILED, check)


if __name__ == "__main__":
    sys.exit(main())
