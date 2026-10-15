"""The state the monitor's steps read, from the session's running agents
and their transcripts: the late resumes of the operators, and each watched
agent's readings."""

import time
from pathlib import Path

from agent_reports import parent_transcripts
from agent_turns import first_time, last_time
from budgets import budgets_in_force, past_budget
from context_bound_hook import OPERATORS
from open_agents import Listed
from operator_reads import resumed_at
from run_prints import self_of
from run_reads import bash_spans, repeated_runs, run_entries
from transcripts import epoch

from controlled_markdown import mctx
from operations import monitor
from operations.constants import COORDINATOR
from operations.monitor import Watched
from operations.state import LateResume


def late_resumes(runs: list[tuple[str, Path]],
                 undecided: list[str]) -> dict[str, tuple[LateResume, ...]]:
    """`TranscriptsRead.late_resumes` of the operators `runs` gives, in the order of
    their first entry."""
    out: dict[str, tuple[LateResume, ...]] = {}
    for (aid, path), (later, later_path) in zip(runs, runs[1:]):
        first = first_time(later_path)
        if first is None:
            continue
        found = tuple(LateResume(t, later, first) for t in resumed_at(aid, path, undecided)
                      if t > first)
        if found:
            out[aid] = found
    return out


UNWATCHED = OPERATORS
"""The agent types the monitor's steps do not watch."""


def stalled_at(listed: Listed, listing: list[Listed], undecided: list[str]) -> float | None:
    """The end of the turn of `listed` where it stalled, as
    `monitor.ALERTS` gives a stall, or None. A run whose turn end
    `agent_turns.turn_end` cannot find has no stall, and an `undecided`
    line names it."""
    aid = listed.launch.agent
    if (not listed.ended or listed.found != [] or listed.running
            or any(x.parent == aid for x in listing)):
        return None
    end = listed.end
    if end is None:
        undecided.append(mctx("{run}: its turn reads as ended, yet no timestamped entry "
                              "of its transcripts ends it, so it counts as not "
                              "stalled").format(run=aid))
        return None
    if any(t > end for t in listed.run.ended):
        return None
    if any(e.get("type") == "user" and e.get("timestamp") and epoch(e["timestamp"]) > end
           for e in run_entries(listed.path)):
        return None
    answered = [t for p in parent_transcripts(listed.path)
                if (t := last_time(p, lambda e: e.get("type") == "assistant")) is not None]
    return end if any(t > end for t in answered) else None


def repeated(listed: Listed) -> tuple[float, ...]:
    """The `repeated` readings of `listed` (`run_reads.repeated_runs`)."""
    entries = run_entries(listed.path)
    calls = [(s.call, s.command, s.start) for s in bash_spans(listed.run.spans, entries)]
    return tuple(repeated_runs(calls, entries, monitor.REPEATS))


def watched(listing: list[Listed], launched: set[str],
            undecided: list[str], opened: float) -> list[Watched]:
    """The agents of `listing`, whose work is open, that an operator
    launched, by `launched`, their agent ids, or that the coordinator, the
    session's main transcript, launched, as read in the state that opened
    at `opened`."""
    out: list[Watched] = []
    now = time.time()
    for listed in listing:
        r = listed.run
        aid = listed.launch.agent
        if (aid is None or r.agent_type in UNWATCHED
                or (aid not in launched and listed.parent != COORDINATOR)):
            continue
        budget = next(reversed(budgets_in_force(r, undecided)), None)
        self_time = self_of(listed, now)
        out.append(Watched(
            agent_id=aid,
            over_budget=past_budget(self_time, budget),
            stalled=stalled_at(listed, listing, undecided), repeated=repeated(listed)))
    return out
