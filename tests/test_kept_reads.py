"""The reads `state_reads` keeps on disk across processes (`kept_reads`): a
record reused past a change of a file it rests on gives a stale result,
with no failure."""

import os
import sys
from pathlib import Path

import pytest

from tests.conftest import script

script("profile_runs")
state_reads = sys.modules["state_reads"]
kept_reads = sys.modules["kept_reads"]
file_reads = sys.modules["file_reads"]

runs: list[str] = []


@state_reads.state_cache(state_reads.DERIVED, kept=state_reads.Kept.DISK)
def words(path: Path) -> int:
    runs.append("words")
    return len(file_reads.file_text(path).split())


@state_reads.state_cache(state_reads.DERIVED, kept=state_reads.Kept.DISK)
def many(path: Path) -> bool:
    runs.append("many")
    return words(path) > 2


def new_process() -> None:
    """Write the records, and drop what this process holds, as a new
    process starts with none."""
    kept_reads.flush()
    state_reads._held.clear()
    for info in state_reads._reads.values():
        info.held.clear()
    kept_reads.open_store(kept_reads.store().path)
    state_reads.new_state()


def write(path: Path, text: str, tick: int) -> None:
    path.write_text(text)
    os.utime(path, ns=(tick * 10**9, tick * 10**9))


def test_stale(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A kept result stands in a later process while the files it rests on
    stand, and is computed again once one changes, also where it rests on
    them through another kept read whose result changed."""
    monkeypatch.setattr(kept_reads, "_store", None)
    kept_reads.open_store(tmp_path / "store.sqlite")
    f = tmp_path / "f.txt"
    write(f, "a b c", 1)
    new_process()
    assert many(f) is True

    runs.clear()
    new_process()
    assert many(f) is True
    assert runs == []

    runs.clear()
    write(f, "a b", 2)
    new_process()
    assert many(f) is False
    assert words(f) == 2
    assert runs == ["words", "many"]
