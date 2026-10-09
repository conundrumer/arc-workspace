"""The reads of the transcripts of a session's operators: the operators
that ran `operate.py`, each operator's calls, the messages it received, each read in place of the filed line that
gives it, and
the agents it launched, with their reports and the agents each doc
reviewer sent a message, the outcome of its merge
calls, and the tickets its solver passes filed."""

import math
import re
from dataclasses import replace
from pathlib import Path
from typing import Any

from agent_launches import launched, resumes, run_launches, sent_to, timed_entries, turn_signs
from agent_reports import ENDED, Sign, last_sign
from agent_turns import first_time, has_ended, turns
from context_bound_hook import OPERATOR
from controlled_markdown import mctx
from filed_texts import unfiled
from merge_change import conflicted, left_edits, ran
from open_agents import work_open
from run_reads import (BACKGROUND_TASK, MAIN, agent_messages, agent_type, blocks, is_prompt,
                       message_text, notifications, output_file, run_entries,
                       run_sessions, session_agents, text_of, type_in)
from run_reads import Status as TaskStatus
from senders import AUDITOR, Sender, sender
from ticket_numbers import TICKET_NUMBER
from transcripts import epoch, find, read_entries, session_directory

from operations import alerts
from operations.merging import MERGE_SCRIPT, merge_messages
from operations.reports import TICKETS_FILED
from operations.roles import PASSES, Role, described
from operations.state import Agent, Call, Merge, Message, Report
from operations.steps import COMMAND, is_next, unfenced


def merge_outcome(aid: str, command: str, time: float, result: str | None, error: bool,
                  subjects: dict[str, float], undecided: list[str]) -> Merge | None:
    """What a Bash call of the operator `aid` of `command` at `time` that
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
    """The input and the result of a call of the operator `aid`, with each
    file the command wrote, that the field `FILED_FIELDS` gives or the
    result of a call of `next` gives, read in place of the line that gives
    it (`filed_texts.unfiled`), and that field read without the fence
    lines an operator passed with it (`steps.unfenced`)."""
    where = mctx("{run}: a call of {tool}").format(run=aid, tool=tool)
    if (name := FILED_FIELDS.get(tool)) is not None:
        inp = {**inp, name: unfiled(unfenced(str(inp.get(name, ""))), where, undecided)}
    elif tool == "Bash" and result is not None and is_next(str(inp.get("command", "")), aid):
        result = unfiled(result, where, undecided)
    return inp, result


def ran_command(path: Path) -> bool:
    """Whether the transcript at `path` holds a Bash call of the command."""
    return any(b.get("name") == "Bash" and COMMAND in str((b.get("input") or {}).get("command"))
               for e in read_entries(path, naming={COMMAND}) if e.get("type") == "assistant"
               for b in blocks(e, "tool_use"))


def operator_runs(session: str, me: str) -> list[tuple[str, Path]]:
    """The operator `me` and each other operator of the session that ran
    the command, by agent id, in the order of their first entry. An
    operator that never ran the command left no work under its procedures.
    An operator whose transcript holds no timestamped entry has made no
    call yet, and is left out."""
    directory = session_directory(find(session))
    runs = [(aid, p, t) for aid, p in session_agents(directory).items()
            if agent_type(p) == OPERATOR and (aid == me or ran_command(p))
            and (t := first_time(p)) is not None]
    return [(aid, p) for aid, p, _ in sorted(runs, key=lambda r: r[2])]


WRAP = ("The coordinator sent a message while you were working:",
        "Address this before completing your current task.")
"""The lines the harness puts around a message from the coordinator that
arrives while the operator works."""


def unwrapped(text: str) -> str:
    return "\n".join(line for line in text.splitlines() if line.strip() not in WRAP)


def read_operator(aid: str, path: Path, main: Path, undecided: list[str],
                  agents: list[Agent], calls: list[Call], messages: list[Message],
                  passes: dict[str, tuple[str, ...] | None],
                  subjects: dict[str, float]) -> None:
    entries = run_entries(path)
    uses: dict[str, tuple[float, dict[str, Any], str]] = {}
    results: dict[str, tuple[str | None, bool]] = {}
    moved: dict[str, tuple[str, Path | None]] = {}
    tasks: dict[str, TaskStatus | None] = {}
    briefed = False
    children = run_launches(path)[1].get(aid, frozenset())
    sessions = run_sessions(path)
    for e in entries:
        stamp = e.get("timestamp")
        if e.get("type") == "assistant" and stamp:
            for b in blocks(e, "tool_use"):
                uses[b.get("id", "")] = (epoch(stamp), b.get("input") or {}, b.get("name", ""))
        elif e.get("type") == "user":
            result = e.get("toolUseResult")
            for b in blocks(e, "tool_result"):
                call = b.get("tool_use_id", "")
                results[call] = (text_of(b.get("content")), bool(b.get("is_error")))
                if isinstance(result, dict) and result.get(BACKGROUND_TASK):
                    moved[call] = (str(result[BACKGROUND_TASK]), output_file(b))
        if e.get("type") != "assistant":
            for n in notifications(e):
                for v in n.ids:
                    tasks[v] = n.status
        if stamp and is_prompt(e):
            if not briefed or sender(e, MAIN, frozenset(), sessions) is Sender.PARENT:
                briefed = True
                messages.append(Message(aid, epoch(stamp), None, unwrapped(message_text(e))))
            else:
                where = mctx("{run}: a message from").format(run=aid)
                messages += [Message(aid, epoch(stamp), s, unfiled(
                    unfenced(text), f"{where} {s}", undecided))
                             for s, text in agent_messages(e)
                             if s not in children or type_in(sessions, s) == AUDITOR]
    for call, (t, inp, tool) in uses.items():
        text, error = results.get(call, (None, False))
        if call in moved:
            text, error = background_output(aid, call, *moved[call], tasks, undecided)
        inp, text = unfiled_call(aid, tool, inp, text, undecided)
        uses[call] = (t, inp, tool)
        calls.append(Call(aid, t, tool, inp, text, error, merge_outcome(
            aid, str(inp.get("command", "")) if tool == "Bash" else "", t, text, error,
            subjects, undecided)))
    if not any(tool == "Agent" and described(str(inp.get("description", "")))
               for _, inp, tool in uses.values()):
        return
    found = launched(path, undecided)
    signs = turn_signs(path, [launch for launch in found if launch.pending])
    own = resumes(timed_entries(path), path.stem, None, undecided)
    for launch in found:
        use = uses.get(launch.call)
        if use is None:
            continue
        d = described(str(use[1].get("description", "")))
        if d is None:
            continue
        reports = tuple(Report(r.time, r.text) for r in launch.reports(0.0, undecided))
        sign = (signs.get(launch.agent or "") if launch.pending else
                last_sign(launch.entries, launch.since, {launch.agent or "", launch.call}))
        still = sign is Sign.STILL_RUNNING
        a = Agent(launch.agent, aid, d.role, d.subject, str(use[1].get("prompt", "")),
                  use[0], still or (launch.pending and sign not in ENDED), reports,
                  still_running=still,
                  notifies=launch.since <= max(use[0], own.get(launch.agent or "", 0.0)),
                  messaged=sent_to(launch.path) if d.role is Role.DOC_REVIEWER and launch.path
                  else None)
        if launch.pending and not a.pending and launch.agent:
            a = ended_with(a, None if any(r.time > launch.since for r in reports)
                           else reply_to(a, launch.since))
        agents.append(a)
        if d.role in PASSES and launch.agent and reports:
            passes[launch.agent] = pass_tickets(reports[-1].text, main)


def background_output(aid: str, call: str, task: str, output: Path | None,
                      tasks: dict[str, TaskStatus | None],
                      undecided: list[str]) -> tuple[str | None, bool]:
    """The result of the Bash call `call`, which the harness ran or moved
    to the background as task `task`, writing to `output`: None while no
    notification of the task reached the operator, and otherwise the
    output, as an error where the notification's status is not
    `completed`. An output whose file is gone, or named by no result, and
    a notification whose status is of no known form, are unknown: the call
    stays pending, and an `undecided` line names it."""
    if task not in tasks:
        return None, False
    status = tasks[task]
    if status is None or output is None or not output.is_file():
        undecided.append(mctx("{run}: the outcome of call {call}, which ran in the background "
                              "as task {task}, is unknown: {why}").format(
            run=aid, call=call, task=task,
            why=mctx("its notification's status is of no known form") if status is None
            else mctx("its output is gone")))
        return None, False
    return output.read_text(errors="replace"), status is not TaskStatus.COMPLETED


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


def reply_to(a: Agent, since: float) -> Report | None:
    """The final reply in the transcript of `a` after `since`, where its
    operator launched or last resumed it itself, so that reply went to
    that operator, or None."""
    return reply_since(a.agent_id, since) if a.agent_id and a.notifies else None


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


def ended_elsewhere(agents: list[Agent], me: str) -> dict[str, Report | None]:
    """For each pending agent of another operator whose work is no longer
    open, an agent whose report reaches no running operator, the final
    reply in its transcript, where it gives one after its launch and went
    to that operator (`reply_to`), or None."""
    out: dict[str, Report | None] = {}
    for a in agents:
        if not a.pending or a.operator == me or a.agent_id is None or a.agent_id in out:
            continue
        path = find(a.agent_id)
        if work_open(path, []):
            continue
        out[a.agent_id] = reply_to(a, a.launched)
    return out
