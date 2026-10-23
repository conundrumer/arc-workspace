"""PreToolUse hook on SubagentHandback: denies the SubagentHandback call of
an agent whose type has a checklist (`handbook.checklist.checklist_agents`)
where the results of the step calls in its own transcript leave an item of
its walk unprinted (`handbook.checklist.Checklist.gap`), and the reason
gives the call that prints the first such item (`handbook.checklist.Gap.call`).

A result counts only where its Bash command's simple commands, through a
shell wrapper, are one step call for the caller's agent type and optional
`cd` commands. A pipe or join with other work, or two step calls, counts
as no step call. The results are taken in order: an item is held only after
the item before it, in a later result or later in the same result, so one
result may hold several items, and a later round is held to each item from the first one
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
results instead. Unreadable or incomplete Codex turn records are denied once
for each `codex_agent` launch call of the launcher, as a Claude agent's refusal is
denied once for each step call; the launcher must pass the refusal back to Codex by
a resume. Where `walk_entries` read a native assignment, its receipt holds the walk
check, and the hook allows the call.

A denied call is recorded with the id of the agent's last step call, in a
file named by its agent id under `STOPS` of its session directory, and no
call is denied again while that step call is still the last: a fault in
the check, or a checklist that changed under the run, then cannot hold the
agent in a loop of denials. Where the hook cannot tell the agent type, it
allows the call and says why on stderr."""

import sys
from pathlib import Path
from shlex import join

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


def shell_command(words: list[str]) -> tuple[str | None, list[str]]:
    """The program and arguments with combined shell command flags normalized."""
    normalized = ["-c" if w.startswith("-") and "c" in w[1:]
                  and set(w[1:]) <= set("lic") else w for w in words]
    return segment_program(normalized)


def step_arguments(command: str, agent: str):
    """Executable step calls, including shell command-string wrappers."""
    from handbook.checklist import STEP_SCRIPT

    for words in simple_commands(command):
        program, args = segment_program(words)
        shell, rest = shell_command(words)
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


def isolated_step(command: str, agent: str) -> bool:
    """Whether the command contains one step call and only directory changes."""
    count = 0
    for words in simple_commands(command):
        if not words:
            continue
        program, args = shell_command(words)
        if program == "cd":
            continue
        if program in {"bash", "sh", "zsh"} and args:
            if not isolated_step(args[0], agent):
                return False
            count += 1
        elif len(list(step_arguments(join(words), agent))) == 1:
            count += 1
        else:
            return False
    return count == 1


def _calls(entries: Iterable[dict[str, Any]], agent: str) -> list[tuple[str, str, str]]:
    """The id, the command and the result text of each step call of
    `agent` among `entries`, in the order of their results."""
    from run_reads import blocks, tool_results

    entries = list(entries)
    commands = {str(b.get("id")): command
                for e in entries if e.get("type") == "assistant"
                for b in blocks(e, "tool_use") if b.get("name") == "Bash"
                for command in [str((b.get("input") or {}).get("command", ""))]
                if isolated_step(command, agent)}
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
        # Ticket 11-3130: doc editor ad68ab6b18e660953 advanced past
        # write-the-edit after a refusal, then made that item's edit.
        # Request 11-3448: ticket reviewer ae30ef4e377e4d07d read the call as
        # run, though it ran it joined with other work, and ran other calls.
        mctx("If `{command}` has an item argument, first do the work that item's "
             "previously printed instruction gives. Run that call again, even "
             "where you ran it before: a step call joined with other work or "
             "piped holds no item. Run it as the whole command of a Bash call, "
             "with no pipe, do the item it prints, then "
             "go on by the call each item ends with. Then give your report again."),
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
        from codex_reads import calls as launch_calls, native_walk, walk_entries

        try:
            native = native_walk(entries, kind)
            entries = walk_entries(entries, kind) if native is None else native
        except (OSError, ValueError, KeyError, IndexError, TypeError, AttributeError) as exc:
            launches = launch_calls(entries, [])
            launch = launches[-1].call_id if launches else NO_CALL
            if not first_at(hook, STOPS, agent, launch):
                print(f"{HOOK}: allowed: a handback was denied after Codex launch {launch}, "
                      f"and the launcher made no launch since: {exc}", file=sys.stderr)
                return None
            return mctx("Blocked: cannot read the Codex walk: {error}. "
                        "Resume Codex to finish its walk.").format(error=exc)
        if native is not None:
            return None
    calls = _calls(entries, kind)
    gap = walk_gap(kind, calls, stop_bound(entries, calls, kind))
    if gap is None:
        return None
    last = calls[-1][0] if calls else NO_CALL
    if not first_at(hook, STOPS, agent, last):
        print(f"{HOOK}: allowed: a handback was denied at step call {last}, "
              "and the agent made no step call since", file=sys.stderr)
        return None
    reason = refusal(gap.call, kind)
    if codex:
        return mctx("Blocked: resume Codex with this refusal, then hand back its updated reply.") + "\n" + reason
    return reason


def main() -> int:
    return run_pre_tool_use(HOOK, [check])


if __name__ == "__main__":
    sys.exit(main())
