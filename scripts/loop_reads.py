"""The reads that turn a loop's record into the state's facts: what a
merge call did, the tickets a solver pass's report lists, the files a call
gives, and the final replies in the transcripts of the agents the loop
launched."""

import math
import re
from dataclasses import replace
from pathlib import Path
from typing import Any

from agent_turns import has_ended, turns
from filed_texts import unfiled
from merge_change import conflicted, left_edits, ran
from run_reads import blocks, run_entries
from ticket_numbers import TICKET_NUMBER
from transcripts import epoch, find

from controlled_markdown import mctx
from operations import alerts
from operations.merging import MERGE_SCRIPT, merge_messages
from operations.reports import TICKETS_FILED
from operations.state import Agent, Merge, Message, Report
from operations.steps import unfenced


def merge_outcome(aid: str, command: str, time: float, result: str | None, error: bool,
                  subjects: dict[str, float], undecided: list[str]) -> Merge | None:
    """What a Bash call of the loop `aid` of `command` at `time` that
    `merge_change.py` runs did, or None for any other call, one that
    merges no change, as a call of its `--help`, and one still pending. A
    call the harness refused, an error with no line of the script's own,
    never ran. A call whose output gives that `master` is fast-forwarded
    and the worktree stays for changes made after the commit left edits.
    Otherwise it merged where `master` holds, by `subjects`, the
    time of the latest commit of `master` with each subject, a commit made
    at or after the call with the message of each change it merges,
    whatever its exit status, as through a pipe; and otherwise the
    output's own forms give what it did. A call whose quoting cannot be
    read has no outcome, and an `undecided` line names it."""
    if MERGE_SCRIPT not in command or result is None:
        return None
    messages = merge_messages(command)
    if messages is None:
        undecided.append(mctx("{run}: the quoting of the merge call `{command}` cannot be "
                              "read").format(run=aid, command=command))
        return None
    if not messages:
        return None
    if error and not ran(result):
        return Merge.NOT_RUN
    if left_edits(result):
        return Merge.LEFT_EDITS
    if all(subjects.get(m, -math.inf) >= math.floor(time) for m in messages):
        return Merge.MERGED
    if not ran(result):
        return Merge.NOT_RUN
    return Merge.CONFLICT if conflicted(result) else Merge.REFUSED


def pass_tickets(report: str, main: Path) -> tuple[str, ...] | None:
    """The numbers the report whose path a pass replied with lists under
    `## Tickets filed`, or None where the reply is no report's path."""
    text = report.strip()
    if "\n" in text or not text:
        return None
    path = Path(text) if Path(text).is_absolute() else main / text
    if not path.is_file():
        return None
    body = path.read_text().split(TICKETS_FILED, 1)
    if len(body) < 2:
        return None
    section = body[1].split("\n## ", 1)[0]
    return tuple(m.group(0).rstrip("_") for m in re.finditer(
        rf"{TICKET_NUMBER.pattern}_", section))


FILED_FIELDS = {"Agent": "prompt", "SendMessage": "message"}
"""The field of each tool's input that may give a file the command wrote."""


def unfiled_call(aid: str, tool: str, inp: dict[str, Any], result: str | None,
                 undecided: list[str]) -> tuple[dict[str, Any], str | None]:
    """The input and the result of a call of the loop `aid`, with each
    file the command wrote, that the field `FILED_FIELDS` gives, read in
    place of the line that gives it (`filed_texts.unfiled`), and that field
    read without fence lines (`steps.unfenced`)."""
    where = mctx("{run}: a call of {tool}").format(run=aid, tool=tool)
    if (name := FILED_FIELDS.get(tool)) is not None:
        inp = {**inp, name: unfiled(unfenced(str(inp.get(name, ""))), where, undecided)}
    return inp, result


def final_reply(path: Path) -> Report | None:
    """The final reply in the transcript at `path`: the text of the entry
    that ends its last turn, or the message of the call that ends it, where
    its turn has ended."""
    if not has_ended(path):
        return None
    entries = run_entries(path)
    _, ends = turns(entries)
    if not ends:
        return None
    e = entries[max(ends)]
    stamp = e.get("timestamp")
    if not stamp:
        return None
    if e.get("type") == "assistant":
        text = "\n".join(str(b.get("text", "")) for b in blocks(e, "text"))
    else:
        ended = {b.get("tool_use_id") for b in blocks(e, "tool_result")}
        text = next((str((b.get("input") or {}).get("message", ""))
                     for x in entries if x.get("type") == "assistant"
                     for b in blocks(x, "tool_use") if b.get("id") in ended), "")
    return Report(epoch(stamp), text) if text.strip() else None


def reply_since(agent: str, since: float) -> Report | None:
    """The final reply in the transcript of `agent`, where it gives one
    after `since`."""
    r = final_reply(find(agent))
    return r if r is not None and r.time > since else None


def stalled_reports(agents: list[Agent], messages: list[Message]) -> dict[str, Report]:
    """The final reply in the transcript of each agent a stall alert names
    that is pending, given after its launch."""
    out: dict[str, Report] = {}
    pending = {a.agent_id: a for a in agents if a.pending and a.agent_id}
    for m in messages:
        alert = alerts.parsed(m) if m.sender is not None else None
        if alert is None or alert.kind is not alerts.AlertKind.STALL:
            continue
        a = pending.get(alert.agent)
        if a is None or alert.agent in out:
            continue
        r = reply_since(alert.agent, a.launched)
        if r is not None:
            out[alert.agent] = r
    return out


def ended_with(a: Agent, reply: Report | None) -> Agent:
    """`a` as no longer pending, with `reply` as its last report."""
    return replace(a, pending=False, reports=a.reports if reply is None else (*a.reports, reply))
