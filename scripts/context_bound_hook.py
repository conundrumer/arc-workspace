"""PreToolUse hook on Agent: denies the Agent call of an operator or an
operator launcher subagent whose context is past the bound in force
(`context_bound`), other than the launch of a
reply-only agent, a `general-purpose` agent on `haiku`. The denial gives the
caller the call of `operate.py` that prints its calls (`ACTIONS`), which
prints its end for its context.

The context is read from the end of the caller's own transcript. Where the
hook cannot tell the caller's agent type or context, it allows the call and
says why on stderr."""

import sys
from pathlib import Path
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
"""The bound in force where no override stands. Has no margin under it:
the requests of a run's hand-over may go past it."""
OVERRIDE = Path(".cache") / "context-bound"
"""The file, under the main tree, that holds the bound that overrides
`CONTEXT_BOUND` for every session on the machine, as one positive whole
number of tokens."""
REPLY_ONLY_TYPE = "general-purpose"


def bounded(agent_type: str) -> bool:
    return agent_type in OPERATORS


def tokens_of(text: str) -> int | None:
    """The bound `text` gives as one positive whole number of tokens, or
    None where it gives anything else."""
    tokens = text.strip()
    return int(tokens) if tokens.isdecimal() and int(tokens) > 0 else None


def override_read(main_tree: Path) -> int | None:
    """The bound the override file under `main_tree` holds, or None where
    the file is absent. Where the file holds anything other than one
    positive whole number, None, and says so on stderr."""
    path = main_tree / OVERRIDE
    try:
        text = path.read_text()
    except FileNotFoundError:
        return None
    tokens = tokens_of(text)
    if tokens is not None:
        return tokens
    print(f"{HOOK}: {path} holds no positive whole number, so the bound is "
          f"{CONTEXT_BOUND:,}", file=sys.stderr)
    return None


def context_bound(main_tree: Path) -> int:
    """The bound in force: the override under `main_tree`, or
    `CONTEXT_BOUND` where none stands."""
    override = override_read(main_tree)
    return CONTEXT_BOUND if override is None else override


def past_bound(context: int | None, bound: int) -> bool:
    return context is not None and context > bound


def reply_only(inp: dict[str, Any]) -> bool:
    """Whether the Agent call input `inp` launches a `general-purpose` agent,
    the type a call that gives none launches, on `haiku`."""
    return (inp.get("subagent_type") or REPLY_ONLY_TYPE) == REPLY_ONLY_TYPE \
        and inp.get("model") == Model.HAIKU


def past_reason(context: int, bound: int, command: str) -> str:
    from controlled_markdown import mctx

    return "\n".join([
        mctx("Blocked: your context is {context:,} tokens, past the bound of "
             "{bound:,} tokens.").format(context=context, bound=bound),
        mctx("Run `{command}` again: it prints how you end.").format(command=command)])


def check(hook: dict[str, Any]) -> str | None:
    """The reason to deny the Agent call `hook` gives where its caller is
    past the bound, and None otherwise."""
    from operations.command_words import next_command
    from run_reads import caller_id, caller_type, context_size
    from entry_reads import entries_back
    from tree_reads import main_tree

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
    bound = context_bound(main_tree())
    if not past_bound(context, bound):
        return None
    agent = caller_id(hook)
    if agent is None:
        raise ValueError(f"{HOOK}: the {kind} caller of {path} gives no agent id")
    return past_reason(context, bound, next_command(agent, ACTIONS[kind]))


def main() -> int:
    from reader_delivery import reader_update

    return run_pre_tool_use(HOOK, [check], reader_update)


if __name__ == "__main__":
    sys.exit(main())
