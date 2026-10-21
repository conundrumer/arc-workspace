"""Transcript metadata and the boundary after a fork's copied parent entries."""

import json
from pathlib import Path
from typing import Any

from controlled_markdown import mctx
from file_reads import stat_of
from state_reads import DERIVED, Kept, state_cache
from transcript_snapshots import Entry, Refused, parse, snapshot


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
    is no file or has invalid JSON or a non-object value, read with no held read."""
    m = meta_path(path)
    try:
        value = json.loads(m.read_bytes()) if m.is_file() else None
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    return value if isinstance(value, dict) else None


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
                  if any(own_result(e, call) for e in snap.entry(i))), None)
    return range(0) if start is None else range(start, snap.count)


def forked_from(path: Path) -> str | None:
    """The id of the session that the session whose transcript is at
    `path` was forked from, which the transcript's first line names, or
    None where that line names none."""
    with path.open() as fh:
        first = fh.readline()
    entry = next(iter(parse(first)), None)
    if not isinstance(entry, dict):
        raise Refused(mctx("the first line of {path} is not a transcript entry").format(path=path))
    fork = entry.get("forkedFrom")
    return fork["sessionId"] if fork else None


def own_result(entry: Entry, call: str) -> bool:
    """Whether an entry starts a fork's own records."""
    return any(b.get("tool_use_id") == call for b in blocks(entry, "tool_result"))
