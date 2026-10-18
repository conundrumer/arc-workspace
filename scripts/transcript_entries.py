"""Read a Claude Code transcript, each read held for one state of the
process (`state_cache`): the lines that hold a word, the lines that are
its run's own, its `.meta.json` file, and the folds over the entries of
transcripts that go on from where the last fold stopped (`fold`). The
lines are read from the transcript's snapshot (`transcript_snapshots`),
and `entry_reads` gives their entries. No held read holds a parsed
entry: each read parses the lines it reads anew, so its entries are held
by its caller alone.

The lines that hold a word (`entries_naming`) and the lines that are a
run's own (`own_range`) are kept on disk across processes as well
(`state_reads.Kept.DISK`), so a later process reads and searches a
transcript again only once it changed."""

import json
from collections.abc import Callable, Hashable, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from file_reads import stat_of
from state_reads import DERIVED, Kept, state_cache
from transcript_snapshots import Entry, Refused, Snapshot, parse, snapshot

from controlled_markdown import mctx


def epoch(iso: str) -> float:
    return datetime.fromisoformat(iso).timestamp()


def named_lines(snap: Snapshot, own: range, naming: frozenset[str]) -> list[int]:
    """The lines of `snap` within `own` that hold a word of `naming`, in
    their order."""
    return sorted(i for i in snap.holding(naming) if i in own)


@dataclass(frozen=True)
class Folded:
    """Where a fold stood in a transcript when it was kept: the `generation`
    of the snapshot it read, the first of the run's own lines then
    (`own_range`), and the line it stopped before, each line before it a
    whole line."""
    path: Path
    generation: object
    own: int
    done: int


type Step[S] = Callable[[S, Path, int, Entry], None]
"""A fold's step: it adds to the state an entry, with its transcript and
the index of its line."""

_folds: dict[Hashable, tuple[Any, tuple[Folded, ...]]] = {}
"""The state of each fold kept by its step and run, with where it stood in
each transcript it read."""


def fold[S](step: Step[S], start: Callable[[], S], run: Hashable, paths: Sequence[Path],
            naming: frozenset[str] | None = None) -> S:
    """The state `step` gives from `start()` over each entry of the run's
    own lines of each transcript of `paths`, in their order, or with
    `naming` each entry `read_entries` gives with it, as the transcripts
    stand at the state this process is in. A later call with the same
    `step` and `run` parses only the lines added since, where `goes_on`
    holds, and otherwise starts the fold again, as for a transcript
    written anew, cut, or changed before its end. A fold whose step
    fails is not kept. A state over a line that is not whole is given and
    not kept. The caller changes none of the state it gets, and holds
    none of it past its read, as a later fold adds to it."""
    key = step, run
    held = _folds.pop(key, None)
    now = [(p, snapshot(p), own_range(p)) for p in paths]
    if held is not None and goes_on(held[1], now):
        state, marks = held[0], held[1]
    else:
        state, marks = start(), ()
    kept: list[Folded] = []
    for j, (p, snap, own) in enumerate(now):
        done = marks[j].done if j < len(marks) else own.start
        whole = max(own.start, min(own.stop, snap.settled()))
        fold_lines(state, step, p, snap, range(done, whole), naming)
        kept.append(Folded(p, snap.generation, own.start, whole))
    _folds[key] = state, tuple(kept)
    if not any(parse(line) for _, snap, own in now
               for line in snap.lines(selected_lines(snap, range(max(own.start, snap.settled()),
                                                         own.stop), naming))):
        return state
    state = start()
    for p, snap, own in now:
        fold_lines(state, step, p, snap, own, naming)
    return state


def goes_on(marks: tuple[Folded, ...], now: list[tuple[Path, Snapshot, range]]) -> bool:
    """Whether a fold that stood at `marks` goes on over the transcripts
    `now` gives, each with its snapshot and own lines: each transcript of
    `marks` is the one at its place in `now`, of the same snapshot
    `generation` and first own line, and only the last of them has lines
    past where the fold stopped."""
    if len(marks) > len(now):
        return False
    for j, m in enumerate(marks):
        p, snap, own = now[j]
        if (m.path != p or m.generation is not snap.generation or m.own != own.start
                or m.done > own.stop):
            return False
        if j < len(marks) - 1 and m.done != own.stop:
            return False
    return True


def fold_lines[S](state: S, step: Step[S], path: Path, snap: Snapshot, lines: range,
                  naming: frozenset[str] | None) -> None:
    """Fold into `state` the entries of `lines` of `snap`, the snapshot of
    the transcript at `path`, or with `naming` of those lines that hold one
    of its words."""
    found = selected_lines(snap, lines, naming)
    for i, line in zip(found, snap.lines(found)):
        for e in parse(line):
            step(state, path, i, e)


def selected_lines(snap: Snapshot, lines: range, naming: frozenset[str] | None) -> list[int]:
    """`lines` of `snap`, or with `naming` those of them that hold one of
    its words."""
    if not lines or naming is None:
        return list(lines)
    return named_lines(snap, lines, naming)


def meta_path(path: Path) -> Path:
    """The `.meta.json` file of the transcript at `path`."""
    return path.with_suffix(".meta.json")


@state_cache(lambda path: stat_of(meta_path(path)))
def transcript_meta(path: Path) -> dict[str, Any] | None:
    m = meta_path(path)
    return json.loads(m.read_bytes()) if m.is_file() else None


def blocks(entry: Entry, kind: str) -> list[dict[str, Any]]:
    content = (entry.get("message") or {}).get("content")
    if not isinstance(content, list):
        return []
    return [b for b in content if isinstance(b, dict) and b.get("type") == kind]


@state_cache(DERIVED, kept=Kept.DISK)
def own_range(path: Path) -> range:
    """The indices of the lines of the transcript at `path` that are its
    run's own. A fork's transcript opens with a copy of its parent's
    entries, through the Agent call that launched the fork, which its
    `.meta.json` gives as `toolUseId`, and its own entries run from the
    first line whose entry holds that call's result to its last line.
    For a fork's transcript where no line holds that result, it is empty.
    For each other transcript, it is every line."""
    meta = transcript_meta(path) or {}
    call = meta.get("toolUseId")
    snap = snapshot(path)
    if meta.get("isFork") is not True or not isinstance(call, str):
        return range(snap.count)
    start = next((i for i in sorted(snap.holding(frozenset({call})))
                  if any(b.get("tool_use_id") == call
                         for e in snap.entry(i) for b in blocks(e, "tool_result"))), None)
    return range(0) if start is None else range(start, snap.count)


def forked_from(path: Path) -> str | None:
    """The id of the session that the session whose transcript is at
    `path` was forked from, which the transcript's first line names, or
    None where that line names none."""
    with path.open() as fh:
        first = fh.readline()
    entry = next(iter(parse(first)), None)
    if not isinstance(entry, dict):
        raise Refused(mctx("the first line of {path} is no transcript entry").format(path=path))
    fork = entry.get("forkedFrom")
    return fork["sessionId"] if fork else None
