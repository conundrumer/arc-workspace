"""Read the entries of a Claude Code transcript, from the lines of its
snapshot (`transcript_snapshots`) that are its run's own
(`transcript_entries.own_range`), each line parsed only when it is
reached, so a reader holds only the entries it keeps."""

from collections.abc import Iterable, Iterator, Sequence
from pathlib import Path

from state_reads import DERIVED, Kept, state_cache
from transcript_entries import own_range, selected_lines
from transcript_snapshots import Entry, last_snapshot, parse, snapshot


def read_entries(path: Path, naming: Iterable[str] | None = None) -> Iterator[Entry]:
    """The entries of the transcript at `path` as it stands at the state this
    process is in, or with `naming` only those whose line holds one of its
    words, which spares parsing the rest, each line parsed only when it is
    reached."""
    return (e for _, e in numbered_entries(path, naming))


def numbered_entries(path: Path, naming: Iterable[str] | None = None
                     ) -> Iterator[tuple[int, Entry]]:
    """Each entry `read_entries` gives, with the index of its line, each
    line parsed only when it is reached."""
    lines = entries_naming(path, None if naming is None else frozenset(naming))
    snap = last_snapshot(path)
    for i, line in zip(lines, snap.lines(lines)):
        for e in parse(line):
            yield i, e


def line_entries(path: Path, i: int) -> list[Entry]:
    """The entries of line `i` of the snapshot of the transcript at `path`
    that `numbered_entries` or `fold` read at this state."""
    return last_snapshot(path).entry(i)


@state_cache(DERIVED, kept=Kept.DISK)
def entries_naming(path: Path, naming: frozenset[str] | None) -> Sequence[int]:
    """The lines whose entries `read_entries` gives, held so that a read
    derived from it sees a change of the transcript only where those lines
    change: a transcript is added to at its end, so a line keeps its bytes
    while its index stands here. With no `naming` they are its own lines
    as a `range`, which its kept record holds in a few bytes."""
    own = own_range(path)
    return own if naming is None else selected_lines(snapshot(path), own, naming)


def entries_forward(path: Path) -> Iterator[Entry]:
    """The entries of the transcript at `path` as it stands at the state this
    process is in, in their order, each line parsed only when it is reached."""
    snap = snapshot(path)
    for i in own_range(path):
        yield from snap.entry(i)


def entries_back(path: Path) -> Iterator[Entry]:
    """The entries of the transcript at `path` as it stands at the state this
    process is in, last first, each line parsed only when it is reached."""
    snap = snapshot(path)
    for i in reversed(own_range(path)):
        yield from snap.entry(i)
