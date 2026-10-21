"""The sweep of the `validation` tickets under `tickets/deferred/`, whose
rules `file_ticket.py sweep --help-all` states."""

import os
import signal
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from controlled_markdown import mctx
from engine import checkout
from operations.constants import FOREGROUND_MS
from ticket_files import ticket_name
from ticket_log import VALIDATED, Moved, line_time, log_lines, log_moves
from ticket_watch import Thresholds, deferred, route
from ticketing.times import utc_stamp
from run_reads import agent_type
from ticketing.vocabulary import Kind, Status, Verdict, last_move_into
from validation_checks import AGENT_FIELD, COMMAND_FIELD, EXERCISED_FIELD, Check, check_of
from transcripts import chain, find
from transcript_entries import epoch
from transcript_ownership import own_range
from transcript_snapshots import Refused, snapshot
from tree_reads import main_tree

UNEXERCISED_DAYS = 7
"""The days since its last move into `deferred` from which a `validation`
ticket that no run exercised moves into `reopened`."""

COMMAND_SECONDS = 60
"""The seconds the sweep lets the command of a check run."""

SWEEP = "sweep"
"""The `<agent>` of the lines the sweep writes."""

EXERCISED = mctx("{exercised}: {runs}")

UNEXERCISED = mctx("{unexercised}: no run matched since {time}")

EXITED = mctx("{failed}: {command} exited {code}")

TIMED_OUT = mctx("{failed}: {command} timed out")

UNREAD = mctx("{failed}: {reason}")

SWEEP_MARGIN = 30
"""The seconds of a sweep's Bash call kept for its work other than the
commands of checks."""


type TimedLine = tuple[float, str]
"""A line of a run's own whose entry gives a `timestamp`, with that time."""


@dataclass(frozen=True)
class GivenRun:
    """A run given to the sweep, with its timestamped own lines from a time
    on, in their order."""
    lines: list[TimedLine]
    agent_type: str | None

    def since(self, since: float) -> "GivenRun":
        """The run with its lines at or after `since` alone."""
        return GivenRun([(t, line) for t, line in self.lines if t >= since], self.agent_type)


def given_run(run: str, since: float) -> GivenRun:
    """The run `run`, read once for the sweep, with its own lines
    timestamped at or after `since`, read from its last line back to the
    first timestamped line before `since`."""
    path = find(run)
    back: list[TimedLine] = []
    for p in reversed(chain(path)):
        snap = snapshot(p)
        for i in reversed(own_range(p)):
            times = [e["timestamp"] for e in snap.entry(i) if e.get("timestamp")]
            if not times:
                continue
            t = epoch(times[0])
            if t < since:
                return GivenRun(back[::-1], agent_type(path))
            back.append((t, snap.line(i).decode()))
    return GivenRun(back[::-1], agent_type(path))


def exercisers(check: Check, runs: dict[str, GivenRun]) -> list[str] | None:
    """The runs of `runs`, by agent id, that exercise `check`, or None
    where none does. Which runs exercise a check, `file_ticket.py sweep
    --help-all` states."""
    by = [run for run, given in runs.items()
          if (not check.agent_types or given.agent_type in check.agent_types)
          and (not check.patterns
               or any(p.search(line) for p in check.patterns for _, line in given.lines))]
    return by or None


def deferred_since(path: Path, text: str) -> float:
    """The time of the last line of the log of the ticket at `path` with
    text `text` that moves it into `deferred`."""
    lines = log_lines(text)
    i = last_move_into([Status(m["status"]) for m in lines], Status.DEFERRED)
    if i is None:
        raise Refused(mctx("{path} has no log line that moves it into `{deferred}`").format(
            path=path, deferred=Status.DEFERRED))
    return line_time(lines[i])


def read_since(path: Path, text: str) -> float | None:
    """`deferred_since` of the ticket, or None where it refuses."""
    try:
        return deferred_since(path, text)
    except Refused:
        return None


def run_command(command: str) -> tuple[Status, str]:
    """Runs the command of a check from the main tree, and gives the status
    its ticket moves into, with the note of that line. The command runs in
    a session of its own, so that its whole process group ends at the
    timeout."""
    with subprocess.Popen(command, shell=True, cwd=main_tree(),
                          env=checkout.tree_env(), stdin=subprocess.DEVNULL,
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                          start_new_session=True) as process:
        try:
            code = process.wait(COMMAND_SECONDS)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()
            return Status.REOPENED, TIMED_OUT.format(failed=Verdict.FAILED, command=command)
    if code == 0:
        return Status.CLOSED, f"{VALIDATED} {command}"
    return Status.REOPENED, EXITED.format(failed=Verdict.FAILED, command=command, code=code)


class OutOfTime(Exception):
    """The sweep has no time left to run the command of a check within its
    Bash call."""


def judged(path: Path, text: str, runs: dict[str, GivenRun], now: float,
           deadline: float) -> tuple[Status, str] | None:
    """The status the deferred ticket at `path` with text `text` moves
    into at a sweep at `now` of the runs `runs`, with the note of that
    line, or None where it stays. Raises `OutOfTime` where its command
    would run past `deadline`, a `time.monotonic` time."""
    check = check_of(path, text)
    since = deferred_since(path, text)
    by = exercisers(check, {run: after for run, given in runs.items()
                            if (after := given.since(since)).lines})
    if by is not None and check.command is not None:
        if time.monotonic() + COMMAND_SECONDS > deadline:
            raise OutOfTime
        return run_command(check.command)
    if by is not None:
        return Status.REOPENED, EXERCISED.format(exercised=Verdict.EXERCISED,
                                                 runs=" ".join(by))
    if now - since < UNEXERCISED_DAYS * 86400:
        return None
    return Status.REOPENED, UNEXERCISED.format(unexercised=Verdict.UNEXERCISED, time=utc_stamp(since))


def sweep(tickets: Path, runs: list[str], undecided: list[str]) -> list[Path]:
    """Moves each `validation` ticket under `tickets/deferred/` as `file_ticket.py
    sweep --help-all` states, then routes the deferred groups as `route`
    does, and returns the path each moved ticket went to."""
    deadline = time.monotonic() + FOREGROUND_MS / 1000 - SWEEP_MARGIN
    validations = deferred(tickets, Kind.VALIDATION)
    now = time.time()
    oldest = min((t for path, text in validations if (t := read_since(path, text)) is not None),
                 default=now)
    given = {run: given_run(run, oldest) for run in runs}
    moved: list[Path] = []
    for path, text in validations:
        try:
            move = judged(path, text, given, now, deadline)
        except OutOfTime:
            undecided.append(mctx("{path}: the command of its `{field}` line did not run, with no time "
                                  "left in the sweep's Bash call, and the next sweep runs it").format(path=path, field=COMMAND_FIELD))
            continue
        except Moved:
            continue
        except Refused as e:
            move = Status.REOPENED, UNREAD.format(failed=Verdict.FAILED, reason=e)
        if move is None:
            continue
        try:
            moved += log_moves(tickets, ticket_name(path).number, move[0], SWEEP,
                               Status.DEFERRED, None, move[1]).moved
        except Moved:
            continue
    return moved + list(route(tickets, SWEEP, Thresholds(tickets, undecided), None).values())
