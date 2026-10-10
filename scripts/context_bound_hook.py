"""PreToolUse hook on Agent: denies the Agent call of an operator subagent
whose context is past `CONTEXT_BOUND` tokens, other than the launch of a
reply-only agent, a `general-purpose` agent on `haiku`.

The context is read from the end of the caller's own transcript. Where the
hook cannot tell the caller's agent type or context, it allows the call and
says why on stderr."""

import sys
from typing import Any

from hook_entry import run_pre_tool_use

HOOK = "context_bound_hook"
OPERATOR = "operator"
CONTEXT_BOUND = 47_855
"""Keeps each request of an operator run, its hand-over included, within
the cheap tier of `claude-haiku-5-5`, up to 100,000 input tokens. The
margin under 100,000 is the sum of two measures over the operator runs of
this project's transcripts: the largest rise in input tokens between two
consecutive requests of a run, 18,994, since the context tested is that of
the last request made, and the largest rise from the request after which
`next` first prints the context-bound ending to the run's last request,
33,151."""
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


def past_reason(context: int) -> str:
    from controlled_markdown import mctx

    return mctx(
        "Blocked: your context is {context:,} tokens, past the operator's "
        "bound of {bound:,} tokens. Past that bound you end as your "
        "documents give for your context."
    ).format(context=context, bound=CONTEXT_BOUND)


def check(hook: dict[str, Any]) -> str | None:
    """The reason to deny the Agent call `hook` gives where its caller is
    past the bound, and None otherwise."""
    from run_reads import UNKNOWN_TYPE, agent_type, caller_transcript, context_size
    from transcripts import entries_back

    tool, inp = hook["tool_name"], hook["tool_input"]
    if tool != "Agent":
        raise ValueError(f"the hook is registered on Agent, and the input "
                         f"gives tool `{tool}`")
    if reply_only(inp):
        return None
    path = caller_transcript(hook)
    kind = agent_type(path)
    if kind is None:
        print(f"{HOOK}: allowed: {UNKNOWN_TYPE.format(path=path)}",
              file=sys.stderr)
        return None
    if not bounded(kind):
        return None
    context = context_size(entries_back(path))
    if context is None:
        print(f"{HOOK}: allowed: no assistant entry of {path} gives usage, so "
              "the context is unknown", file=sys.stderr)
        return None
    return past_reason(context) if past_bound(context) else None


def main() -> int:
    from reader_commits import reader_update

    return run_pre_tool_use(HOOK, check, reader_update)


if __name__ == "__main__":
    sys.exit(main())
