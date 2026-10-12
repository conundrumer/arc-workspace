"""PreToolUse hook on Agent: denies the Agent call of an operator or an
operator launcher subagent whose context is past `CONTEXT_BOUND` tokens, other than the launch of a
reply-only agent, a `general-purpose` agent on `haiku`. The denial gives the
caller the call of `operate.py` that prints its calls (`ACTIONS`), which
prints its end for its context.

The context is read from the end of the caller's own transcript. Where the
hook cannot tell the caller's agent type or context, it allows the call and
says why on stderr."""

import sys
from typing import Any

from hook_entry import not_registered, run_pre_tool_use
from operations.command_words import Action
from operations.roles import Model, Role

HOOK = "context_bound_hook"
OPERATOR = Role.OPERATOR.agent_type
OPERATOR_LAUNCHER = "operator-launcher"
ACTIONS: dict[str, Action] = {OPERATOR: Action.NEXT, OPERATOR_LAUNCHER: Action.RELAY}
"""The action of `operate.py` that prints the calls of each agent type the
hooks hold to them."""
OPERATORS = frozenset(ACTIONS)
"""The agent types that make only the calls their command prints."""
CONTEXT_BOUND = 100_000
"""Has no margin under it: the requests of a run's hand-over may go past
it."""
REPLY_ONLY_TYPE = "general-purpose"


def bounded(agent_type: str) -> bool:
    return agent_type in OPERATORS


def past_bound(context: int | None) -> bool:
    return context is not None and context > CONTEXT_BOUND


def reply_only(inp: dict[str, Any]) -> bool:
    """Whether the Agent call input `inp` launches a `general-purpose` agent,
    the type a call that gives none launches, on `haiku`."""
    return (inp.get("subagent_type") or REPLY_ONLY_TYPE) == REPLY_ONLY_TYPE \
        and inp.get("model") == Model.HAIKU


def past_reason(context: int, command: str) -> str:
    from controlled_markdown import mctx

    return "\n".join([
        mctx("Blocked: your context is {context:,} tokens, past the bound of "
             "{bound:,} tokens.").format(context=context, bound=CONTEXT_BOUND),
        mctx("Run `{command}` again: it prints how you end.").format(command=command)])


def check(hook: dict[str, Any]) -> str | None:
    """The reason to deny the Agent call `hook` gives where its caller is
    past the bound, and None otherwise."""
    from operations.command_words import next_command
    from run_reads import caller_id, caller_type, context_size
    from transcripts import entries_back

    tool, inp = hook["tool_name"], hook["tool_input"]
    if tool != "Agent":
        raise not_registered("Agent", "tool", tool)
    if reply_only(inp):
        return None
    path, kind = caller_type(HOOK, hook)
    if kind is None:
        return None
    if not bounded(kind):
        return None
    context = context_size(entries_back(path))
    if context is None:
        print(f"{HOOK}: allowed: no assistant entry of {path} gives usage, so "
              "the context is unknown", file=sys.stderr)
        return None
    if not past_bound(context):
        return None
    agent = caller_id(hook)
    if agent is None:
        raise ValueError(f"{HOOK}: the {kind} caller of {path} gives no agent id")
    return past_reason(context, next_command(agent, ACTIONS[kind]))


def main() -> int:
    from reader_commits import reader_update

    return run_pre_tool_use(HOOK, check, reader_update)


if __name__ == "__main__":
    sys.exit(main())
