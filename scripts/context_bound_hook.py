"""PreToolUse hook on Agent: denies the Agent call of an operator subagent
whose context is past `CONTEXT_BOUND` tokens, other than the launch of a
reply-only agent, a `general-purpose` agent on `haiku`. `past_bound` is the
test of the bound, which `profile_runs.py --running` marks on its listing as
well.

The context is the input of the caller's latest request, as `--running`
gives it, read from the end of the caller's own transcript. The caller's
agent type is the one the `.meta.json` of that transcript gives. A hook input
inside a subagent gives the subagent's agent id, so an input that gives none
is the main session's, which no bound limits.

Where the hook cannot tell the caller's agent type or context, or its check
fails on its own error, it allows the call and says why on stderr."""

import sys
from pathlib import Path
from typing import Any

from hook_entry import run_hook
from pending_wait_hook import deny

HOOK = "context_bound_hook"
OPERATOR = "operator"
CONTEXT_BOUND = 200_000
REPLY_ONLY_TYPE = "general-purpose"
REPLY_ONLY_MODEL = "haiku"


def past_bound(agent_type: str, context: int | None) -> bool:
    """Whether an agent of `agent_type` whose context is `context` tokens is
    an operator past `CONTEXT_BOUND`. An unknown context is not past it."""
    return (agent_type == OPERATOR and context is not None
            and context > CONTEXT_BOUND)


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
    """Deny the Agent call `hook` gives where its caller is an operator past
    the bound and the call launches no reply-only agent."""
    from run_reads import context_size, session_agents, session_of, transcript_meta
    from transcripts import entries_back

    tool, inp = hook["tool_name"], hook["tool_input"]
    if tool != "Agent":
        raise ValueError(f"the hook is registered on Agent, and the input "
                         f"gives tool `{tool}`")
    caller = hook.get("agent_id")
    if not caller or reply_only(inp):
        return
    session = session_of(Path(hook["transcript_path"]))
    path = session_agents(session).get(caller)
    if path is None:
        print(f"{HOOK}: allowed: no transcript of agent {caller} under "
              f"{session}, so its agent type is unknown", file=sys.stderr)
        return
    agent_type = (transcript_meta(path) or {}).get("agentType")
    if not isinstance(agent_type, str):
        print(f"{HOOK}: allowed: the .meta.json of {path} gives no agent "
              "type", file=sys.stderr)
        return
    if agent_type != OPERATOR:
        return
    context = context_size(entries_back(path))
    if context is None:
        print(f"{HOOK}: allowed: no assistant entry of {path} gives usage, so "
              "the context is unknown", file=sys.stderr)
        return
    if past_bound(agent_type, context):
        deny_past(context)


def main() -> int:
    return run_hook(HOOK, "allowed: the check failed", check)


if __name__ == "__main__":
    sys.exit(main())
