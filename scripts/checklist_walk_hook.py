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


def runs_step(command: str, agent: str) -> bool:
    return re.search(rf"scripts/step\.py\s+{re.escape(agent)}(?![\w-])", command) is not None


def step_calls(entries: Iterable[dict[str, Any]], agent: str) -> list[tuple[str, str]]:
    """The id and the result text of each step call of `agent` among
    `entries`, in the order of their results."""
    from run_reads import blocks, tool_results

    entries = list(entries)
    calls = {str(b.get("id")) for e in entries if e.get("type") == "assistant"
             for b in blocks(e, "tool_use") if b.get("name") == "Bash"
             and runs_step(str((b.get("input") or {}).get("command", "")), agent)}
    return [(call, result) for e in entries for call, _, result in tool_results(e)
            if call in calls]


def refusal(call: str) -> str:
    from controlled_markdown import mctx

    return "\n".join([
        mctx("Blocked: the results of your step calls do not hold, whole, each item the "
             "step command gives up to your checklist's last item, each in a result "
             "after the last result that holds an earlier item."),
        mctx("Run `{call}`, do each item from the one it prints to your checklist's last "
             "item, then give your report again."),
    ]).format(call=call)


def check(hook: dict[str, Any]) -> str | None:
    """The reason to deny the SubagentHandback call `hook` gives, as the
    module docstring gives it, or None."""
    from printed_launch_hook import first_at
    from run_reads import caller_id, caller_type
    from transcript_entries import entries_back

    from handbook.checklist import Checklist, checklist_agents

    tool = hook.get("tool_name")
    if tool is not None and tool != "SubagentHandback":
        raise not_registered("SubagentHandback", "tool", tool)
    path, kind = caller_type(HOOK, hook)
    agent = caller_id(hook)
    if kind is None or agent is None or kind not in checklist_agents():
        return None
    calls = step_calls(reversed(list(entries_back(path))), kind)
    gap = Checklist(kind).gap(result for _, result in calls)
    if gap is None:
        return None
    last = calls[-1][0] if calls else NO_CALL
    if not first_at(hook, STOPS, agent, last):
        print(f"{HOOK}: allowed: a handback was denied at step call {last}, "
              "and the agent made no step call since", file=sys.stderr)
        return None
    return refusal(gap.call)


def main() -> int:
    return run_pre_tool_use(HOOK, check)


if __name__ == "__main__":
    sys.exit(main())
