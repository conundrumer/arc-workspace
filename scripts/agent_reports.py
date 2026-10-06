"""The reports of an agent that reached its parent, as the HELP of
`profile_runs` gives them."""

from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from controlled_markdown import mctx
from quota import epoch
from run_reads import (MAIN, LaunchStatus, Status, agent_messages, blocks, is_prompt,
                       launch_status, notifications, notified, parent_id, read_meta,
                       session_agents, session_of, text_of)
from transcripts import Entry, agent_id, chain, main_transcript, read_entries

# The opening of the note of a notification that the agent stopped with work
# of its own still running.
STILL_RUNNING = "This agent stopped with background work of its own still running"


class ReportKind(Enum):
    """The entries of a parent's transcript that give a report of an agent,
    as HELP gives them."""
    NOTIFICATION = "notification"
    RESULT = "result"
    MESSAGE = "message"


# The kinds of report that the harness gives the parent once the agent's turn
# has ended.
TURN_ENDED = frozenset({ReportKind.NOTIFICATION, ReportKind.RESULT})


@dataclass
class Report:
    kind: ReportKind
    time: float
    text: str


def reports_after(entries: Iterable[Entry], since: float, aid: str | None,
                  call: str | None, undecided: list[str]) -> list[Report]:
    """The reports of the agent `aid`, launched by call `call`, among
    `entries` of its parent's transcripts."""
    return sorted((r for e in entries
                   if e.get("timestamp") and epoch(e["timestamp"]) > since
                   for r in entry_reports(e, aid, call, undecided)),
                  key=lambda r: r.time)


def parent_transcripts(path: Path) -> list[Path]:
    """The transcripts of the parent of the subagent at `path`, under the
    sessions of that subagent's run: the main transcript of each, or the
    transcripts of the parent's run."""
    parent = parent_id(path)
    sessions = dict.fromkeys(session_of(p) for p in chain(path))
    if parent == MAIN:
        return [m for s in sessions if (m := main_transcript(s)).is_file()]
    runs = [chain(a) for s in sessions if (a := session_agents(s).get(parent))]
    return list(dict.fromkeys(p for run in runs for p in run))


def reports(path: Path, since: float, undecided: list[str]) -> list[Report] | None:
    """Only the lines of the parent's transcripts that hold the agent id of
    the subagent at `path` or the id of the call that launched it are read,
    which the line of every entry that gives a report of it holds one
    of."""
    aid = agent_id(path)
    found = parent_transcripts(path)
    if not found:
        undecided.append(mctx("{run}: no transcript of its parent is found, so "
                              "whether a report reached it is unknown").format(run=aid))
        return None
    call = (read_meta(path) or {}).get("toolUseId")
    if not call:
        undecided.append(mctx("{run}: no `.meta.json` of its run gives a `toolUseId`, "
                              "so the result of its launch cannot be matched").format(run=aid))
    words = {aid, call} if call else {aid}
    return reports_after((e for p in found for e in read_entries(p, naming=words)),
                         since, aid, call, undecided)


def report_ids(entry: Entry) -> list[str]:
    """An entry of a parent's transcript that gives a report of an agent
    gives, among the ids this function returns, the agent id or the id of
    the call that launched it."""
    if not entry.get("timestamp") or entry.get("type") == "assistant":
        return []
    ids = [*notified(entry),
           *(who for who, _ in (agent_messages(entry) if is_prompt(entry) else [])),
           *(b["tool_use_id"] for b in blocks(entry, "tool_result")
             if b.get("tool_use_id"))]
    return list(dict.fromkeys(ids))


def entry_reports(e: Entry, aid: str | None, call: str | None,
                  undecided: list[str]) -> list[Report]:
    """The reports of the agent `aid`, launched by call `call`, that the
    timestamped entry `e` of its parent's transcripts gives, as HELP gives
    them."""
    if e.get("type") == "assistant":
        return []
    t = epoch(e["timestamp"])
    out: list[Report] = []
    for n in notifications(e):
        if (aid is None or aid not in n.ids) and call not in n.ids:
            continue
        if n.status is None:
            undecided.append(mctx("{run}: a notification of it at {time} gives "
                                  "the status `{status}`, of no known form").format(
                run=aid, time=e["timestamp"], status=n.status_text))
        elif (n.status is Status.COMPLETED and n.result is not None
                and not (n.note or "").startswith(STILL_RUNNING)):
            out.append(Report(ReportKind.NOTIFICATION, t, n.result.strip()))
    if is_prompt(e):
        out.extend(Report(ReportKind.MESSAGE, t, text)
                   for who, text in agent_messages(e) if aid is not None and who == aid)
    result = e.get("toolUseResult")
    if call and isinstance(result, dict) and any(
            b.get("tool_use_id") == call for b in blocks(e, "tool_result")):
        if launch_status(result, undecided, call) is LaunchStatus.COMPLETED:
            out.append(Report(ReportKind.RESULT, t,
                              text_of(result.get("content")).strip()))
    return out
