"""The lines of a transcript that hold a word (`transcript_entries.named_lines`),
held across the growth of the transcript: a held index that misses the
lines added since gives too few entries, with no failure."""

import json
import sys
from pathlib import Path
from typing import Any

import pytest

from handbook.paths import scripts_importable
from tests.conftest import script

scripts_importable()
script("transcript_entries")
transcript_entries = sys.modules["transcript_entries"]
state_reads = sys.modules["state_reads"]

AGENT = "a0123456789abcdef"


def add(path: Path, *texts: str) -> None:
    with path.open("a") as fh:
        for text in texts:
            fh.write(json.dumps({"type": "user", "message": {"content": text}}) + "\n")


def named(path: Path, words: set[str]) -> list[int]:
    state_reads.new_state()
    snap = transcript_entries.snapshot(path)
    return transcript_entries.named_lines(snap, range(snap.count), frozenset(words))


def test_lines_named_after_growth(tmp_path: Path) -> None:
    """An index made before the transcript grew, and one first made after,
    each give the lines added."""
    asked_before = tmp_path / "before.jsonl"
    asked_after = tmp_path / "after.jsonl"
    for path in (asked_before, asked_after):
        add(path, f"launched {AGENT}", "SendMessage once", "nothing")
    assert named(asked_before, {AGENT, "SendMessage"}) == [0, 1]
    for path in (asked_before, asked_after):
        add(path, f"from {AGENT}", "SendMessage again")
    assert named(asked_before, {AGENT}) == [0, 3]
    assert named(asked_before, {AGENT, "SendMessage"}) == [0, 1, 3, 4]
    assert named(asked_after, {AGENT, "SendMessage"}) == [0, 1, 3, 4]


def texts(*paths: Path) -> list[str]:
    """The texts `fold` gives over `paths` at a new state."""
    state_reads.new_state()
    return list(transcript_entries.fold(add_text, list[str], paths, list(paths)))


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
        return list(transcript_entries.fold(step, list[str], path, [path]))
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
        return list(transcript_entries.fold(add_text, list[str], path, [path],
                                            frozenset({"ZZTOP"})))
    assert named() == []
    with path.open("r+b") as fh:
        fh.seek(path.read_bytes().index(b"line 20"))
        fh.write(b"ZZTOP20")
    assert named() == ["ZZTOP20 " + "x" * 1000]
    add(path, "ZZTOP again")
    assert named() == ["ZZTOP20 " + "x" * 1000, "ZZTOP again"]
