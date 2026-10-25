"""The operator records and live agents of the dashboard sessions: the
records of the last reads of the operators of each session, and the
agents that run under the sessions whose process runs."""

from dataclasses import dataclass
from pathlib import Path

from idle_sessions import harness_processes, live, named_main
from open_agents import Listed, running_agents
from shown_state import Shown, ShownAgent, ShownParty, Start, shown_read
from ticket_numbers import indexed, indexes, parsed_number
from transcripts import mains_named
from tree_reads import scratch
from operations.lineage import tickets as agent_tickets
from operations.roles import described

STALE_RECORD = 600.0
"""The age, in seconds, past which an operator's record reads as no
operator's read: a few minutes above the longest time between two full
reads of `operate.py next` (`operate_loop.FALLBACK_SECONDS`)."""


@dataclass(frozen=True)
class SessionRecord:
    """The record of a read of a session's operator, with the session's
    index, None where `ticket_numbers.indexes` gives the session none."""
    index: int | None
    shown: Shown


@dataclass(frozen=True)
class OperatorRecords:
    """The records the page is rendered from: the main session's first,
    then each other session's by index; and why the main session has none,
    where it has none; with the live agent listing where supplied."""
    records: tuple[SessionRecord, ...]
    main_missing: str | None
    running: tuple[Listed, ...] | None = None

    def expedited(self) -> frozenset[str]:
        """The tickets any record gives as expedited."""
        return frozenset(n for r in self.records for n in r.shown.expedited)

    def agents(self) -> dict[str, list[ShownAgent]]:
        """The live agents by ticket, or the recorded agents where no live
        read was supplied."""
        out: dict[str, list[ShownAgent]] = {}
        agents = (tuple(a for r in self.records for a in r.shown.agents)
                  if self.running is None else
                  tuple(ShownAgent(d.role, x.launch.since, tuple(agent_tickets(d.role, d.subject)))
                        for x in self.running if (d := described(x.run.description)) is not None))
        for a in agents:
            for n in a.tickets:
                out.setdefault(n, []).append(a)
        return out

    def any_running(self) -> bool:
        """Whether an agent runs, including one with no ticket or known role."""
        return (any(r.shown.agents for r in self.records) if self.running is None
                else bool(self.running))

    def unwaited(self) -> dict[str, float]:
        """The tickets any record gives as waiting on nothing, each with
        the earliest time a record gives it."""
        out: dict[str, float] = {}
        for r in self.records:
            for n, at in r.shown.unwaited.items():
                out[n] = min(at, out.get(n, at))
        return out

    def starts(self) -> list[Start]:
        """The starts of the records in their order, each ticket once:
        unheld where any record gives it unheld, and otherwise with the
        hold of the record of its own session, or else of the first record
        that gives it, the main session's where that one does."""
        given: dict[str, list[tuple[int | None, ShownParty | None]]] = {}
        for r in self.records:
            for s in r.shown.starts:
                given.setdefault(s.number, []).append((r.index, s.held))
        out: list[Start] = []
        for n, holds in given.items():
            if any(h is None for _, h in holds):
                out.append(Start(n, None))
                continue
            number = parsed_number(n)
            own = None if number is None else number.session
            out.append(Start(n, next((h for i, h in holds if i is not None and i == own), holds[0][1])))
        return out


def operator_records(tickets: Path, now: float, undecided: list[str] | None = None,
                     live_agents: bool = True) -> OperatorRecords:
    """The records of the last reads of the operators of each session that
    `ticket_numbers.indexes` gives (`shown_state.write_shown`): the main
    session's, or why it has none; each other session's whose time is
    within `STALE_RECORD` of `now`, or whose session `idle_sessions.live`
    gives as live; and none of another session whose record is missing or
    does not parse; with the agents `open_agents.running_agents` gives
    under the indexed sessions and the main session whose process runs
    (`idle_sessions.harness_processes`), or under all of them where that
    gives None, independently of those records and their ages. Where
    `live_agents` is false, running is None and the records supply the
    agents."""
    ids = indexes(tickets)
    main = named_main(tickets)
    records: list[SessionRecord] = []
    missing: str | None = None
    if main is None:
        missing = "no main session is set (`file_ticket.py main`)"
    else:
        shown = shown_read(scratch(main))
        if isinstance(shown, str):
            missing = shown
        else:
            records.append(SessionRecord(indexed(ids, main), shown))
    for i in sorted(ids):
        for session in ids[i]:
            if session == main:
                continue
            shown = shown_read(scratch(session))
            if not isinstance(shown, str) and (now - shown.at <= STALE_RECORD or live(session, now)):
                records.append(SessionRecord(i, shown))
    sessions = {s for names in ids.values() for s in names}
    if main is not None:
        sessions.add(main)
    processes = harness_processes() if live_agents else None
    if processes is not None:
        sessions.intersection_update(processes.values())
    notes = [] if undecided is None else undecided
    running = tuple(x for session in sorted(sessions) for path in mains_named(session)
                    for x in running_agents(path, notes)) if live_agents else None
    return OperatorRecords(tuple(records), missing, running)
