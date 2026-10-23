"""The transcripts of a session changed since a time, the facts of those
transcripts by the agents they name, and the entries of a run that have a
time."""

from collections.abc import Callable, Iterable, Iterator, Sequence, Sized
from dataclasses import dataclass
from pathlib import Path

from run_reads import (run_entries,
                       session_transcripts)
from file_reads import mtime
from state_reads import DERIVED, state_cache
from transcript_snapshots import Entry


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


@state_cache(DERIVED)
def with_facts[F: Sized](session: Path,
                         facts: Callable[[Path], F]) -> tuple[tuple[Path, float, F], ...]:
    """Each transcript of `session` for which `facts` gives any, with the
    time of its last write and those facts."""
    return tuple((p, t, found) for p, t in written(session) if len(found := facts(p)))


@dataclass(frozen=True, slots=True)
class Fact[F]:
    """A fact of a transcript of a session (`with_facts`): the place of that
    transcript among the session's transcripts, the fact's own place among
    that transcript's facts, the transcript, the time of its last write,
    and the fact."""
    transcript: int
    entry: int
    path: Path
    written: float
    fact: F


@state_cache(DERIVED)
def facts_by_agent[F](session: Path, facts: Callable[[Path], Sequence[F]],
                      agents_of: Callable[[F], Iterable[str]]) -> dict[str, tuple[Fact[F], ...]]:
    """Each fact `facts` gives of a transcript of `session`, by each agent
    id `agents_of` gives of it, so that a read of the facts that name a few
    agents reads only those facts."""
    out: dict[str, list[Fact[F]]] = {}
    for k, (p, written_at, found) in enumerate(with_facts(session, facts)):
        for j, fact in enumerate(found):
            for v in dict.fromkeys(agents_of(fact)):
                out.setdefault(v, []).append(Fact(k, j, p, written_at, fact))
    return {v: tuple(at) for v, at in out.items()}


def agents_facts[F](sessions: Iterable[Path], since: float, facts: Callable[[Path], Sequence[F]],
                    agents_of: Callable[[F], Iterable[str]],
                    agents: Iterable[str]) -> list[Fact[F]]:
    """Each fact of `facts_by_agent` of `sessions` that names an agent of
    `agents`, of a transcript that changed at or after `since`, each once,
    in the order of `sessions`, of their transcripts and of the facts of
    each."""
    out: list[Fact[F]] = []
    for session in sessions:
        index = facts_by_agent(session, facts, agents_of)
        named = {(at.transcript, at.entry): at for v in agents
                 for at in index.get(v, ()) if at.written >= since}
        out += [named[k] for k in sorted(named)]
    return out


def timed_entries(path: Path) -> Iterator[Entry]:
    return (e for e in run_entries(path) if e.get("timestamp"))
