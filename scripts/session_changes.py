"""The transcripts of a session changed since a time, and the entries of a
run that have a time."""

from collections.abc import Iterable
from pathlib import Path

from run_reads import (run_entries,
                       session_transcripts)
from state_reads import DERIVED, mtime, state_cache
from transcript_entries import Entry


def changed_since(sessions: Iterable[Path], since: float) -> list[Path]:
    """The transcripts of `sessions` that changed at or after `since`."""
    return [p for session in sessions for p in changed_in(session, since)]


@state_cache(None)
def written(session: Path) -> tuple[tuple[Path, float], ...]:
    """Each transcript of `session`, with the time of its last write."""
    return tuple((p, mtime(p)) for p in session_transcripts(session))


@state_cache(DERIVED)
def changed_in(session: Path, since: float) -> list[Path]:
    """The transcripts of `session` that changed at or after `since`, from
    `written`, so a read derived from it sees a change only where the
    transcripts it gives change."""
    return [p for p, t in written(session) if t >= since]


def timed_entries(path: Path) -> list[Entry]:
    return [e for e in run_entries(path) if e.get("timestamp")]
