"""The agents pending to a run, and the latest sign of the turn of each
agent a run launched."""

import re
from dataclasses import dataclass
from pathlib import Path

from agent_reports import Sign, can_report, entry_signs, latest_sign
from run_reads import is_prompt, notified, run_sessions
from state_reads import DERIVED, Kept, state_cache
from transcript_entries import Entry, epoch, named_lines, own_range, parse, snapshot
from agent_launches import Launch, launched
from agent_resumes import note_latest
from session_changes import with_facts

from operations.roles import AGENT_ID


def pending_agents(path: Path, undecided: list[str]) -> list[str]:
    """The agent ids of the agents pending to the run at `path`, in the
    order of their launch, as `profile_runs.py --help running` gives them."""
    own = [a for a in launched(path, undecided) if a.pending and a.agent]
    if not own:
        return []
    told = notified_after([(path, a) for a in own], min(a.since for a in own))
    out: list[str] = []
    for a in own:
        last = told.get(a.agent or "")
        if a.agent and (last is None or last <= a.since):
            out.append(a.agent)
    return out


def notified_after(found: list[tuple[Path, Launch]],
                   since: float) -> dict[str, float]:
    """The time of the last notification of the agent of each launch of
    `found`, given with the path of the run that launched it, in any
    transcript changed at or after `since` of the sessions of that run and
    of the agent's own run, where its transcript is known."""
    agents = {a.agent for _, a in found if a.agent}
    out: dict[str, float] = {}
    for e in session_signs(found, since):
        for v in e.notified:
            if v in agents:
                note_latest(out, v, e.time)
    return out


@dataclass(frozen=True)
class SignEntry:
    """What an entry that can give a notification of an agent or a sign of
    its turn (`may_sign`) gives of them: its time, the ids it notifies
    (`notified`), and the signs it gives (`agent_reports.entry_signs`)."""
    time: float
    notified: tuple[str, ...]
    signs: tuple[tuple[str, Sign], ...]


def session_signs(found: list[tuple[Path, Launch]], since: float) -> list[SignEntry]:
    """The `SignEntry` of each entry that notifies the agent of a launch of
    `found`, given with the path of the run that launched it, or gives a
    sign of it, in each transcript changed at or after `since` of the
    sessions of that run and of the agent's own run, where its transcript
    is known."""
    agents = {a.agent for _, a in found if a.agent}
    runs = [p for launcher, a in found for p in (launcher, a.path) if p]
    sessions = dict.fromkeys(s for p in runs for s in run_sessions(p))
    return signs_since(tuple(sessions), since, frozenset(agents))


@state_cache(DERIVED, kept=Kept.VALUE)
def signs_since(sessions: tuple[Path, ...], since: float,
                agents: frozenset[str]) -> list[SignEntry]:
    """`session_signs`, held so that a read derived from it sees a new
    transcript only where it names one of `agents`. Each session's entries
    come from its `sign_index`, in the order of its transcripts and of
    their entries."""
    out: list[SignEntry] = []
    for session in sessions:
        index = sign_index(session)
        named = {(at.transcript, at.entry): at.sign for v in agents
                 for at in index.get(v, ()) if at.written >= since}
        out += [named[k] for k in sorted(named)]
    return out


@dataclass(frozen=True)
class SignAt:
    """A `SignEntry` of a transcript of a session, with the place of that
    transcript among the session's transcripts (`with_facts`), its own
    place among that transcript's `sign_entries`, and the time of that
    transcript's last write."""
    transcript: int
    entry: int
    written: float
    sign: SignEntry


@state_cache(DERIVED)
def sign_index(session: Path) -> dict[str, tuple[SignAt, ...]]:
    """Each `SignEntry` of the transcripts of `session`, by each id it
    notifies or gives a sign of, so that a read of the entries that name a
    few agents reads only those entries."""
    out: dict[str, list[SignAt]] = {}
    for k, (_, written, found) in enumerate(with_facts(session, sign_entries)):
        for j, e in enumerate(found):
            for v in dict.fromkeys((*e.notified, *(v for v, _ in e.signs))):
                out.setdefault(v, []).append(SignAt(k, j, written, e))
    return {v: tuple(at) for v, at in out.items()}


SIGN_WORDS = frozenset({"<task-notification>", "<agent-message from="})
"""Words the line of each entry that gives a notification
(`run_reads.NOTIFICATION`) or a message from an agent
(`run_reads.AGENT_MESSAGE`) holds."""


@state_cache(DERIVED, kept=Kept.DISK)
def sign_entries(path: Path) -> tuple[SignEntry, ...]:
    """The `SignEntry` of each entry of the transcript at `path` that may
    give a notification or a sign (`may_sign`) and gives one of an id of
    the form of an agent id. Only the lines that hold the opening of a
    notification or of a message from an agent (`SIGN_WORDS`) are read,
    each parsed for it alone, so that a read of every transcript of a
    session holds no entry."""
    snap = snapshot(path)
    out: list[SignEntry] = []
    for i in named_lines(snap, own_range(path), SIGN_WORDS):
        for e in parse(snap.line(i)):
            if not may_sign(e):
                continue
            told = tuple(v for v in notified(e) if re.fullmatch(AGENT_ID, v))
            signs = tuple((v, sign) for v, sign in entry_signs(e) if re.fullmatch(AGENT_ID, v))
            if told or signs:
                out.append(SignEntry(epoch(e["timestamp"]), told, signs))
    return tuple(out)


def may_sign(entry: Entry) -> bool:
    """Whether `entry` can give a notification of an agent (`notified`) or
    a sign of its turn (`agent_reports.entry_signs`): it can give a report
    (`agent_reports.can_report`), and where it is an attachment, it is a
    message queued while the model worked (`run_reads.is_prompt`)."""
    return can_report(entry) and (entry.get("type") != "attachment" or is_prompt(entry))


def turn_signs(path: Path, found: list[Launch]) -> dict[str, tuple[Sign, float]]:
    """The latest sign of its turn (`agent_reports.latest_sign`), with its
    time, of the agent
    of each launch of `found`, launched by the run at `path`, after the
    call that launched or last resumed it, in the transcripts
    `session_signs` gives, where one stands."""
    own = [a for a in found if a.agent]
    if not own:
        return {}
    signs = session_signs([(path, a) for a in own], min(a.since for a in own))
    return {a.agent: sign for a in own if a.agent
            and (sign := latest_sign(((e.time, e.signs) for e in signs if e.time > a.since),
                                     {a.agent})) is not None}
