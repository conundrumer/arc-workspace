"""Read a Claude Code transcript, each read held for one state of the
process (`state_cache`): the lines that hold a word, the lines that are
its run's own, and its `.meta.json` file. The lines are read from the
transcript's snapshot (`transcript_snapshots`), and `entry_reads` gives
their entries. No held read holds a parsed
entry: each read parses the lines it reads anew, so its entries are held
by its caller alone.

The lines that hold a word (`entries_naming`) and the lines that are a
run's own (`own_range`) are kept on disk across processes as well
(`state_reads.Kept.DISK`), so a later process reads and searches a
transcript again only once it changed."""

import json
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


def selected_lines(snap: Snapshot, lines: range, naming: frozenset[str] | None) -> list[int]:
    """`lines` of `snap`, or with `naming` those of them that hold one of
    its words."""
    if not lines or naming is None:
        return list(lines)
    return named_lines(snap, lines, naming)


TRANSCRIPT = ".jsonl"
"""The suffix of a transcript's file name."""

META = ".meta.json"
"""The suffix of the name of a transcript's `.meta.json` file."""


def meta_path(path: Path) -> Path:
    """The `.meta.json` file of the transcript at `path`."""
    return path.with_suffix(META)


def meta_transcript(meta: Path) -> Path | None:
    """The transcript whose `.meta.json` file is at `meta`, or None where
    `meta` is the `.meta.json` file of no transcript (`meta_path`)."""
    if not meta.name.endswith(META):
        return None
    path = meta.with_name(meta.name.removesuffix(META) + TRANSCRIPT)
    return path if meta_path(path) == meta else None


@state_cache(lambda path: stat_of(meta_path(path)))
def transcript_meta(path: Path) -> dict[str, Any] | None:
    return read_meta(path)


def read_meta(path: Path) -> dict[str, Any] | None:
    """The `.meta.json` of the transcript at `path`, parsed, None where it
    is no file, read with no held read."""
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
