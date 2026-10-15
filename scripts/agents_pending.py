"""The agents pending to a run, and the latest sign of the turn of each
agent a run launched."""

from pathlib import Path

from agent_reports import Sign, can_report, last_sign
from run_reads import is_prompt, notified, run_sessions
from state_reads import DERIVED, state_cache
from transcript_entries import Entry, entries_unheld, epoch
from agent_launches import Launch, launched
from agent_resumes import note_latest
from session_changes import changed_since


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
    for e in session_entries(found, since):
        if not e.get("timestamp") or e.get("type") == "assistant":
            continue
        for v in notified(e):
            if v in agents:
                note_latest(out, v, epoch(e["timestamp"]))
    return out


def session_entries(found: list[tuple[Path, Launch]], since: float) -> list[Entry]:
    """The entries that name the agent of a launch of `found`, given with
    the path of the run that launched it, in each transcript changed at or
    after `since` of the sessions of that run and of the agent's own run,
    where its transcript is known."""
    agents = {a.agent for _, a in found if a.agent}
    runs = [p for launcher, a in found for p in (launcher, a.path) if p]
    sessions = dict.fromkeys(s for p in runs for s in run_sessions(p))
    return entries_since(tuple(sessions), since, frozenset(agents))


@state_cache(DERIVED)
def entries_since(sessions: tuple[Path, ...], since: float, agents: frozenset[str]) -> list[Entry]:
    """The entries that name one of `agents` in each transcript of
    `sessions` changed at or after `since`, held so that a read derived from
    them sees a new transcript only where it names one of `agents`. It holds
    only those that can give a notification or a sign of an agent
    (`may_sign`), and each is parsed for it alone, so that its read of
    every transcript of the sessions holds no other entry."""
    return [e for p in changed_since(sessions, since) for e in entries_unheld(p, agents)
            if may_sign(e)]


def may_sign(entry: Entry) -> bool:
    """Whether `entry` can give a notification of an agent (`notified`) or
    a sign of its turn (`agent_reports.entry_signs`): it can give a report
    (`agent_reports.can_report`), and where it is an attachment, it is a
    message queued while the model worked (`run_reads.is_prompt`)."""
    return can_report(entry) and (entry.get("type") != "attachment" or is_prompt(entry))


def turn_signs(path: Path, found: list[Launch]) -> dict[str, tuple[Sign, float]]:
    """The latest sign of its turn (`agent_reports.last_sign`), with its
    time, of the agent
    of each launch of `found`, launched by the run at `path`, after the
    call that launched or last resumed it, in the transcripts
    `session_entries` gives, where one stands."""
    own = [a for a in found if a.agent]
    if not own:
        return {}
    entries = session_entries([(path, a) for a in own], min(a.since for a in own))
    return {a.agent: sign for a in own if a.agent
            and (sign := last_sign(entries, a.since, {a.agent})) is not None}
