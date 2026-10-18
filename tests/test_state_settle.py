"""The reads `state_reads` holds across states: a held result that stands
past a change of a file it rests on gives a stale result, with no
failure."""

import os
import sys
from pathlib import Path

from tests.conftest import script

script("profile_runs")
state_reads = sys.modules["state_reads"]
file_reads = sys.modules["file_reads"]


@state_reads.state_cache(state_reads.DERIVED)
def words(path: Path) -> int:
    return len(file_reads.file_text(path).split())


@state_reads.state_cache(state_reads.DERIVED)
def many(path: Path) -> bool:
    return words(path) > 2


@state_reads.state_cache(state_reads.DERIVED)
def both(p: Path, q: Path) -> tuple[bool, int]:
    return many(p), words(q)


@state_reads.state_cache(state_reads.DERIVED)
def above(p: Path, q: Path) -> tuple[bool, int]:
    return both(p, q)


def write(path: Path, text: str, tick: int) -> None:
    path.write_text(text)
    os.utime(path, ns=(tick * 10**9, tick * 10**9))


def test_a_change_reaches_each_read_above_it(tmp_path: Path) -> None:
    """A read gives at each state the result its files give then: where a
    file changes and a read between them gives the result it gave, and
    where a read rests on that file both through such a read and through a
    read whose result changes."""
    p, q = tmp_path / "p.txt", tmp_path / "q.txt"
    write(p, "a b c", 1)
    write(q, "a", 1)
    state_reads.new_state()
    assert above(p, q) == (True, 1)

    write(p, "a b c d", 2)
    state_reads.new_state()
    assert above(p, q) == (True, 1)

    write(p, "a", 3)
    write(q, "a b", 3)
    state_reads.new_state()
    assert above(p, q) == (False, 2)

    write(q, "a b c", 4)
    state_reads.new_state()
    assert above(p, q) == (False, 3)
    assert words(q) == 3


def test_a_change_a_partial_state_leaves_out_reaches_the_next_full_state(tmp_path: Path) -> None:
    """A state that reads again only the stats of some paths sees a change
    of those files and is partial, and the next state that reads each stat
    again sees a change of the others and is not partial."""
    p, q = tmp_path / "p.txt", tmp_path / "q.txt"
    write(p, "a b c", 1)
    write(q, "a", 1)
    state_reads.new_state()
    assert above(p, q) == (True, 1)

    write(p, "a", 2)
    write(q, "a b", 2)
    file_reads.stats_stand_but({str(q)})
    state_reads.new_state()
    assert above(p, q) == (True, 2)
    assert state_reads.partial()

    file_reads.stats_stand_but(None)
    state_reads.new_state()
    assert above(p, q) == (False, 2)
    assert not state_reads.partial()
