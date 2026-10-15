"""The sweep of the `validation` tickets under `tickets/deferred/`, whose
rules `file_ticket.py sweep --help-all` states."""

import json
import os
import re
import signal
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from agent_turns import first_time
from controlled_markdown import mctx
from engine import checkout
from operations.constants import FOREGROUND_MS
from ticket_files import ticket_name
from ticket_form import section
from ticket_log import VALIDATED, Moved, line_time, log_lines, log_moves
from ticket_watch import Thresholds, deferred, route
from ticketing.text import VALIDATION
from ticketing.times import utc_stamp
from ticketing.vocabulary import Kind, Status, Verdict
from transcripts import Refused, chain, find, own_range, snapshot

UNEXERCISED_DAYS = 7
"""The days since its last move into `deferred` from which a `validation`
ticket that no run exercised moves into `open`."""

COMMAND_SECONDS = 60
"""The seconds the sweep lets the command of a check run."""

SWEEP = "sweep"
"""The `<agent>` of the lines the sweep writes."""

EXERCISED_FIELD = "Exercised:"

COMMAND_FIELD = "Command:"

EXERCISED_LINE = re.compile(rf"^- {EXERCISED_FIELD} (?P<pattern>.+)$", re.MULTILINE)

COMMAND_LINE = re.compile(rf"^- {COMMAND_FIELD} `(?P<command>.+)`$", re.MULTILINE)

EXERCISED = mctx("{exercised}: {runs}")

UNEXERCISED = mctx("{unexercised}: no run matched since {time}")

EXITED = mctx("{failed}: {command} exited {code}")

TIMED_OUT = mctx("{failed}: {command} timed out")

UNREAD = mctx("{failed}: {reason}")

SWEEP_MARGIN = 30
"""The seconds of a sweep's Bash call kept for its work other than the
commands of checks."""


@dataclass(frozen=True)
class Check:
    """The check a `validation` ticket's `Validation` section gives: the patterns of
    its `Exercised:` lines, and the command of its `Command:` line, None
    where it gives none."""
    patterns: tuple[re.Pattern[str], ...]
    command: str | None


def check_of(path: Path, text: str) -> Check:
    """The check of the ticket at `path` with text `text`, or a refusal
    by the rules `file_ticket.py sweep --help-all` states."""
    body = section(text, VALIDATION)
    commands = [m["command"] for m in COMMAND_LINE.finditer(body)]
    if len(commands) > 1:
        raise Refused(mctx("{path} gives more than one `{field}` line").format(
            path=path, field=COMMAND_FIELD))
    try:
        patterns = tuple(re.compile(m["pattern"]) for m in EXERCISED_LINE.finditer(body))
    except re.error as e:
        raise Refused(mctx("{path} gives an `{field}` pattern that does not compile: "
                           "{error}").format(path=path, field=EXERCISED_FIELD, error=e))
    for pattern in patterns:
        once = json.dumps(pattern.pattern)[1:-1]
        if pattern.search(once) or pattern.search(json.dumps(once)[1:-1]):
            raise Refused(mctx("{path} gives an `{field}` pattern that matches its own "
                               "text in its JSON escape: {pattern}").format(
                path=path, field=EXERCISED_FIELD, pattern=pattern.pattern))
    return Check(patterns, commands[0] if commands else None)


@dataclass(frozen=True)
class GivenRun:
    """A run given to the sweep: the time of its first timestamped entry,
    and the lines of its transcripts that are its own (`own_lines`)."""
    start: float
    lines: list[str]


def given_run(run: str) -> GivenRun:
    """The run `run`, read once for the sweep. Refuses a run whose
    transcripts hold no timestamped entry."""
    path = find(run)
    start = first_time(path)
    if start is None:
        raise Refused(mctx("{run} has no timestamped entry").format(run=run))
    return GivenRun(start, [line for p in chain(path) for line in own_lines(p)])


def own_lines(path: Path) -> list[str]:
    """The lines of the transcript at `path` that are its run's own."""
    snap = snapshot(path)
    return [snap.line(i).decode() for i in own_range(path)]


def exercisers(check: Check, runs: dict[str, list[str]]) -> list[str] | None:
    """The runs of `runs`, by agent id with the lines of their transcripts,
    that exercise `check`, each of them where it gives no pattern, or None
    where `runs` is empty or no run matches a pattern it gives."""
    if not runs:
        return None
    if not check.patterns:
        return list(runs)
    by = [run for run, lines in runs.items()
          if any(p.search(line) for p in check.patterns for line in lines)]
    return by or None


def deferred_since(path: Path, text: str) -> float:
    """The time of the last line of the log of the ticket at `path` with
    text `text` that moves it into `deferred`."""
    lines = log_lines(text)
    moves = [m for i, m in enumerate(lines) if m["status"] == Status.DEFERRED
             and (i == 0 or lines[i - 1]["status"] != Status.DEFERRED)]
    if not moves:
        raise Refused(mctx("{path} has no log line that moves it into `{deferred}`").format(
            path=path, deferred=Status.DEFERRED))
    return line_time(moves[-1])


def run_command(command: str) -> tuple[Status, str]:
    """Runs the command of a check from the main tree, and gives the status
    its ticket moves into, with the note of that line. The command runs in
    a session of its own, so that its whole process group ends at the
    timeout."""
    with subprocess.Popen(command, shell=True, cwd=checkout.main_worktree(checkout.ROOT),
                          env=checkout.tree_env(), stdin=subprocess.DEVNULL,
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                          start_new_session=True) as process:
        try:
            code = process.wait(COMMAND_SECONDS)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()
            return Status.OPEN, TIMED_OUT.format(failed=Verdict.FAILED, command=command)
    if code == 0:
        return Status.CLOSED, f"{VALIDATED} {command}"
    return Status.OPEN, EXITED.format(failed=Verdict.FAILED, command=command, code=code)


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
    by = exercisers(check, {run: given.lines for run, given in runs.items()
                            if given.start >= since})
    if by is not None and check.command is not None:
        if time.monotonic() + COMMAND_SECONDS > deadline:
            raise OutOfTime
        return run_command(check.command)
    if by is not None:
        return Status.OPEN, EXERCISED.format(exercised=Verdict.EXERCISED,
                                             runs=" ".join(by))
    if now - since < UNEXERCISED_DAYS * 86400:
        return None
    return Status.OPEN, UNEXERCISED.format(unexercised=Verdict.UNEXERCISED, time=utc_stamp(since))


def sweep(tickets: Path, runs: list[str], undecided: list[str]) -> list[Path]:
    """Moves each `validation` ticket under `tickets/deferred/` as `file_ticket.py
    sweep --help-all` states, then routes the deferred groups as `route`
    does, and returns the path each moved ticket went to."""
    deadline = time.monotonic() + FOREGROUND_MS / 1000 - SWEEP_MARGIN
    given = {run: given_run(run) for run in runs}
    now = time.time()
    moved: list[Path] = []
    for path, text in deferred(tickets, Kind.VALIDATION):
        try:
            move = judged(path, text, given, now, deadline)
        except OutOfTime:
            undecided.append(mctx("{path}: the command of its `{field}` line did not run, with no time "
                                  "left in the sweep's Bash call, and the next sweep runs it").format(path=path, field=COMMAND_FIELD))
            continue
        except Moved:
            continue
        except Refused as e:
            move = Status.OPEN, UNREAD.format(failed=Verdict.FAILED, reason=e)
        if move is None:
            continue
        try:
            moved += log_moves(tickets, ticket_name(path).number, move[0], SWEEP,
                               Status.DEFERRED, None, move[1]).moved
        except Moved:
            continue
    return moved + list(route(tickets, SWEEP, Thresholds(tickets, undecided), None).values())
