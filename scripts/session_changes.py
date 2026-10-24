"""The transcripts of a session changed since a time, the facts of those
transcripts by the agents they name, and the entries of a run that have a
time."""

from collections.abc import Callable, Iterable, Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path

from run_reads import (run_entries,
                       session_transcripts)
from file_reads import mtime, stat_read
from state_reads import DERIVED, Kept, state_cache
from transcript_snapshots import Entry, snapshot
from transcript_ownership import meta_path, own_range
from transcript_folds import Step, fold
from transcripts import chain


def changed_since(sessions: Iterable[Path], since: float) -> list[Path]:
    """The transcripts of `sessions` that changed at or after `since`."""
    return [p for session in sessions for p in changed_in(session, since)]


@state_cache(DERIVED)
def written(session: Path) -> tuple[tuple[Path, float], ...]:
    """Each transcript of `session`, with the time of its last write."""
    return tuple((p, mtime(p)) for p in session_transcripts(session))


@state_cache(DERIVED)
def changed_in(session: Path, since: float) -> list[Path]:
    """The transcripts of `session` that changed at or after `since`, from
    `written`, so a read derived from it sees a change only where the
    transcripts it gives change."""
    return [p for p, t in written(session) if t >= since]


@dataclass(frozen=True, slots=True)
class Fact[F]:
    """A selected fact, with its transcript and entry positions."""
    transcript: int
    entry: int
    path: Path
    fact: F


def agents_facts[F](sessions: Iterable[Path], since: float,
                    facts: Callable[[Path, frozenset[str]], Sequence[F]],
                    agents: frozenset[str]) -> list[Fact[F]]:
    """Selected facts in session, transcript and entry order, from
    transcripts written at or after `since`. Empty ids read no transcript."""
    if not agents:
        return []
    return [Fact(k, j, p, fact) for session in sessions
            for k, (p, t) in enumerate(written(session)) if since <= 0.0 or t >= since
            for j, fact in enumerate(facts(p, agents))]


@dataclass
class MatchingFacts[F]:
    """Requested ids and their facts in transcript entry order."""
    agents: frozenset[str]
    facts: list[F]


def matching_facts[F](path: Path, agents: frozenset[str],
                       add: Step[MatchingFacts[F]]) -> tuple[F, ...]:
    """Incremental facts of requested ids only, with one fact per entry.
    The step retains matching facts and determines the fold's code identity."""
    if not agents:
        return ()
    snap = snapshot(path)
    own = own_range(path)
    if not any(i in own for i in snap.matching(agents)):
        return ()
    state = fold(add, lambda: MatchingFacts(agents, []), path, [path], agents, selective=True)
    return tuple(state.facts)


def transcript_stamp(path: Path) -> tuple[object, ...]:
    """Transcript bytes and the metadata that determines ownership."""
    return stat_read(path), stat_read(meta_path(path))


def session_source_stamp(session: Path) -> tuple[object, ...]:
    return tuple((p, transcript_stamp(p)) for p, _ in written(session))


@state_cache(session_source_stamp, kept=Kept.VALUE)
def session_sources(session: Path) -> tuple[object, ...]:
    """Receipt content, ownership metadata and transcript membership.
    Metadata edits invalidate this value independently of transcript writes."""
    return session_source_stamp(session)


def run_stamp(path: Path) -> tuple[object, ...]:
    """Run membership, transcript bytes and ownership metadata. Discovery
    reads also track candidate transcripts and directory membership."""
    return tuple((p, transcript_stamp(p)) for p in chain(path))


def timed_entries(path: Path) -> Iterator[Entry]:
    return (e for e in run_entries(path) if e.get("timestamp"))
