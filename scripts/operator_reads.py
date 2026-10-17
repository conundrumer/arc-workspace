"""The reads of the transcripts of a session's operators: the operators
that ran `operate.py`, each operator's calls, the messages it received, each read in place of the filed line that
gives it, and
the agents it launched, with their reports and the agents each doc
reviewer sent a message, the outcome of its merge
calls, and the tickets its solver passes filed."""

import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from agent_launches import children_of, launched, launches
from agent_resumes import resumes, sent_to
from agents_pending import turn_signs
from agent_reports import ENDED, Sign, last_sign
from agent_turns import first_time, has_ended, turns
from context_bound_hook import OPERATOR
from controlled_markdown import mctx
from filed_texts import report_file, report_text, unfiled
from merge_change import conflict_paths, left_edits, ran
from open_agents import work_open
from pending_wait_hook import bound_denied
from run_reads import (BACKGROUND_TASK, MAIN, agent_messages, agent_type, blocks, is_prompt,
                       message_text, notifications, output_file, parent_id, run_entries,
                       run_sessions, session_agents, tool_results)
from run_reads import Status as TaskStatus
from senders import Origin, Sender, origin, sender
from file_reads import file_text, is_dir, is_file, listed, mtime
from state_reads import DERIVED, Kept, state_cache
from ticket_numbers import TICKET_NUMBER
from transcripts import find, session_directory
from transcript_entries import epoch, read_entries

from operations.merging import MERGE_SCRIPT, merge_messages
from operations.reports import CONCEPT_FAULTS, TICKETS_FILED, section, section_items
from operations.roles import PASSES, Role, described
from operations.state import (
    Agent, Call, Merge, Message, PassReport, Report, Tool, Waits,
)
from operations.task_work import refine_report, tasks_work
from operations.command_words import COMMAND, is_next
from operations.printing import unfenced


def merge_outcome(aid: str, command: str, time: float, result: str | None, error: bool,
                  subjects: Mapping[str, float], denied: set[str],
                  undecided: list[str]) -> Merge | None:
    """What a Bash call of the operator `aid` of `command` at `time` that
    `merge_change.py` runs did, or None for any other call, one that
    merges no change, as a call of its `--help`, and one still pending. A
    call the harness refused, an error with no line of the script's own,
    never ran. A call that `pending_wait_hook` denied for its timeout has
    no outcome either, so the merge call is given again, unless the
    operator's last merge call of `command` was denied so too: `denied`
    holds each command whose last merge call was, read in the order of
    the calls, and that second denial never ran. A call whose output gives that `master` is fast-forwarded
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
        if bound_denied(result) and command not in denied:
            denied.add(command)
            return None
        denied.discard(command)
        return Merge.NOT_RUN
    denied.discard(command)
    if left_edits(result):
        return Merge.LEFT_EDITS
    if all(subjects.get(m, -math.inf) >= math.floor(time) for m in messages):
        return Merge.MERGED
    if not ran(result):
        return Merge.NOT_RUN
    return Merge.REFUSED if conflict_paths(result) is None else Merge.CONFLICT


def pass_report(task: str, role: Role, launched: float, main: Path) -> Path | None:
    """The report file the pass of `role` on `task` wrote since its launch
    at `launched`, as `docs/handbook/procedure.md` names it: for Refine,
    the `refine-<n>.md` first written after the launch."""
    work = tasks_work(main) / task
    if not is_dir(work):
        return None
    files = (sorted(work / e.name for e in listed(work) if refine_report(e.name))
             if role is Role.REFINE else [work / f"{role.value}.md"])
    written = [(mtime(p), p) for p in files if is_file(p)]
    return min(((t, p) for t, p in written if t > launched), default=(0.0, None))[1]


def pass_read(task: str, role: Role, launched: float, main: Path) -> PassReport:
    """The read of the report file of the pass (`PassReport`)."""
    path = pass_report(task, role, launched, main)
    if path is None:
        return PassReport(None, ())
    text = file_text(path)
    filed = section(text, TICKETS_FILED)
    tickets = None if filed is None else tuple(m.group(0).rstrip("_") for m in re.finditer(
        rf"(?<![\w-]){TICKET_NUMBER.pattern}_", filed))
    return PassReport(tickets, section_items(text, CONCEPT_FAULTS))


FILED_FIELDS: dict[str, str] = {Tool.AGENT: "prompt", Tool.SEND_MESSAGE: "message"}
"""The field of each tool's input that may give a file the command wrote."""


def unfiled_call(aid: str, tool: str, inp: dict[str, Any], result: str | None,
                 undecided: list[str]) -> tuple[dict[str, Any], str | None]:
    """The input and the result of a call of the operator `aid`, with each
    file the command wrote, that the field `FILED_FIELDS` gives or the
    result of a call of `next` gives, read in place of the line that gives
    it (`filed_texts.unfiled`), and that field read without the fence
    lines an operator passed with it (`operations.printing.unfenced`)."""
    where = mctx("{run}: a call of {tool}").format(run=aid, tool=tool)
    if (name := FILED_FIELDS.get(tool)) is not None:
        inp = {**inp, name: unfiled(unfenced(str(inp.get(name, ""))), where, undecided)}
    elif tool == Tool.BASH and result is not None and is_next(str(inp.get("command", "")), aid):
        result = unfiled(result, where, undecided)
    return inp, result


@state_cache(DERIVED, kept=Kept.DISK)
def ran_command(path: Path) -> bool:
    """Whether the transcript at `path` holds a Bash call of the command."""
    return any(b.get("name") == Tool.BASH and COMMAND in str((b.get("input") or {}).get("command"))
               for e in read_entries(path, naming={COMMAND}) if e.get("type") == "assistant"
               for b in blocks(e, "tool_use"))


def operator_runs(session: str, me: str) -> list[tuple[str, Path]]:
    """The operator `me` and each other operator of the session that ran
    the command, by agent id, in the order of their first entry. An
    operator that never ran the command left no work under its procedures.
    An operator whose transcript holds no timestamped entry has made no
    call yet, and is left out."""
    return list(session_operators(session, me))


@state_cache(DERIVED)
def session_operators(session: str, me: str) -> tuple[tuple[str, Path], ...]:
    """`operator_runs`, held."""
    directory = session_directory(find(session))
    runs = [(aid, p, t) for aid, p in session_agents(directory).items()
            if agent_type(p) == OPERATOR and (aid == me or ran_command(p))
            and (t := first_time(p)) is not None]
    return tuple((aid, p) for aid, p, _ in sorted(runs, key=lambda r: r[2]))


@state_cache(DERIVED, notes="undecided", kept=Kept.DISK)
def resumed_at(aid: str, path: Path, undecided: list[str]) -> list[float]:
    """The time of each resume of the agent `aid` whose transcript is at
    `path`. A resume is as `ALERTS` in `src/operations/monitor.py` gives
    it."""
    out: list[float] = []
    ended = False
    for e in run_entries(path):
        if e.get("toolEndsTurn"):
            ended = True
        elif e.get("type") == "assistant":
            ended = False
        elif ended and is_prompt(e):
            ended = False
            if e.get("timestamp"):
                t = epoch(e["timestamp"])
                if not by_callees(path, e, t, undecided):
                    out.append(t)
            else:
                undecided.append(mctx("{run}: a prompt resumed it after its run ended, yet its "
                                      "entry gives no time, so it counts as no "
                                      "resume").format(run=aid))
    return out


def by_callees(path: Path, e: dict[str, Any], t: float, undecided: list[str]) -> bool:
    senders = [s for s, _ in agent_messages(e)]
    notes = notifications(e)
    if not senders and not notes:
        return False
    mine = {a.agent for a in launches(path, undecided) if a.agent and a.since < t}
    mine |= resumes(path, undecided, before=t).keys()
    return (all(s in mine for s in senders)
            and all(any(i in mine for i in n.ids) for n in notes))


WRAP = ("The coordinator sent a message while you were working:",
        "Address this before completing your current task.")
"""The lines the harness puts around a message from the coordinator that
arrives while the operator works."""


MESSAGE_FROM = mctx("{run}: a message from")


def unwrapped(text: str) -> str:
    return "\n".join(line for line in text.splitlines() if line.strip() not in WRAP).strip()


def from_parent(aid: str, e: dict[str, Any], parent: str, undecided: list[str]) -> str:
    """The text of the brief, or of the message from `parent`, that the
    entry `e` of the operator `aid` gives, where `parent` is the operator's
    parent, or `main` for a message of the coordinator's. An operator
    launcher's brief and messages are files the command wrote, read in
    place of the line that gives each, and a message of its arrives in the
    form of any agent's."""
    text = unwrapped(message_text(e))
    if parent == MAIN:
        return text
    given = [t for s, t in agent_messages(e) if s == parent]
    where = MESSAGE_FROM.format(run=aid)
    return unfiled(unfenced("\n".join(given) if given else text), f"{where} {parent}",
                   undecided)


MESSAGING = frozenset({Role.DOC_REVIEWER, Role.ITEM_CHECKER})
"""The roles whose `TranscriptsRead.messaged` the command reads."""


@dataclass(frozen=True)
class AgentsRead:
    """Agents read from transcripts, with the parts of
    `TranscriptsRead.messaged` and `TranscriptsRead.limited` for them."""
    agents: tuple[Agent, ...]
    messaged: Mapping[str, frozenset[str]]
    limited: Mapping[str, float]


def joined(reads: Sequence[AgentsRead]) -> AgentsRead:
    """The agents of `reads`, in their order, with their mappings merged."""
    return AgentsRead(tuple(a for r in reads for a in r.agents),
                      {k: v for r in reads for k, v in r.messaged.items()},
                      {k: v for r in reads for k, v in r.limited.items()})


def kept(agents: Sequence[Agent], reads: Sequence[AgentsRead]) -> AgentsRead:
    """`agents`, with the parts of the mappings of `reads` for them."""
    ids = {a.agent_id for a in agents}
    whole = joined(reads)
    return AgentsRead(tuple(agents),
                      {k: v for k, v in whole.messaged.items() if k in ids},
                      {k: v for k, v in whole.limited.items() if k in ids})


@dataclass(frozen=True)
class OperatorRead:
    """What the transcript of one operator gives: its launches, its calls,
    the messages that reached it, and `passes`, for each solver pass it
    launched with an agent id, the read of its report
    (`TranscriptsRead.pass_reports`)."""
    launched: AgentsRead
    calls: tuple[Call, ...]
    messages: tuple[Message, ...]
    passes: Mapping[str, PassReport]

    @property
    def agents(self) -> tuple[Agent, ...]:
        return self.launched.agents


def read_operator(aid: str, path: Path, main: Path, undecided: list[str],
                  subjects: Mapping[str, float]) -> OperatorRead:
    """What the transcript at `path` of the operator `aid` gives. A message
    from the operator's parent, the coordinator or the operator launcher
    that launched it, or from the coordinator where the parent is an
    operator launcher, is read as a message of the coordinator's."""
    merged = merge_subjects(path)
    return operator_read(aid, path, main, undecided,
                         frozenset((m, t) for m, t in subjects.items() if m in merged))


@state_cache(DERIVED, kept=Kept.DISK)
def merge_subjects(path: Path) -> frozenset[str]:
    """The commit messages the merge calls of the run at `path` give
    (`operations.merging.merge_messages`), the subjects `merge_outcome`
    looks up."""
    return frozenset(m for e in run_entries(path, naming={MERGE_SCRIPT})
                     if e.get("type") == "assistant" for b in blocks(e, "tool_use")
                     if b.get("name") == Tool.BASH
                     and MERGE_SCRIPT in (command := str((b.get("input") or {}).get("command", "")))
                     for m in merge_messages(command) or ())


@state_cache(DERIVED, notes="undecided", kept=Kept.DISK)
def operator_read(aid: str, path: Path, main: Path, undecided: list[str],
                  commits: frozenset[tuple[str, float]]) -> OperatorRead:
    """`read_operator`, with `subjects` as the pairs `commits` gives, those
    of `merge_subjects`."""
    subjects = dict(commits)
    agents: list[Agent] = []
    calls: list[Call] = []
    messages: list[Message] = []
    passes: dict[str, PassReport] = {}
    messaged: dict[str, frozenset[str]] = {}
    limited: dict[str, float] = {}
    entries = run_entries(path)
    uses: dict[str, tuple[float, dict[str, Any], str]] = {}
    results: dict[str, tuple[str | None, bool]] = {}
    moved: dict[str, tuple[str, Path | None]] = {}
    tasks: dict[str, TaskStatus | None] = {}
    briefed = False
    children = children_of(path, aid)
    sessions = run_sessions(path)
    parent = parent_id(path)
    for e in entries:
        stamp = e.get("timestamp")
        if e.get("type") == "assistant" and stamp:
            for b in blocks(e, "tool_use"):
                uses[b.get("id", "")] = (epoch(stamp), b.get("input") or {}, b.get("name", ""))
        elif e.get("type") == "user":
            result = e.get("toolUseResult")
            for call, b, text in tool_results(e):
                results[call] = (text, bool(b.get("is_error")))
                if isinstance(result, dict) and result.get(BACKGROUND_TASK):
                    moved[call] = (str(result[BACKGROUND_TASK]), output_file(b))
        if e.get("type") != "assistant":
            for n in notifications(e):
                for v in n.ids:
                    tasks[v] = n.status
        if stamp and is_prompt(e):
            direct = origin(e)[1] is Origin.COORDINATOR
            if not briefed or direct or sender(e, parent, frozenset(), sessions) is Sender.PARENT:
                briefed = True
                messages.append(Message(aid, epoch(stamp), None, from_parent(
                    aid, e, MAIN if direct else parent, undecided)))
            else:
                where = MESSAGE_FROM.format(run=aid)
                messages += [Message(aid, epoch(stamp), s, unfiled(
                    unfenced(text), f"{where} {s}", undecided))
                             for s, text in agent_messages(e) if s not in children]
    denied: set[str] = set()
    for call, (t, inp, tool) in uses.items():
        text, error = results.get(call, (None, False))
        if call in moved:
            text, error = background_output(aid, call, *moved[call], tasks, undecided)
        inp, text = unfiled_call(aid, tool, inp, text, undecided)
        uses[call] = (t, inp, tool)
        merge = merge_outcome(aid, str(inp.get("command", "")) if tool == Tool.BASH else "",
                              t, text, error, subjects, denied, undecided)
        conflicts = conflict_paths(text or "") if merge is Merge.CONFLICT else None
        calls.append(Call(aid, t, tool, inp, text, error, merge, conflicts or ()))
    if not any(tool == Tool.AGENT and described(str(inp.get("description", "")))
               for _, inp, tool in uses.values()):
        return OperatorRead(AgentsRead((), {}, {}), tuple(calls), tuple(messages), {})
    found = launched(path, undecided)
    signs = turn_signs(path, [launch for launch in found if launch.pending])
    own = resumes(path, undecided)
    for launch in found:
        use = uses.get(launch.call)
        if use is None:
            continue
        d = described(str(use[1].get("description", "")))
        if d is None:
            continue
        reports = tuple(Report(r.time, r.text, r.file) for r in launch.reports(0.0, undecided))
        signed = (signs.get(launch.agent or "") if launch.pending else
                  last_sign(launch.entries, launch.since, {launch.agent or "", launch.call}))
        a = Agent(launch.agent, aid, d.role, d.subject, str(use[1].get("prompt", "")),
                  use[0], waits(signed, launch.pending), reports,
                  notifies=launch.since <= max(use[0], own.get(launch.agent or "", 0.0)))
        if d.role in MESSAGING and launch.path and launch.agent is not None:
            messaged[launch.agent] = sent_to(launch.path)
        if signed is not None and signed[0] is Sign.LIMITED and launch.agent is not None:
            limited[launch.agent] = signed[1]
        if not a.pending and launch.agent:
            a = ended_with(a, None if any(r.time > launch.since for r in reports)
                           else reply_to(a, launch.since, undecided))
        agents.append(a)
        if d.role in PASSES and launch.agent:
            passes[launch.agent] = pass_read(d.subject, d.role, use[0], main)
    return OperatorRead(AgentsRead(tuple(agents), messaged, limited), tuple(calls),
                        tuple(messages), passes)


def waits(signed: tuple[Sign, float] | None, pending: bool) -> Waits | None:
    """`Agent.waits` of a launch whose latest sign is the first of
    `signed`, where `pending` gives whether the launch's result has not
    reached its operator."""
    match signed:
        case (Sign.STILL_RUNNING, _):
            return Waits.STILL_RUNNING
        case (Sign.LIMITED, _):
            return Waits.LIMITED
        case (sign, _) if sign in ENDED:
            return None
        case _:
            return Waits.AT_WORK if pending else None


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
    if status is None or output is None or not is_file(output):
        undecided.append(mctx("{run}: the outcome of call {call}, which ran in the background "
                              "as task {task}, is unknown: {why}").format(
            run=aid, call=call, task=task,
            why=mctx("its notification's status is of no known form") if status is None
            else mctx("its output is gone")))
        return None, False
    return file_text(output, "replace"), status is not TaskStatus.COMPLETED


@state_cache(DERIVED, kept=Kept.DISK)
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


def reply_to(a: Agent, since: float, undecided: list[str]) -> Report | None:
    """The final reply in the transcript of `a` after `since`, where its
    operator launched or last resumed it itself, so that reply went to
    that operator, or where it is the path of a report file alone
    (`filed_texts.report_file`), whichever agent it went to, read from
    that file, or None. A reply whose file is gone keeps the path as its
    text."""
    r = reply_since(a.agent_id, since) if a.agent_id else None
    path = report_file(r.text) if r is not None else None
    if r is None or path is None:
        return r if a.notifies else None
    text = report_text(path, a.agent_id or "", undecided)
    return r if text is None else replace(r, text=text, file=path)


def stalled_reports(agents: list[Agent], coordinators: dict[str, float],
                    stalls: list[str]) -> dict[str, Report]:
    """The final reply in the transcript of each agent of `stalls`, the
    agents whose `stall` reading fired (`operations.monitor`), that is
    pending, or that the coordinator launched, by `coordinators`, their
    launch times, given after its launch."""
    out: dict[str, Report] = {}
    launched = {a.agent_id: a.launched for a in agents if a.pending and a.agent_id}
    for agent in stalls:
        since = launched[agent] if agent in launched else coordinators.get(agent)
        if since is None or agent in out:
            continue
        r = reply_since(agent, since)
        if r is not None:
            out[agent] = r
    return out


def ended_with(a: Agent, reply: Report | None) -> Agent:
    """`a` as no longer pending, with `reply` as its last report."""
    return replace(a, waits=None, reports=a.reports if reply is None else (*a.reports, reply))


def ended_by(agents: Sequence[Agent], ended: Mapping[str, Report | None]) -> list[Agent]:
    """`agents`, each pending one of `ended` ended with the report it gives
    (`ended_with`)."""
    return [ended_with(a, ended[a.agent_id])
            if a.pending and a.agent_id is not None and a.agent_id in ended else a
            for a in agents]


def ended_elsewhere(agents: list[Agent], me: str,
                    undecided: list[str]) -> dict[str, Report | None]:
    """For each pending agent of another operator whose work is no longer
    open, an agent whose report reaches no running operator, the final
    reply in its transcript that `reply_to` gives after its launch, or
    None."""
    out: dict[str, Report | None] = {}
    for a in agents:
        if not a.pending or a.operator == me or a.agent_id is None or a.agent_id in out:
            continue
        path = find(a.agent_id)
        if work_open(path, []):
            continue
        out[a.agent_id] = reply_to(a, a.launched, undecided)
    return out
