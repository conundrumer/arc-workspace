"""The folds over a transcript's entries (`transcript_folds`), kept across
its growth and its rewrites, and across processes: a kept fold that
misses a change gives a stale result, with no failure."""

import json
import sys
from pathlib import Path
from typing import Any

import pytest

from handbook.paths import scripts_importable
from tests.conftest import script

scripts_importable()
script("transcript_folds")
transcript_folds = sys.modules["transcript_folds"]
transcript_snapshots = sys.modules["transcript_snapshots"]
state_reads = sys.modules["state_reads"]
kept_reads = sys.modules["kept_reads"]


def add(path: Path, *texts: str) -> None:
    with path.open("a") as fh:
        for text in texts:
            fh.write(json.dumps({"type": "user", "message": {"content": text}}) + "\n")


def texts(*paths: Path) -> list[str]:
    """The texts `fold` gives over `paths` at a new state."""
    state_reads.new_state()
    return list(transcript_folds.fold(add_text, list[str], paths, list(paths)))


def add_text(out: list[str], _path: Path, _line: int, entry: dict[str, Any]) -> None:
    out.append(entry["message"]["content"])


def test_fold_as_whole_read(tmp_path: Path) -> None:
    """A fold kept over a transcript gives what a fold of the whole
    transcript gives, after it grew, after a line not yet whole, and after
    it was written anew, cut, or grew before the last one folded."""
    first, second = tmp_path / "first.jsonl", tmp_path / "second.jsonl"
    add(first, "one", "two")
    assert texts(first) == ["one", "two"]
    add(first, "three")
    assert texts(first) == ["one", "two", "three"]
    with first.open("a") as fh:
        fh.write(json.dumps({"type": "user", "message": {"content": "four"}}))
    assert texts(first) == ["one", "two", "three", "four"]
    with first.open("a") as fh:
        fh.write("\n")
    add(first, "five")
    assert texts(first) == ["one", "two", "three", "four", "five"]
    with first.open("r+b") as fh:
        fh.write(json.dumps({"type": "user", "message": {"content": "ONE"}}).encode())
    assert texts(first) == ["ONE", "two", "three", "four", "five"]
    add(first, *(f"line {n:02} " + "x" * 1000 for n in range(10)))
    assert len(texts(first)) == 15
    with first.open("r+b") as fh:
        fh.seek(first.read_bytes().index(b"line 05"))
        fh.write(b"LINE 05")
    assert "LINE 05 " + "x" * 1000 in texts(first)
    first.write_text("")
    add(first, "six")
    assert texts(first) == ["six"]
    add(second, "seven")
    assert texts(first, second) == ["six", "seven"]
    add(first, "eight")
    assert texts(first, second) == ["six", "eight", "seven"]



def test_fold_failed_not_kept(tmp_path: Path) -> None:
    """A fold whose step fails partway keeps none of what it added: the
    next fold gives each entry once."""
    path = tmp_path / "t.jsonl"
    failing = [True]

    def step(out: list[str], p: Path, i: int, e: dict[str, Any]) -> None:
        if e["message"]["content"] == "fail" and failing[0]:
            failing[0] = False
            raise ValueError("fail")
        add_text(out, p, i, e)

    def folded() -> list[str]:
        state_reads.new_state()
        return list(transcript_folds.fold(step, list[str], path, [path]))
    add(path, "one")
    assert folded() == ["one"]
    add(path, "two", "fail")
    with pytest.raises(ValueError):
        folded()
    assert folded() == ["one", "two", "fail"]


def test_fold_naming_after_rewrite(tmp_path: Path) -> None:
    """A fold kept over the lines that hold a word gives the lines a whole
    read gives after a rewrite in place, of the same length, in the middle
    of the transcript."""
    path = tmp_path / "t.jsonl"
    add(path, *(f"line {n:02} " + "x" * 1000 for n in range(40)))

    def named() -> list[str]:
        state_reads.new_state()
        return list(transcript_folds.fold(add_text, list[str], path, [path],
                                          frozenset({"ZZTOP"})))
    assert named() == []
    with path.open("r+b") as fh:
        fh.seek(path.read_bytes().index(b"line 20"))
        fh.write(b"ZZTOP20")
    assert named() == ["ZZTOP20 " + "x" * 1000]
    add(path, "ZZTOP again")
    assert named() == ["ZZTOP20 " + "x" * 1000, "ZZTOP again"]


def later_process(store: Path) -> None:
    """Drop what this process holds, as a new process starts with none,
    and open the store at `store`."""
    kept_reads.flush()
    for h in list(state_reads._held):
        h.drop()
    state_reads._held.clear()
    transcript_snapshots._read.clear()
    transcript_folds._folds.clear()
    kept_reads.open_store(store)


def test_kept_fold_in_a_later_process(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A later process gives what a fold of the whole transcript gives,
    from the fold the store keeps: after the transcript grew, and after it
    was written anew in place before the line the kept fold stopped at."""
    monkeypatch.setattr(kept_reads, "_store", None)
    store = tmp_path / "store.sqlite"
    path = tmp_path / "t.jsonl"
    add(path, "one", "two")
    later_process(store)
    assert texts(path) == ["one", "two"]
    add(path, "three")
    later_process(store)
    assert texts(path) == ["one", "two", "three"]
    with path.open("r+b") as fh:
        fh.write(json.dumps({"type": "user", "message": {"content": "ONE"}}).encode())
    later_process(store)
    assert texts(path) == ["ONE", "two", "three"]
    later_process(store)
    assert texts(path) == ["ONE", "two", "three"]
