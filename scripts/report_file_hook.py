"""PreToolUse hook on SubagentHandback: denies the SubagentHandback call of
an agent whose brief gives a report file (`filed_texts.brief_report_file`)
where the call's message is not that file's path alone
(`filed_texts.report_file`), or no file is there, or that file was last
written before the last message the agent got that is no notification
(`senders.is_notification`) and no note of the harness
(`senders.is_harness_note`), and the reason gives the path. A file written
before that message holds the reply of an earlier round. A notification
does not count, as one that resumes the agent after its final reply has it
give that reply again with the file unchanged. A note of the harness does
not count, as the harness writes one, such as one that asks for the
handback, after the agent has written its final reply.

The brief is the first message of the agent's own transcript, with each
file it gives by `FILED_LINE` read in (`filed_texts.unfiled`).

A Codex launcher must have readable turn records (`codex_reads`). Where its
brief cannot be read, the hook allows the call and says why on stderr.
Unreadable turn records are denied once for
each `codex_agent` launch call of the launcher; a repeated handback with no new
launch is allowed, and the reason goes to stderr.

A denied call is recorded with the id of the last message the agent got
that is no note of the harness,
in a file named by its agent id under `STOPS` of its session directory,
and no call is denied again while that message is still the last. A denial
gives the agent no message, so a fault in the check cannot hold the agent
in a loop of denials, and a message that resumes the agent after its final
reply has a new handback checked again. Where the brief gives a file that
is gone, the hook allows the call and says why on stderr."""

import sys

from controlled_markdown import mctx
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from hook_entry import Hook, not_registered, run_pre_tool_use

HOOK = "report_file_hook"
STOPS = "report-file-stops"


def brief(entries: Iterable[dict[str, Any]], where: str, undecided: list[str]) -> str | None:
    """The text of the first message among `entries`, with each file it
    gives read in, or None where they hold no message."""
    from filed_texts import unfiled
    from run_reads import is_prompt, message_text

    first = next((e for e in entries if is_prompt(e)), None)
    return None if first is None else unfiled(message_text(first), where, undecided)


def last_message(entries: Iterable[dict[str, Any]]) -> str:
    """The id of the first message among `entries`, read last first, that
    is no note of the harness."""
    from run_reads import is_prompt
    from senders import is_harness_note

    return next(str(e["uuid"]) for e in entries if is_prompt(e) and not is_harness_note(e))


def written_since(path: Path, entries: Iterable[dict[str, Any]]) -> bool:
    """Whether the file at `path` was last written after the first message
    among `entries`, read last first, that is no notification and no note
    of the harness."""
    from file_reads import stat_read
    from run_reads import is_prompt
    from senders import is_harness_note, is_notification
    from transcript_entries import epoch

    found = stat_read(path)
    if found is None or not found.is_file:
        return False
    last = next(e for e in entries
                if is_prompt(e) and not is_notification(e) and not is_harness_note(e))
    return found.mtime > epoch(str(last["timestamp"]))


def refusal(path: Path) -> str:
    from controlled_markdown import mctx

    return "\n".join([
        mctx("Blocked: your brief gives the report file `{path}`, and the message of this "
             "call is not that file's path alone, or that file does not exist or was last "
             "written before the last message you got."),
        mctx("Write your final reply to that file, then give its path alone as the text you hand back."),
    ]).format(path=path)


def check(hook: Hook) -> str | None:
    """The reason to deny the SubagentHandback call `hook` gives, as the
    module docstring gives it, or None."""
    from filed_texts import brief_report_file, report_file
    from printed_launch_hook import first_at
    from run_reads import agent_type, caller_id, caller_transcript, role_type
    from operations.roles import CODEX_LAUNCHER
    from entry_reads import entries_back, entries_forward

    tool = hook.get("tool_name")
    if tool is not None and tool != "SubagentHandback":
        raise not_registered("SubagentHandback", "tool", tool)
    agent = caller_id(hook)
    if agent is None:
        return None
    path = caller_transcript(hook)
    codex = agent_type(path) == CODEX_LAUNCHER
    if codex:
        from codex_reads import calls as launch_calls, walk_entries

        try:
            kind = role_type(path)
            if kind is None:
                raise ValueError("the Codex role is unknown")
            walk_entries(list(entries_forward(path)), kind)
        except (OSError, ValueError, KeyError, IndexError, TypeError, AttributeError) as exc:
            launches = launch_calls(list(entries_forward(path)), [])
            launch = launches[-1].call_id if launches else "none"
            if not first_at(hook, STOPS, agent, launch):
                print(f"{HOOK}: allowed: a handback was denied after Codex launch {launch}, "
                      f"and the launcher made no launch since: {exc}", file=sys.stderr)
                return None
            return mctx("Blocked: cannot read the Codex report's run: {error}.").format(error=exc)
    undecided: list[str] = []
    try:
        text = brief(entries_forward(path), f"the brief of {agent}", undecided)
    except (OSError, ValueError) as exc:
        if codex:
            print(f"{HOOK}: allowed: cannot read the Codex brief: {exc}", file=sys.stderr)
            return None
        raise
    for line in undecided:
        print(f"{HOOK}: allowed: {line}", file=sys.stderr)
    if text is None:
        print(f"{HOOK}: allowed: the transcript holds no brief message", file=sys.stderr)
    if text is None or undecided:
        return None
    wanted = brief_report_file(text)
    if wanted is None:
        return None
    given = report_file(str((hook.get("tool_input") or {}).get("message", "")))
    if given == wanted and written_since(wanted, entries_back(path)):
        return None
    last = last_message(entries_back(path))
    if not first_at(hook, STOPS, agent, last):
        print(f"{HOOK}: allowed: a handback was denied after message {last}, "
              "and the agent got no message since", file=sys.stderr)
        return None
    return refusal(wanted)


def main() -> int:
    return run_pre_tool_use(HOOK, [check])


if __name__ == "__main__":
    sys.exit(main())
