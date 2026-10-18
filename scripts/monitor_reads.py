"""The state the monitor's steps read, from the session's running agents
and their transcripts: the late resumes of the operators, and each watched
agent's readings."""

import time
from pathlib import Path

from agent_reports import parent_transcripts
from agent_turns import first_time, last_time
from context_bound_hook import OPERATORS
from open_agents import Listed, quiet_since
from operator_reads import resumed_at
from run_reads import (bash_ids, bash_spans, repeated_runs, result_texts, run_entries,
                       same_since)
from transcript_entries import epoch
from transcript_snapshots import Entry

from controlled_markdown import mctx
from operations import monitor
from operations.constants import COORDINATOR, stuck_reached
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
    """The end of the turn of `listed` where it stalled, or None.

    It stalled where its turn ended since its parent's latest message to
    it, and all of these hold:

    - No `user` entry in its transcript is timestamped after that turn
      ended.
    - No agent it launched and no command it backgrounded still runs or
      ended after that turn ended.
    - Its parent's transcripts hold an `assistant` entry timestamped after
      that turn ended.

    That turn ended at the last timestamped entry of its transcripts that
    ends a turn, as `scripts/profile_runs.py --help runs` gives one. A run
    whose turn end `agent_turns.turn_end` cannot find has no stall, and an
    `undecided` line names it."""
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
                if (t := last_time(p, is_assistant)) is not None]
    return end if any(t > end for t in answered) else None


def is_assistant(entry: Entry) -> bool:
    return entry.get("type") == "assistant"


def bash_calls(listed: Listed) -> tuple[list[tuple[str, str, float]], dict[str, str]]:
    """The Bash calls of `listed`, as `run_reads.repeated_runs` takes them,
    and the text of each of their results by its call, read in one pass
    over its entries."""
    bash: set[str] = set()
    texts: dict[str, str] = {}
    for e in run_entries(listed.path):
        bash |= bash_ids((e,))
        texts.update(result_texts(e, bash))
    return [(s.call, s.command, s.start) for s in bash_spans(listed.run.spans, bash)], texts


def repeated(listed: Listed) -> tuple[float, ...]:
    """The `repeated` readings of `listed` (`run_reads.repeated_runs`)."""
    calls, texts = bash_calls(listed)
    return tuple(repeated_runs(calls, texts, monitor.REPEATS))


def stuck_at(aid: str, listed: Listed, listing: list[Listed], now: float) -> float | None:
    """The time from which `listed`, the run of `aid`, is stuck, or None
    where it is not. An agent that keeps making the same Bash call with
    the same result shows progress to `quiet_since`, so a run of such
    calls `STUCK_SECONDS` long counts as stuck too, from that run's
    start."""
    quiet = quiet_since(aid, listed.path, listing, now)
    if quiet is not None:
        return quiet
    calls, texts = bash_calls(listed)
    since = same_since(calls, texts)
    return since if since is not None and stuck_reached(since, now) else None


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
        out.append(Watched(
            agent_id=aid,
            stalled=stalled_at(listed, listing, undecided), repeated=repeated(listed),
            stuck=stuck_at(aid, listed, listing, now)))
    return out
