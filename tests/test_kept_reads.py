"""The reads `state_reads` keeps on disk across processes (`kept_reads`): a
record reused past a change of a file it rests on gives a stale result,
with no failure."""

import ast
import os
import sys
from pathlib import Path

import pytest

from engine import checkout
from handbook.paths import console_importable
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


KEPT_BY_HAND = ("audit_window",)
"""The modules that keep records through `kept_reads.store()` with no
`state_cache` read of their own."""

UNREACHED = ("src/checker", "src/solver", "src/souffle", "tools/console",
             "scripts/merge_change.py", "scripts/reader_commits.py")
"""The code a kept read's module does not import, so that a commit to it
alone leaves the records standing."""


def disk_read_modules() -> list[str]:
    """Each module under `scripts/` with a `state_cache` read kept on disk."""
    found: list[str] = list(KEPT_BY_HAND)
    for path in sorted(checkout.scripts().glob("*.py")):
        for node in ast.walk(ast.parse(path.read_bytes())):
            if isinstance(node, ast.keyword) and node.arg == "kept" \
                    and ast.unparse(node.value) == "Kept.DISK":
                found.append(path.stem)
                break
    return found


def test_closures_reach_no_unrelated_code(monkeypatch: pytest.MonkeyPatch) -> None:
    """The import closure of each module that keeps records holds no file
    of the solver, the lib, the checker, the console or the merge script."""
    monkeypatch.setattr(kept_reads, "_store", None)
    console_importable()
    modules = disk_read_modules()
    assert "operator_reads" in modules
    reached = {module: sorted(str(path.relative_to(checkout.ROOT))
                              for path in kept_reads.closure_files(module)
                              if path.relative_to(checkout.ROOT).as_posix().startswith(UNREACHED))
               for module in modules}
    assert reached == {module: [] for module in modules}
