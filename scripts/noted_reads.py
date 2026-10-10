"""The reads a computation makes past the transcripts and their
`.meta.json` files, noted while a record of them is open, so that a result
held past the process names each file it rests on (`run_store`).

Each read of a file that is neither a transcript nor a `.meta.json` file,
in code a profile of a run reaches, notes the file's path, whether or not
the file is there, and each read of the state of a running process notes
that the result rests on it."""

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Reads:
    paths: set[Path] = field(default_factory=set)
    live: bool = False
    """Whether the result rests on the state of a running process, which
    no file's stat gives."""


_open: list[Reads] = []


@contextmanager
def recording() -> Iterator[Reads]:
    """The reads made inside the `with` block."""
    reads = Reads()
    _open.append(reads)
    try:
        yield reads
    finally:
        _open.remove(reads)


def note_read(path: Path) -> None:
    for reads in _open:
        reads.paths.add(path)


def note_live() -> None:
    for reads in _open:
        reads.live = True
