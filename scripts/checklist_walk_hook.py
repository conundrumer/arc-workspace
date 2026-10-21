"""PreToolUse hook on SubagentHandback: denies the SubagentHandback call of
an agent whose type has a checklist (`handbook.checklist.checklist_agents`)
where the results of the step calls in its own transcript leave an item of
its walk unprinted (`handbook.checklist.Checklist.gap`), and the reason
gives, as one command (`handbook.checklist.Gap.command`), the step calls
that print each item from the first such item.

A result counts where its Bash command runs `scripts/step.py <agent>` for
the caller's own agent type, however the command pipes or joins it. The
results are taken in order: an item is held only after the item before
it, in a later result or later in the same result, so one result may hold
several items, and a later round is held to each item from the first one
it repeats.

Where the agent's last step call is a stop, `scripts/step.py <agent>
--stop <item>`, and no entry after that call's result gives the agent a
message (`run_reads.is_prompt`) other than a harness notification
(`run_reads.notifications`), the walk is held only up to that item
(`Checklist.gap` with `upto`). Once such a message has reached the agent,
the stop bounds nothing, and the whole walk is held. A stop on an item the walk skips, or on no
item of the checklist, is held to the whole walk. The result of a stop
holds no item.

For a Codex launcher, `codex_reads.walk_entries` reads Codex's command
results instead. An unreadable or incomplete Codex walk is denied on each
attempt; the launcher must pass the refusal back to Codex by a resume.

A denied Claude call is recorded with the id of the agent's last step call, in a
file named by its agent id under `STOPS` of its session directory, and no
call is denied again while that step call is still the last: a fault in
the check, or a checklist that changed under the run, then cannot hold the
agent in a loop of denials. Where the hook cannot tell the agent type, it
allows the call and says why on stderr."""

import sys
from pathlib import Path

from command_labels import segment_program, simple_commands

from controlled_markdown import mctx
from collections.abc import Iterable
from typing import TYPE_CHECKING, Any

from hook_entry import not_registered, run_pre_tool_use

if TYPE_CHECKING:
    from handbook.checklist import Gap

HOOK = "checklist_walk_hook"
STOPS = "checklist-walk-stops"
NO_CALL = "none"
"""The record of an agent denied before it made any step call."""


def step_arguments(command: str, agent: str):
    """Executable step calls, including shell command-string wrappers."""
    from handbook.checklist import STEP_SCRIPT

    for words in simple_commands(command):
        program, args = segment_program(words)
        # segment_program treats combined shell flags as interpreter options.
        # Normalize those flags before asking it for the command string.
        normalized = ["-c" if w.startswith("-") and "c" in w[1:]
                      and set(w[1:]) <= set("lic") else w for w in words]
        shell, rest = segment_program(normalized)
        if shell in {"bash", "sh", "zsh"} and rest:
            yield from step_arguments(rest[0], agent)
        elif program == Path(STEP_SCRIPT).name and args and args[0] == agent:
            script = words[len(words) - len(args) - 1]
            if script == STEP_SCRIPT or script.endswith("/" + STEP_SCRIPT):
                yield args[1:]


def runs_step(command: str, agent: str) -> bool:
    return next(step_arguments(command, agent), None) is not None


def stop_item(command: str, agent: str) -> str | None:
    """The item a `--stop` step call of `agent` in `command` names, or None
    where `command` makes no such call."""
    calls = list(step_arguments(command, agent))
    args = calls[-1] if calls else []
    return args[1] if len(args) == 2 and args[0] == "--stop" else None


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


def refusal(command: str, agent: str) -> str:
    from controlled_markdown import mctx

    return "\n".join([
        mctx("Blocked: the results of your step calls do not hold, whole, each item the "
             "step command gives up to your checklist's last item, or, where your last "
             "step call is a stop and no message has reached you since its result, up "
             "to its item, each after the item before it, in a later result or later "
             "in the same result."),
        mctx("Run `{command}` in one Bash call, do each item from the first one it prints "
             "to your checklist's last item, then give your report again."),
        mctx("Where you find no way to do the item your walk is at, run "
             "`uv run python scripts/step.py {agent} --stop <item>`, with that item as "
             "`<item>`, then give your report again."),
    ]).format(command=command, agent=agent)


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


def walk_gap(kind: str, calls: list[tuple[str, str, str]], stop: str | None) -> "Gap | None":
    """The gap the step calls `calls` of an agent of type `kind` leave in
    its walk, up to the item `stop` where it gives one, as the module
    docstring gives it, or None."""
    from handbook.checklist import Checklist

    checklist = Checklist(kind)
    results = [result for _, _, result in not_stops(calls, kind)]
    # A stop that names no item, or whose part the walk skips, bounds nothing.
    for upto in [*([] if stop is None else [stop]), None]:
        try:
            gap = checklist.gap(results, upto=upto)
        except (ValueError, SystemExit):
            continue
        return gap
    raise AssertionError("the walk with no bound raised")


def check(hook: dict[str, Any]) -> str | None:
    """The reason to deny the SubagentHandback call `hook` gives, as the
    module docstring gives it, or None."""
    from printed_launch_hook import first_at
    from run_reads import agent_type, caller_id, caller_type, caller_transcript
    from operations.roles import CODEX_LAUNCHER
    from entry_reads import entries_back

    from handbook.checklist import checklist_agents

    tool = hook.get("tool_name")
    if tool is not None and tool != "SubagentHandback":
        raise not_registered("SubagentHandback", "tool", tool)
    path = caller_transcript(hook)
    codex = agent_type(path) == CODEX_LAUNCHER
    try:
        path, kind = caller_type(HOOK, hook)
    except ValueError as exc:
        if codex:
            return mctx("Blocked: cannot read the Codex role: {error}.").format(error=exc)
        raise
    agent = caller_id(hook)
    if kind is None or agent is None or kind not in checklist_agents():
        return None
    entries = list(reversed(list(entries_back(path))))
    if codex:
        from codex_reads import walk_entries

        try:
            entries = walk_entries(entries, kind)
        except (OSError, ValueError, KeyError, IndexError, TypeError, AttributeError) as exc:
            return mctx("Blocked: cannot read the Codex walk: {error}. "
                        "Resume Codex to finish its walk.").format(error=exc)
    calls = _calls(entries, kind)
    gap = walk_gap(kind, calls, stop_bound(entries, calls, kind))
    if gap is None:
        return None
    last = calls[-1][0] if calls else NO_CALL
    if not codex and not first_at(hook, STOPS, agent, last):
        print(f"{HOOK}: allowed: a handback was denied at step call {last}, "
              "and the agent made no step call since", file=sys.stderr)
        return None
    reason = refusal(gap.command, kind)
    if codex:
        return mctx("Blocked: resume Codex with this refusal, then hand back its updated reply.") + "\n" + reason
    return reason


def main() -> int:
    return run_pre_tool_use(HOOK, [check])


if __name__ == "__main__":
    sys.exit(main())
