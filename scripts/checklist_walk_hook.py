"""PreToolUse hook on SubagentHandback: denies the SubagentHandback call of
an agent whose type has a checklist (`handbook.checklist.checklist_agents`)
where the results of the step calls in its own transcript leave an item of
its walk unprinted (`handbook.checklist.Checklist.gap`), and the reason
gives the step call that prints the first such item.

A result counts where its Bash command runs `scripts/step.py <agent>` for
the caller's own agent type, however the command pipes or joins it. The
results are taken in order: an item is held only by a result that comes
after the last result that holds an earlier item of the walk, so a later
round is held to each item from the first one it repeats.

Where the agent's last step call is a stop, `scripts/step.py <agent>
--stop <item>`, and no entry after that call's result gives the agent a
message (`run_reads.is_prompt`) other than a harness notification
(`run_reads.notifications`), the walk is held only up to that item
(`Checklist.gap` with `upto`). Once such a message has reached the agent,
the stop bounds nothing, and the whole walk is held. A stop on an item the walk skips, or on no
item of the checklist, is held to the whole walk. The result of a stop
holds no item.

A denied call is recorded with the id of the agent's last step call, in a
file named by its agent id under `STOPS` of its session directory, and no
call is denied again while that step call is still the last: a fault in
the check, or a checklist that changed under the run, then cannot hold the
agent in a loop of denials. Where the hook cannot tell the agent type, it
allows the call and says why on stderr."""

import re
import sys
from collections.abc import Iterable
from typing import Any

from hook_entry import not_registered, run_pre_tool_use

HOOK = "checklist_walk_hook"
STOPS = "checklist-walk-stops"
NO_CALL = "none"
"""The record of an agent denied before it made any step call."""


def _step(agent: str) -> str:
    """The pattern of a step call of `agent` (`checklist.step_call`), up to
    its agent argument."""
    from handbook.checklist import STEP_SCRIPT

    return rf"{re.escape(STEP_SCRIPT)}\s+{re.escape(agent)}"


def runs_step(command: str, agent: str) -> bool:
    return re.search(rf"{_step(agent)}(?![\w-])", command) is not None


def stop_item(command: str, agent: str) -> str | None:
    """The item a `--stop` step call of `agent` in `command` names, or None
    where `command` makes no such call."""
    found = re.search(rf"{_step(agent)}\s+--stop\s+"
                      r"""(?:'([^']*)'|"([^"]*)"|([^\s;|&)]+))""", command)
    return None if found is None else next(g for g in found.groups() if g is not None)


def _calls(entries: Iterable[dict[str, Any]], agent: str) -> list[tuple[str, str, str]]:
    """The id, the command and the result text of each step call of
    `agent` among `entries`, in the order of their results."""
    from run_reads import blocks, tool_results

    entries = list(entries)
    commands = {str(b.get("id")): command
                for e in entries if e.get("type") == "assistant"
                for b in blocks(e, "tool_use") if b.get("name") == "Bash"
                for command in [str((b.get("input") or {}).get("command", ""))]
                if runs_step(command, agent)}
    return [(call, commands[call], result) for e in entries
            for call, _, result in tool_results(e) if call in commands]


def step_calls(entries: Iterable[dict[str, Any]], agent: str) -> list[tuple[str, str]]:
    """The id and the result text of each step call of `agent` among
    `entries` that is not a stop, in the order of their results."""
    return [(call, result) for call, _, result in not_stops(_calls(entries, agent), agent)]


def not_stops(calls: list[tuple[str, str, str]], agent: str) -> list[tuple[str, str, str]]:
    """The step calls of `calls`, as `_calls` gives them, that are not
    stops."""
    return [c for c in calls if stop_item(c[1], agent) is None]


def refusal(call: str, agent: str) -> str:
    from controlled_markdown import mctx

    return "\n".join([
        mctx("Blocked: the results of your step calls do not hold, whole, each item the "
             "step command gives up to your checklist's last item, or, where your last "
             "step call is a stop and no message has reached you since its result, up "
             "to its item, each in a result after the last result that holds an "
             "earlier item."),
        mctx("Run `{call}`, do each item from the one it prints to your checklist's last "
             "item, then give your report again."),
        mctx("Where you find no way to do the item your walk is at, run "
             "`uv run python scripts/step.py {agent} --stop <item>`, with that item as "
             "`<item>`, then give your report again."),
    ]).format(call=call, agent=agent)


def stop_bound(entries: list[dict[str, Any]], calls: list[tuple[str, str, str]],
               kind: str) -> str | None:
    """The item of the stop that bounds the walk of an agent of type `kind`,
    whose transcript `entries` hold its step calls `calls`, as the module
    docstring gives it, or None."""
    from run_reads import is_prompt, notifications, tool_results

    stop = stop_item(calls[-1][1], kind) if calls else None
    if stop is None:
        return None
    answered = [n for n, e in enumerate(entries)
                if any(call == calls[-1][0] for call, _, _ in tool_results(e))]
    since = entries[answered[-1] + 1:] if answered else []
    if any(is_prompt(e) and not notifications(e) for e in since):
        return None
    return stop


def walk_gap(kind: str, calls: list[tuple[str, str, str]], stop: str | None) -> str | None:
    """The step call that prints the first item the step calls `calls` of
    an agent of type `kind` leave unheld, up to the item `stop` where it
    gives one, as the module docstring gives it, or None."""
    from handbook.checklist import Checklist

    checklist = Checklist(kind)
    results = [result for _, _, result in not_stops(calls, kind)]
    # A stop that names no item, or whose part the walk skips, bounds nothing.
    for upto in [*([] if stop is None else [stop]), None]:
        try:
            gap = checklist.gap(results, upto=upto)
        except (ValueError, SystemExit):
            continue
        return None if gap is None else gap.call
    raise AssertionError("the walk with no bound raised")


def check(hook: dict[str, Any]) -> str | None:
    """The reason to deny the SubagentHandback call `hook` gives, as the
    module docstring gives it, or None."""
    from printed_launch_hook import first_at
    from run_reads import caller_id, caller_type
    from entry_reads import entries_back

    from handbook.checklist import checklist_agents

    tool = hook.get("tool_name")
    if tool is not None and tool != "SubagentHandback":
        raise not_registered("SubagentHandback", "tool", tool)
    path, kind = caller_type(HOOK, hook)
    agent = caller_id(hook)
    if kind is None or agent is None or kind not in checklist_agents():
        return None
    entries = list(reversed(list(entries_back(path))))
    calls = _calls(entries, kind)
    call = walk_gap(kind, calls, stop_bound(entries, calls, kind))
    if call is None:
        return None
    last = calls[-1][0] if calls else NO_CALL
    if not first_at(hook, STOPS, agent, last):
        print(f"{HOOK}: allowed: a handback was denied at step call {last}, "
              "and the agent made no step call since", file=sys.stderr)
        return None
    return refusal(call, kind)


def main() -> int:
    return run_pre_tool_use(HOOK, check)


if __name__ == "__main__":
    sys.exit(main())
