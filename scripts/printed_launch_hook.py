"""PreToolUse hook on Agent: denies the Agent call of an operator subagent
that is not the launch `operate.py next` last printed to it, other than the
launch of a reply-only agent (`context_bound_hook.reply_only`). An operator
launcher is held the same way to the launch `operate.py relay` last printed
to it (`context_bound_hook.ACTIONS`), and a doc editor's launch of a doc
reviewer to the launch `operate.py review` last printed to it
(`EDITOR_LAUNCHES`).

The printed launch is read from the result of the last call of `next` in
the caller's own transcript (`printing.printed_launch`). Where that result
gives no whole launch, or a parameter of the call differs from the printed
one, the denial gives what the operator calls instead. A printed
`run_in_background` is compared only where the call input gives it: the
harness gives the hook a `tool_input` with no `run_in_background`, though
the call gives it. Where the hook cannot tell the caller's agent type, it
allows the call and says why on stderr."""

import sys
from collections.abc import Iterable
from contextlib import nullcontext
from typing import Any, NamedTuple

from context_bound_hook import ACTIONS, reply_only
from operations.command_words import Action
from operations.roles import Role
from hook_entry import not_registered, run_pre_tool_use

HOOK = "printed_launch_hook"
EDITOR_LAUNCHES = {Role.DOC_EDITOR.agent_type: (Role.DOC_REVIEWER.agent_type, Action.REVIEW)}
"""For each agent type held only in its launches of one agent type, that
type and the action of `operate.py` that prints those launches."""
UNSEEN = "run_in_background"


def differing(printed: dict[str, str], inp: dict[str, Any]) -> list[tuple[str, str | None, str | None]]:
    """Each parameter that differs between the printed launch `printed` and
    the call input `inp`, with its printed and its given value, None where
    one gives none, in the printed order, then each other parameter of the
    call by name, other than an `UNSEEN` the call input does not give."""
    from operations.printing import parameter

    names = [*printed, *sorted(k for k in inp if k not in printed)]
    out: list[tuple[str, str | None, str | None]] = []
    for name in names:
        if name == UNSEEN and name not in inp:
            continue
        want = printed.get(name)
        got = parameter(inp[name]) if name in inp else None
        if want != got:
            out.append((name, want, got))
    return out


def last_next_call(entries: Iterable[dict[str, Any]], agent: str,
                   action: Action) -> tuple[str, str] | None:
    """The id and the result of the last call of `operate.py` with `action`
    for the agent `agent` among `entries`, read last first, or None where
    none has a result."""
    from operations.command_words import is_next
    from run_reads import blocks, tool_results

    results: dict[str, str] = {}
    for e in entries:
        for call, _, text in tool_results(e):
            results.setdefault(call, text)
        if e.get("type") == "assistant":
            for b in reversed(blocks(e, "tool_use")):
                command = str((b.get("input") or {}).get("command", ""))
                if (b.get("name") == "Bash" and is_next(command, agent, action)
                        and b.get("id", "") in results):
                    return b["id"], results[b["id"]]
    return None


class NextCaller(NamedTuple):
    agent: str
    action: Action
    command: str
    found: tuple[str, str] | None


def held_action(kind: str, inp: dict[str, Any]) -> Action | None:
    """The action of `operate.py` whose printed launch holds the Agent call
    input `inp` of a caller of agent type `kind`, or None where none
    does."""
    if kind in ACTIONS:
        return ACTIONS[kind]
    if kind in EDITOR_LAUNCHES:
        launched, action = EDITOR_LAUNCHES[kind]
        return action if inp.get("subagent_type") == launched else None
    return None


def operator_next(hook: dict[str, Any], name: str) -> NextCaller | None:
    """The agent id of the caller of `hook` where `held_action` gives its
    call an action, with the action and the command that prints its calls and
    the id and the result of its last call of that command
    (`last_next_call`), or None where it is of another type, or where its
    agent type is unknown, which the hook `name` says on stderr. A hook with
    no tool input, the SubagentStop hook, gives `held_action` an empty
    input."""
    from operations.command_words import next_command
    from run_reads import caller_id, caller_type
    from transcript_entries import entries_back

    path, kind = caller_type(name, hook)
    if kind is None:
        return None
    agent = caller_id(hook)
    action = held_action(kind, hook.get("tool_input") or {})
    if action is None or agent is None:
        return None
    return NextCaller(agent, action, next_command(agent, action),
                      last_next_call(entries_back(path), agent, action))


def first_at(hook: dict[str, Any], records: str, agent: str, call: str) -> bool:
    """Whether the caller `agent` of `hook` has no record under `records`
    of its session directory that gives `call`, the id of its last call of
    its command, which it then records: a hook that holds the caller to
    that call's result acts on it once."""
    from run_reads import hook_session

    record = hook_session(hook) / records / agent
    if record.exists() and record.read_text() == call:
        return False
    record.parent.mkdir(parents=True, exist_ok=True)
    record.write_text(call)
    return True


def no_launch_reason(command: str, action: Action) -> str:
    from controlled_markdown import mctx

    return "\n".join([
        mctx("Blocked: the last result of `{command}` gives no whole launch."),
        mctx("Make only the launch that `{action}` prints, and run `{action}` with no "
             "pipe."),
    ]).format(command=command, action=action)


def differ_reason(command: str, diffs: list[tuple[str, str | None, str | None]]) -> str:
    from controlled_markdown import mctx

    head = "\n".join([
        mctx("Blocked: this Agent call differs from the launch the last result of "
             "`{command}` prints.").format(command=command),
        mctx("Make the call again with each parameter as printed:")])
    none = mctx("none")
    lines = [f"- `{name}`: printed `{none if want is None else want}`, given "
             f"`{none if got is None else got}`" for name, want, got in diffs]
    return "\n".join([head, *lines])


def check(hook: dict[str, Any]) -> str | None:
    """The reason to deny the Agent call `hook` gives where `held_action`
    holds it and it is not the launch its command last printed to its
    caller, and None otherwise."""
    from operations.printing import printed_launch

    tool, inp = hook["tool_name"], hook["tool_input"]
    if tool != "Agent":
        raise not_registered("Agent", "tool", tool)
    if reply_only(inp):
        return None
    caller = operator_next(hook, HOOK)
    if caller is None:
        return None
    command, found = caller.command, caller.found
    printed = None if found is None else printed_launch(found[1])
    if printed is None:
        return no_launch_reason(command, caller.action)
    diffs = differing(printed, inp)
    return differ_reason(command, diffs) if diffs else None


def main() -> int:
    return run_pre_tool_use(HOOK, check, lambda hook: nullcontext(None))


if __name__ == "__main__":
    sys.exit(main())
