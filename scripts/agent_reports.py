"""The received reports of an agent, as
`profile_runs.py --help one` gives them, and the signs in session transcripts that
its turn ended.

The forms of the harness that `profile_runs.py --help one` rests on are `HAND_BACK` and
`HAND_BACK_INDENT`, of a message that delivers a SubagentHandback report,
`POINTER`, of a notification that points to such a message, and
`SENT_BY_MESSAGE`, of the line an agent gives after it sent its final reply
by SendMessage."""

import re
from collections.abc import Iterable
from dataclasses import dataclass, replace
from enum import Enum
from pathlib import Path

from controlled_markdown import mctx
from filed_texts import report_file, report_text
from operations.printed_forms import SENT_BY_MESSAGE
from run_reads import (MAIN, LaunchStatus, Notification, Status, agent_messages, agent_type,
                       blocks, is_prompt, launch_status, notifications, notified, parent_id,
                       read_meta, run_sessions, session_agents, text_of)
from file_reads import is_file
from transcripts import agent_id, chain, find, main_transcript
from entry_reads import line_entries
from session_changes import agents_facts
from state_reads import DERIVED, Kept, state_cache
from transcript_folds import fold
from transcript_entries import epoch
from transcript_snapshots import Entry

# The opening of the note of a notification that the agent stopped with work
# of its own still running.
STILL_RUNNING = "This agent stopped with background work of its own still running"

# The words of the summary of a notification of status `failed` that the
# usage limit stopped the agent.
RATE_LIMIT = "error type rate_limit"

HAND_BACK = re.compile(r"\A\[Subagent hand-back\] [^\n]*The report follows:\n")
"""The preamble of a message that delivers an agent's SubagentHandback
report, on the message's first line."""

HAND_BACK_INDENT = "  "
"""The indent the harness puts before each line of a SubagentHandback
report."""

POINTER = re.compile(r'\AThis agent\'s report was delivered to you as a message from "[^"]+" '
                     r"\(its SubagentHandback call\)\. Read it there; it is not repeated here\.\Z")
"""The whole result of a notification whose agent's report reached the
receiver as a SubagentHandback message."""


def gives_text(text: str) -> bool:
    """Whether a report whose text is `text` gives report text: it is
    neither the harness's pointer nor the line an agent gives after it sent
    its final reply by SendMessage."""
    return not any(form.match(text) for form in (POINTER, SENT_BY_MESSAGE))


class ReportKind(Enum):
    """The entries of a session transcript that give a report of an agent,
    as `profile_runs.py --help one` gives them."""
    NOTIFICATION = "notification"
    RESULT = "result"
    MESSAGE = "message"


# The kinds of report that the harness gives the parent once the agent's turn
# has ended.
TURN_ENDED = frozenset({ReportKind.NOTIFICATION, ReportKind.RESULT})


@dataclass(slots=True)
class Report:
    """A report of an agent. `file` is the report file its text was read
    from, or None where the text is the received report."""
    kind: ReportKind
    time: float
    text: str
    file: Path | None = None


class Sign(Enum):
    """What an entry of session transcripts says of an agent's turn: a
    notification that it stopped (`is_stop`), a SubagentHandback message
    from it, a notification that it stopped with background work of its
    own still running, which says it has not reported yet, a notification
    that the usage limit stopped it (`limit_stop`), which says it has not
    ended its work, or any other notification of it."""
    STOPPED = "stopped"
    HANDED_BACK = "handed back"
    STILL_RUNNING = "still running"
    LIMITED = "limited"
    OTHER = "other"


ENDED = frozenset({Sign.STOPPED, Sign.HANDED_BACK})
"""The signs that the agent's turn ended."""


def handed_back(text: str) -> str | None:
    """The report a message from an agent delivers by SubagentHandback,
    without the harness's preamble and indent, or None where the message
    is no such delivery. A line of the report that lacks the indent is
    kept as it stands."""
    m = HAND_BACK.match(text)
    if m is None:
        return None
    return "\n".join(line.removeprefix(HAND_BACK_INDENT)
                     for line in text[m.end():].split("\n")).strip()


def sign_of(n: Notification) -> Sign:
    if limit_stop(n):
        return Sign.LIMITED
    if is_stop(n):
        return Sign.STOPPED
    if still_running(n):
        return Sign.STILL_RUNNING
    return Sign.OTHER


def entry_signs(e: Entry) -> list[tuple[str, Sign]]:
    """Each id that `e`, an entry of session transcripts, gives a sign
    of, with that sign: the task id and the tool-use id of a notification,
    and the agent id of a SubagentHandback message."""
    if not can_report(e):
        return []
    out = [(v, sign_of(n)) for n in notifications(e) for v in n.ids]
    if is_prompt(e):
        out += [(who, Sign.HANDED_BACK) for who, text in agent_messages(e)
                if handed_back(text) is not None]
    return out


def last_sign(found: Iterable["AgentEntry"], since: float,
              ids: set[str]) -> tuple[Sign, float] | None:
    """`latest_sign` of `found` timestamped after `since`."""
    return latest_sign(((a.time, a.signs) for a in found if a.time > since), ids)


def latest_sign(timed: Iterable[tuple[float, Iterable[tuple[str, Sign]]]],
                ids: set[str]) -> tuple[Sign, float] | None:
    """The latest sign among `timed`, the signs of entries (`entry_signs`)
    each with its entry's time, of an agent that one of `ids` names, other
    than `Sign.OTHER`, with its time, or None. Of signs at one time, one of
    `ENDED` counts as the latest."""
    found: tuple[float, bool, Sign] | None = None
    for t, signs in timed:
        for v, sign in signs:
            if v in ids and sign is not Sign.OTHER:
                k = (t, sign in ENDED, sign)
                if found is None or k[:2] > found[:2]:
                    found = k
    return (found[2], found[0]) if found else None


def can_report(entry: Entry) -> bool:
    """Whether `entry` can give a report of an agent or a notification of
    it: it has a timestamp, and it is not the model's."""
    return bool(entry.get("timestamp")) and entry.get("type") != "assistant"


@dataclass(frozen=True, slots=True)
class AgentEntry:
    """What an entry of session transcripts that can give a report
    (`can_report`) gives of one agent: its time, its reports
    (`entry_reports`), whether it notifies that the agent stopped
    (`is_stop`), its signs (`entry_signs`), and the `undecided` lines that
    the reads of its reports and of its notifications give, so that a
    holder keeps these records in place of the entries."""
    time: float
    reports: tuple[Report, ...]
    report_notes: tuple[str, ...]
    stopped: bool
    stop_notes: tuple[str, ...]
    signs: tuple[tuple[str, Sign], ...]


def agent_entries(entries: Iterable[Entry], aid: str | None,
                  call: str | None) -> tuple[AgentEntry, ...]:
    """The `AgentEntry` of each of `entries` that can give a report, of the
    agent `aid`, launched by call `call`."""
    out: list[AgentEntry] = []
    for e in entries:
        if not can_report(e):
            continue
        report_notes: list[str] = []
        stop_notes: list[str] = []
        found = entry_reports(e, aid, call, report_notes)
        stopped = any(is_stop(n) for n in agent_notifications(e, aid, call, stop_notes))
        out.append(AgentEntry(epoch(e["timestamp"]), tuple(found), tuple(report_notes),
                              stopped, tuple(stop_notes), tuple(entry_signs(e))))
    return tuple(out)


def reports_after(found: Iterable[AgentEntry], since: float, aid: str | None,
                  call: str | None, undecided: list[str]) -> list[Report]:
    """The reports of `found` after `since`, of the agent `aid`, launched by
    call `call`, each that is the path of a
    report file alone (`filed_texts.report_file`) read from that file, which
    it keeps as its `file`. An agent writes each report to its report file
    in place of the one before, so only the latest report that gives a file
    is read from it, and an earlier one, or one whose file is gone, keeps
    the path as its text."""
    out: list[Report] = []
    for a in found:
        if a.time > since:
            undecided.extend(a.report_notes)
            out.extend(replace(r) for r in a.reports)
    out.sort(key=lambda r: r.time)
    latest = {path: r for r in out if (path := report_file(r.text)) is not None}
    for path, r in latest.items():
        where = aid if aid is not None else mctx("the agent of call {call}").format(call=call)
        text = report_text(path, where, undecided)
        if text is not None:
            r.text, r.file = text, path
    return out


def stopped_after(found: Iterable[AgentEntry], since: float, undecided: list[str]) -> bool:
    """Whether `found` hold a notification after `since` that the agent
    stopped."""
    for a in found:
        if a.time > since:
            undecided.extend(a.stop_notes)
            if a.stopped:
                return True
    return False


def parent_transcripts(path: Path) -> list[Path]:
    """The transcripts of the parent of the subagent at `path`, under the
    sessions of that subagent's run: the main transcript of each, or the
    transcripts of the parent's run."""
    parent = parent_id(path)
    sessions = run_sessions(path)
    if parent == MAIN:
        return [m for s in sessions if is_file(m := main_transcript(s))]
    runs = [chain(a) for s in sessions if (a := session_agents(s).get(parent))]
    return list(dict.fromkeys(p for run in runs for p in run))


def parent_type(path: Path) -> str | None:
    """The agent type of the parent of the subagent at `path`: `main` where
    that parent is the main session, and otherwise `agent_type` of the
    first of `parent_transcripts`, or, where none is found, of the
    transcript `find` gives the parent, whose `Refused` it raises."""
    parent = parent_id(path)
    if parent == MAIN:
        return MAIN
    found = parent_transcripts(path)
    return agent_type(found[0] if found else find(parent))


def reports(path: Path, since: float, undecided: list[str]) -> list[Report] | None:
    """The received reports of the subagent at `path` across its sessions,
    as `profile_runs.py --help one` gives them."""
    aid = agent_id(path)
    call = (read_meta(path) or {}).get("toolUseId")
    if not call:
        undecided.append(mctx("{run}: no `.meta.json` of its run gives a `toolUseId`, "
                              "so the result of its launch cannot be matched").format(run=aid))
    return reports_after(received_entries(tuple(run_sessions(path)), aid, call),
                         since, aid, call, undecided)


@dataclass(frozen=True, slots=True)
class ReportLine:
    """A line that can give a report or end sign, and its matching ids."""
    line: int
    ids: tuple[str, ...]


def delivery_entry(entry: Entry) -> Entry:
    """Expose an enqueued delivery to the report and sign parsers."""
    if entry.get("type") == "queue-operation" and entry.get("operation") == "enqueue":
        return {**entry, "type": "user", "message": {"content": entry.get("content")}}
    return entry


def add_report_line(out: list[ReportLine], _path: Path, line: int, entry: Entry) -> None:
    if ids := report_ids(delivery_entry(entry)):
        out.append(ReportLine(line, tuple(ids)))


REPORT_WORDS = frozenset({"<task-notification>", "<agent-message from=", '"tool_result"'})
"""Words present in the lines that `report_ids` can match."""


@state_cache(DERIVED, kept=Kept.DISK)
def report_lines(path: Path) -> tuple[ReportLine, ...]:
    """Compact report references, incrementally read from one transcript."""
    return tuple(fold(add_report_line, list[ReportLine], path, [path], REPORT_WORDS))


def line_ids(line: ReportLine) -> tuple[str, ...]:
    return line.ids


@state_cache(DERIVED, kept=Kept.VALUE)
def received_entries(sessions: tuple[Path, ...], aid: str | None,
                     call: str | None) -> tuple[AgentEntry, ...]:
    """Report and end entries matched once by agent or launch-call id in
    `sessions`. Time bounds apply to the decoded entry's timestamp."""
    ids = tuple(v for v in (aid, call) if v)
    found = agents_facts(sessions, 0.0, report_lines, line_ids, ids)
    return agent_entries((delivery_entry(e) for at in found
                          for e in line_entries(at.path, at.fact.line)),
                         aid, call)


def report_ids(entry: Entry) -> list[str]:
    """An entry of a session transcript that gives a report of an agent
    gives, among the ids this function returns, the agent id or the id of
    the call that launched it."""
    if not can_report(entry):
        return []
    ids = [*notified(entry),
           *(who for who, _ in (agent_messages(entry) if is_prompt(entry) else [])),
           *(b["tool_use_id"] for b in blocks(entry, "tool_result")
             if b.get("tool_use_id"))]
    return list(dict.fromkeys(ids))


def agent_notifications(e: Entry, aid: str | None, call: str | None,
                        undecided: list[str]) -> list[Notification]:
    """The notifications of the agent `aid`, launched by call `call`, that
    the timestamped entry `e` gives, other than one that gives no status
    (`Notification.has_status`), and one whose status is of no known form,
    which an `undecided` line names."""
    out: list[Notification] = []
    for n in notifications(e):
        if ((aid is None or aid not in n.ids) and call not in n.ids) or not n.has_status:
            continue
        if n.status is None:
            undecided.append(mctx("{run}: a notification of it at {time} gives "
                                  "the status `{status}`, of no known form").format(
                run=aid, time=e["timestamp"], status=n.status_text))
        else:
            out.append(n)
    return out


def is_stop(n: Notification) -> bool:
    """Whether `n` says the agent stopped: a notification of a known status
    other than `running`, other than one that says the agent stopped with
    background work of its own still running."""
    return (n.status not in (None, Status.RUNNING)
            and not still_running(n))


def limit_stop(n: Notification) -> bool:
    """Whether `n` says the usage limit stopped the agent: a notification
    of status `failed` whose summary gives `RATE_LIMIT`."""
    return n.status is Status.FAILED and RATE_LIMIT in (n.summary or "")


def still_running(n: Notification) -> bool:
    """Whether the note of `n` says the agent stopped with background work
    of its own still running."""
    return (n.note or "").startswith(STILL_RUNNING)


def entry_reports(e: Entry, aid: str | None, call: str | None,
                  undecided: list[str]) -> list[Report]:
    """The reports of the agent `aid`, launched by call `call`, that the
    timestamped entry `e` of session transcripts gives, as
    `profile_runs.py --help one` gives them."""
    t = epoch(e["timestamp"])
    out = [Report(ReportKind.NOTIFICATION, t, n.result.strip())
           for n in agent_notifications(e, aid, call, undecided)
           if n.status is Status.COMPLETED and n.result is not None and is_stop(n)]
    if is_prompt(e):
        out.extend(Report(ReportKind.MESSAGE, t, report if (report := handed_back(text)) is not None
                          else text)
                   for who, text in agent_messages(e) if aid is not None and who == aid)
    result = e.get("toolUseResult")
    if call and isinstance(result, dict) and any(
            b.get("tool_use_id") == call for b in blocks(e, "tool_result")):
        if launch_status(result, undecided, call) is LaunchStatus.COMPLETED:
            out.append(Report(ReportKind.RESULT, t,
                              text_of(result.get("content")).strip()))
    return [r for r in out if gives_text(r.text.strip())]
