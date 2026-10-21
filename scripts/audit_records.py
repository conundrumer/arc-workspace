"""The start and the spend of the window of the next cost audit
(`audit_window`), under the project's transcript directory.

Each `operate.py next` call is its own process, so both reads keep their
records in the store of `kept_reads`, under the transcript directory for
the start and under each transcript's path for its spend. This module
imports none of the modules that call it, so that a commit to those
leaves the records standing (`kept_reads.code_of`):

- The record of the start holds the latest launch found, and a time no
  later than the read of each directory listing the last call used
  (`state_reads.opened`). A call reads only the `.meta.json` files
  modified at or after that time: a run's `.meta.json` is written at its
  launch, so a cost audit launched after those listings were read is read
  at a later call.
- The record of a transcript (`Fold`) holds what its lines up to an offset
  gave. A call parses only the lines past that offset, and only those
  that hold a usage. One request's entries can fall on both sides of an
  offset, so the last request folded stays unsummed until an entry of
  another message id follows it, and the spend counts it at its usage so
  far. An entry of a message id after an entry of another id counts its
  request again.

Where the store holds no record of a transcript for the window's start,
or the transcript is shorter than its record's offset, its fold starts at
its first own line (`own_range`). Where the store holds no record of the
start, every `.meta.json` file is read."""

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import kept_reads
import file_reads
from state_reads import opened
from agent_turns import first_time
from token_prices import priced_requests, request_cost
from transcript_entries import epoch
from transcript_ownership import META, TRANSCRIPT, meta_transcript, own_range, read_meta
from transcripts import walked_entries
from transcript_snapshots import Refused, snapshot

from controlled_markdown import mctx
from operations.roles import Role, described

START = f"{__name__}:start"
"""The read of `kept_reads` whose record is the window's start."""

FOLD = f"{__name__}:fold"
"""The read of `kept_reads` whose record is a transcript's `Fold`."""

USAGE = b'"usage"'
"""The word of each line whose entry can give a usage."""


@dataclass(frozen=True)
class Start:
    """The record of the window's start: the launch of the latest cost
    audit found, or None where none was, and a time no later than the read
    of each directory listing of the call that found it."""
    found: float | None
    listed: float


@dataclass(frozen=True)
class Fold:
    """The record of a transcript's spend in the window from `start`, up
    to `offset`, the end of the last whole line folded: `cost`, the cost of
    the priced requests summed, with the `undecided` lines of those summed, and `last`, the
    entries of the last request folded, unsummed."""
    start: float
    offset: int
    cost: float
    lines: tuple[str, ...]
    last: tuple[dict[str, Any], ...]


_records: dict[tuple[str, str], object] = {}
"""The records this process kept or recalled. The store gives a record
once per process, and a later read of the state in the process recalls it
here."""


def recalled(read: str, key: str) -> object | None:
    """The record of `read` with the key `key`, from this process or from
    the store, or None where neither holds one."""
    if (read, key) not in _records:
        store = kept_reads.store()
        _records[read, key] = store.held(read, key) if store is not None else None
    return _records[read, key]


def keep(read: str, key: str, record: object) -> None:
    """Hold `record` as the record of `read` with the key `key`, for this
    process and for the store."""
    _records[read, key] = record
    store = kept_reads.store()
    if store is not None:
        store.keep(read, key, record)


@dataclass(frozen=True)
class Listing:
    """The transcripts and the `.meta.json` files under a directory, each
    path as a string, with its modification time."""
    transcripts: dict[str, float]
    metas: dict[str, float]


def listing(root: Path, since: float) -> Listing:
    """The transcripts under `root`, and its `.meta.json` files whose
    directory was modified at or after `since`: a `.meta.json` file written
    at or after `since` was made in such a directory. Each directory's
    entries are those `file_reads.listed` gives, as `transcripts.walked_entries`
    walks them, and each file's stat is the one `file_reads.state_stat`
    gives."""
    transcripts: dict[str, float] = {}
    metas: dict[str, float] = {}
    fresh: dict[str, bool] = {}
    for directory, e in walked_entries(str(root), file_reads.listed):
        if directory not in fresh:
            stat = file_reads.stat_of(Path(directory))
            fresh[directory] = stat is not None and stat[0] / 1e9 >= since
        if e.name.endswith(TRANSCRIPT):
            into = transcripts
        elif fresh[directory] and e.name.endswith(META):
            into = metas
        else:
            continue
        path = os.path.join(directory, e.name)
        try:
            found = file_reads.state_stat(path)
        except OSError:
            continue
        if found is not None:
            into[path] = found.mtime
    return Listing(transcripts, metas)


def start_and_spend(root: Path, started: float, undecided: list[str]) -> tuple[float, float]:
    """The start of the window of the next cost audit under `root`, or
    `started` where no cost audit under it launched, and the spend in
    dollars of the window's priced requests alone, a lower bound of its
    spend. Each request it cannot price, for an unknown price or a missing
    message id, gives an `undecided` line."""
    began = opened()
    held = recalled(START, str(root))
    held = held if isinstance(held, Start) else Start(None, float("-inf"))
    listed = listing(root, held.listed)
    start = audit_start(root, held, listed, began)
    start = started if start is None else start
    priced = sum(priced_spend(p, start, undecided)
                 for p in sorted(Path(p) for p, mtime in listed.transcripts.items() if mtime >= start))
    return start, priced


def audit_start(root: Path, held: Start, listed: Listing, began: float) -> float | None:
    """The launch of the latest cost audit under `root`, kept across calls
    as the record `Start`, `held` before this call, where `began` is no
    later than the read of each directory listing `listed` used."""
    found = held.found
    for meta in sorted(m for m, mtime in listed.metas.items() if mtime >= held.listed):
        path = meta_transcript(Path(meta))
        if path is None or str(path) not in listed.transcripts:
            continue
        launch = audit_launch(path)
        if launch is not None and (found is None or launch > found):
            found = launch
    keep(START, str(root), Start(found, began))
    return found


def audit_launch(path: Path) -> float | None:
    """The launch of the run of the transcript at `path`, where its
    `.meta.json` gives a `description` that reads as `Role.COST_AUDIT`."""
    try:
        meta = read_meta(path)
    except OSError:
        return None
    except ValueError as exc:
        raise Refused(mctx("the `.meta.json` of the transcript {path} does not parse as JSON: "
                           "{why}").format(path=path, why=exc)) from exc
    text = meta.get("description") if isinstance(meta, dict) else None
    d = described(text) if isinstance(text, str) else None
    if d is None or d.role is not Role.COST_AUDIT:
        return None
    return first_time(path)


def priced_spend(path: Path, start: float, undecided: list[str]) -> float:
    """The spend of the priced requests of the transcript at `path` in the
    window from `start`, folded on from its record where the store holds
    one for `start`."""
    held = recalled(FOLD, str(path))
    try:
        size = path.stat().st_size
    except OSError:
        return 0.0
    if isinstance(held, Fold) and held.start == start and held.offset <= size:
        fold = held
    else:
        offset = own_offset(path)
        if offset is None:
            return 0.0
        fold = Fold(start, offset, 0.0, (), ())
    if size > fold.offset:
        fold = folded(path, fold)
        keep(FOLD, str(path), fold)
    last = list(fold.lines)
    cost = request_cost(list(fold.last), last) if fold.last else 0.0
    undecided.extend(dict.fromkeys(last))
    return fold.cost + (cost or 0.0)


def own_offset(path: Path) -> int | None:
    own = own_range(path)
    return snapshot(path).starts[own.start] if own else None


def folded(path: Path, fold: Fold) -> Fold:
    """`fold` with the whole lines of the transcript at `path` past its
    offset folded in."""
    lines = list(fold.lines)
    cost = fold.cost
    last = list(fold.last)
    end = fold.offset
    with path.open("rb") as fh:
        fh.seek(fold.offset)
        for line in fh:
            if not line.endswith(b"\n"):
                break
            end += len(line)
            if USAGE not in line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            stamp = entry.get("timestamp") if isinstance(entry, dict) else None
            if not isinstance(stamp, str) or epoch(stamp) < fold.start:
                continue
            groups = priced_requests([entry], lines)
            if not groups:
                continue
            if last and last[0]["message"]["id"] != next(iter(groups)):
                cost += request_cost(last, lines) or 0.0
                last = []
            message = entry["message"]
            last.append({"message": {k: message.get(k) for k in ("id", "model", "usage")}})
    return Fold(fold.start, end, cost, tuple(dict.fromkeys(lines)), tuple(last))
