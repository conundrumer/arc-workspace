"""The file of a session's step journal (`operations.journal`), under the
session's scratchpad: one JSON record per line, appended under a lock,
that `next` gave a step (`given`) or that step's outcome (`closed`), and the run of each Bash
step the command runs itself (`run`), whose output and exit status go to
files under `RUNS`.

The first read of a session's journal with every operator's calls read
starts it, seeded with each SendMessage call the operators made with no
error before then, as a message done, so that no message sent before the
journal is sent again. Each read gives the outcome of each step in flight
that the operators' calls, or a run's files, now give, and writes it."""

import fcntl
import json
import os
import signal
import subprocess
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass, replace
from enum import StrEnum
from pathlib import Path
from typing import Any

from operator_reads import merge_outcome

from controlled_markdown import mctx
from operations.constants import FOREGROUND_MS
from operations.journal import Close, Entry, Journal, Outcome, closing
from operations.roles import description
from operations.state import Call, Tool
from operations.steps import Bash, Journaled, Launch, Send, digest, key

JOURNAL = "step-journal.jsonl"
RUNS = "step-journal"
SEEDED = "seeded"
"""The origin of a message seeded from a call made before the journal."""

class Event(StrEnum):
    """What a record of the file gives."""
    GIVEN = "given"
    CLOSED = "closed"

NO_STATUS = mctx("the command ended with no exit status")
TIMED_OUT = mctx("the command ran past {seconds} seconds and was ended")


def journal_path(scratch: Path) -> Path:
    return scratch / JOURNAL


def runs_dir(scratch: Path) -> Path:
    return scratch / RUNS


@dataclass(frozen=True)
class Run:
    """The files of the run of a Bash step: the process group it leads,
    its output, and its exit status, written once it ends."""
    pid: int
    output: Path
    status: Path


@dataclass(frozen=True)
class Record:
    """An entry as the file gives it: its id, the entry, and the run of a
    Bash step."""
    ident: str
    entry: Entry
    run: Run | None


def append(scratch: Path, records: Sequence[dict[str, Any]]) -> None:
    """Append `records` to the journal of `scratch`, under its lock."""
    if not records:
        return
    path = journal_path(scratch)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            f.write("".join(json.dumps(r) + "\n" for r in records))
            f.flush()
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def entry_record(ident: str, e: Entry, run: Run | None) -> dict[str, Any]:
    """The record of `e` as given, with the run of a Bash step."""
    fields = {k: v for k, v in asdict(e).items() if k != "close"}
    return {"event": Event.GIVEN, "id": ident, **fields,
            "run": None if run is None else {"pid": run.pid, "output": str(run.output),
                                             "status": str(run.status)}}


def given_record(ident: str, step: Journaled, operator: str, time: float,
                 run: Run | None = None) -> dict[str, Any]:
    """The record that `next` gave `step` to `operator` at `time`."""
    match step:
        case Launch(role, subject):
            tool, to, text = Tool.AGENT, None, description(role, subject)
        case Send(to, message):
            tool, text = Tool.SEND_MESSAGE, message
        case Bash(command):
            tool, to, text = Tool.BASH, None, command
    return entry_record(ident, Entry(
        key=key(step), digest=digest(step), origin=step.origin, operator=operator, given=time,
        tool=tool, to=to, text=text, retires=step.retires if isinstance(step, Bash) else None,
        change=step.change, close=None), run)


def closed_record(ident: str, close: Close) -> dict[str, Any]:
    return {"event": Event.CLOSED, "id": ident, "outcome": close.outcome, "time": close.time,
            "why": close.why}


def give(scratch: Path, steps: Sequence[Journaled], operator: str, time: float) -> None:
    """Record that `next` gave each of `steps`, Agent calls and messages, to
    `operator` at `time`."""
    append(scratch, [given_record(uuid.uuid4().hex, s, operator, time) for s in steps])


def give_failed(scratch: Path, step: Launch, operator: str, time: float, why: str) -> None:
    """Record that `next` gave `step` to `operator` at `time` and that it
    failed then, with `why`: an end of turn that holds it for the agent
    listing, as `operate.py --help journal` gives it."""
    ident = uuid.uuid4().hex
    append(scratch, [given_record(ident, step, operator, time),
                     closed_record(ident, Close(Outcome.FAILED, time, why))])


def records(scratch: Path) -> list[Record]:
    """The entries of the journal of `scratch`, each with the first outcome
    recorded for it, in the order they were given; none where it is not
    started."""
    path = journal_path(scratch)
    if not path.exists():
        return []
    given: dict[str, dict[str, Any]] = {}
    closes: dict[str, Close] = {}
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        if r["event"] == Event.GIVEN:
            given[r["id"]] = r
        elif r["event"] == Event.CLOSED and r["id"] not in closes:
            closes[r["id"]] = Close(Outcome(r["outcome"]), r["time"], r["why"])
    out: list[Record] = []
    for ident, r in given.items():
        run = r["run"]
        out.append(Record(ident, Entry(
            key=r["key"], digest=r["digest"], origin=r["origin"], operator=r["operator"],
            given=r["given"], tool=Tool(r["tool"]), to=r["to"], text=r["text"],
            retires=r["retires"], change=r["change"], close=closes.get(ident)),
            None if run is None else Run(run["pid"], Path(run["output"]), Path(run["status"]))))
    return out


def seed(scratch: Path, calls: Sequence[Call]) -> None:
    """Start the journal of `scratch` with each SendMessage call of
    `calls` that the harness gave no error, as a message done."""
    seeded: list[dict[str, Any]] = []
    for c in sorted(calls, key=lambda c: c.time):
        if c.tool != Tool.SEND_MESSAGE or c.error:
            continue
        ident = uuid.uuid4().hex
        seeded += [entry_record(ident, Entry(
            key=None, digest="", origin=SEEDED, operator=c.operator, given=c.time,
            tool=Tool.SEND_MESSAGE, to=str(c.input["to"]), text=c.message, retires=None,
            change=None, close=None), None),
                   closed_record(ident, Close(Outcome.DONE, c.time, ""))]
    path = journal_path(scratch)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch()
    append(scratch, seeded)


def alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def run_close(r: Record, now: float) -> Close | None:
    """The outcome of the Bash run of `r`, read from its files at `now`, or
    None while it runs; a run past `FOREGROUND_MS` is ended."""
    if r.run is None:
        return None
    if r.run.status.exists():
        text = r.run.status.read_text().strip()
        if not text.lstrip("-").isdigit():
            return None
        if int(text) == 0:
            return Close(Outcome.DONE, r.run.status.stat().st_mtime, "")
        lines = output(r.run).strip().splitlines()
        return Close(Outcome.FAILED, r.run.status.stat().st_mtime,
                     lines[-1] if lines else mctx("exit status {status}").format(status=text))
    if not alive(r.run.pid):
        return Close(Outcome.FAILED, now, NO_STATUS)
    if now - r.entry.given > FOREGROUND_MS / 1000:
        try:
            os.killpg(r.run.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        return Close(Outcome.FAILED, now, TIMED_OUT.format(seconds=FOREGROUND_MS // 1000))
    return None


def output(run: Run) -> str:
    return run.output.read_text(errors="replace") if run.output.exists() else ""


def read(scratch: Path, calls: Sequence[Call], live: Callable[[Entry], bool], now: float,
         start: bool) -> tuple[Journal, list[Record]]:
    """The journal of `scratch`, with the outcome of each step in flight
    that `calls`, the operators' calls, or its run's files now give,
    written, where `live` gives whether the work of the operator of an
    entry may still make its call, and
    its records. Where `start` holds and the journal is not started, it is
    seeded from `calls` first (`seed`)."""
    if start and not journal_path(scratch).exists():
        seed(scratch, calls)
    found = records(scratch)
    closes: list[dict[str, Any]] = []
    out: list[Record] = []
    for r in found:
        if r.entry.close is None:
            close = (run_close(r, now) if r.entry.tool is Tool.BASH
                     else closing(r.entry, calls, live(r.entry), now))
            if close is not None:
                closes.append(closed_record(r.ident, close))
                r = Record(r.ident, replace(r.entry, close=close), r.run)
        out.append(r)
    append(scratch, closes)
    return Journal(tuple(r.entry for r in out)), out


def run_calls(found: Sequence[Record], subjects: Mapping[str, float],
              undecided: list[str]) -> list[Call]:
    """Each Bash step of `found` as a call of its operator, with its output
    once it ended, and the outcome of a merge call (`merge_outcome`)."""
    out: list[Call] = []
    denied: set[str] = set()
    for r in found:
        if r.run is None or r.entry.tool is not Tool.BASH:
            continue
        e = r.entry
        text = None if e.close is None else output(r.run)
        error = e.close is not None and e.close.outcome is Outcome.FAILED
        merge = merge_outcome(e.operator, e.text, e.given, text, error, subjects, denied,
                              undecided)
        out.append(Call(e.operator, e.given, Tool.BASH, {"command": e.text}, text, error, merge))
    return out


def start_run(scratch: Path, step: Bash, operator: str, cwd: Path, time: float) -> str:
    """Start the command of `step` in a process group of its own under
    `cwd`, which outlives the command `next`, record that `next` gave it to
    `operator` at `time`, and give its id."""
    ident = uuid.uuid4().hex
    base = runs_dir(scratch) / ident
    base.parent.mkdir(parents=True, exist_ok=True)
    out, status = base.with_suffix(".out"), base.with_suffix(".status")
    script = f'( {step.command}\n) > "$1" 2>&1; echo $? > "$2.tmp" && mv "$2.tmp" "$2"'
    proc = subprocess.Popen(["/bin/bash", "-c", script, "bash", str(out), str(status)],
                            cwd=cwd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL, start_new_session=True)
    append(scratch, [given_record(ident, step, operator, time, Run(proc.pid, out, status))])
    return ident


def running(scratch: Path, now: float) -> list[Record]:
    """The Bash runs of the journal of `scratch` that have not ended, as
    their files give them at `now`."""
    return [r for r in records(scratch)
            if r.run is not None and r.entry.close is None and run_close(r, now) is None]
