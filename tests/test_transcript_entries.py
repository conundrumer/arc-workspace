"""The reads of a transcript (`transcript_entries`), held across its growth
and its rewrites in place: a held read that misses a change gives a stale
result, with no failure."""

import json
import os
import sys
from pathlib import Path
from typing import Any

import pytest

from handbook.paths import scripts_importable
from tests.conftest import script

scripts_importable()
script("transcript_entries")
script("entry_reads")
transcript_entries = sys.modules["transcript_entries"]
transcript_snapshots = sys.modules["transcript_snapshots"]
entry_reads = sys.modules["entry_reads"]
state_reads = sys.modules["state_reads"]

AGENT = "a0123456789abcdef"


def add(path: Path, *texts: str) -> None:
    with path.open("a") as fh:
        for text in texts:
            fh.write(json.dumps({"type": "user", "message": {"content": text}}) + "\n")


def named(path: Path, words: set[str]) -> list[int]:
    state_reads.new_state()
    snap = transcript_snapshots.snapshot(path)
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


def line_of(text: str) -> str:
    return json.dumps({"type": "user", "message": {"content": text}})


def padded(texts: list[str], size: int) -> str:
    """The lines of `texts`, the last one padded with `x` so that they take
    `size` characters, newlines between them included."""
    bare = "\n".join(line_of(text) for text in texts)
    return "\n".join(line_of(text) for text in [*texts[:-1], texts[-1] + "x" * (size - len(bare))])


def whole_read(path: Path, naming: set[str] | None) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_bytes().splitlines()
            if naming is None or any(w.encode() in line for w in naming)]


def rewritten(path: Path, first: int, count: int, texts: list[str]) -> None:
    """Write over lines `first` to `first + count` of the transcript at
    `path`, in place, the lines of `texts` at the same length."""
    lines = path.read_text().split("\n")
    old = "\n".join(lines[first:first + count])
    lines[first:first + count] = [padded(texts, len(old))]
    text = "\n".join(lines)
    assert len(text) == len(path.read_text())
    with path.open("r+") as fh:
        fh.write(text)


@pytest.mark.parametrize(("count", "texts"), [(1, ["ZZTOP20"]), (1, ["ZZTOP20a", "ZZTOP20b"]),
                                              (2, ["ZZTOP2021"])])
def test_reads_after_rewrite(tmp_path: Path, count: int, texts: list[str]) -> None:
    """Each read gives what a whole read gives after a rewrite in place, of
    the same length, before the end of the transcript, also one that
    changes the count of its lines."""
    path = tmp_path / "t.jsonl"
    add(path, *(f"line {n:02} " + "x" * 1000 for n in range(40)))

    def reads() -> list[object]:
        out: list[object] = []
        for naming in (None, {"ZZTOP"}):
            state_reads.new_state()
            out.append(list(entry_reads.read_entries(path, naming)))
            state_reads.new_state()
            out.append([e for _, e in entry_reads.numbered_entries(path, naming)])
            state_reads.new_state()
            out.append(transcript_entries.fold(
                add_entry, list[dict[str, Any]], (path, naming is None), [path],
                None if naming is None else frozenset(naming)))
        state_reads.new_state()
        out.append(len(entry_reads.entries_naming(path, frozenset({"ZZTOP"}))))
        return out

    def expected() -> list[object]:
        named = whole_read(path, {"ZZTOP"})
        return [*[whole_read(path, None)] * 3, *[named] * 3, len(named)]
    assert reads() == expected()
    rewritten(path, 20, count, texts)
    assert reads() == expected()


def add_entry(out: list[dict[str, Any]], _path: Path, _line: int, entry: dict[str, Any]) -> None:
    out.append(entry)



def open_store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    kept_reads = sys.modules["kept_reads"]
    monkeypatch.setattr(kept_reads, "_store", None)
    kept_reads.open_store(tmp_path / "store.sqlite")
    return kept_reads


def drop_held() -> None:
    state_reads._held.clear()
    for info in state_reads._reads.values():
        info.held.clear()


def contents(path: Path, naming: set[str]) -> list[Any]:
    return [e["message"]["content"] for e in entry_reads.read_entries(path, naming)]


def test_kept_lines_in_a_later_process(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A later process whose kept record of the lines that hold a word
    stands reads those lines from the transcript as it stands, and one
    after the transcript grew reads the lines added too."""
    kept_reads = open_store(tmp_path, monkeypatch)
    path = tmp_path / "t.jsonl"
    add(path, "x ZZTOP", "y", "z ZZTOP")

    def later_process() -> list[Any]:
        kept_reads.flush()
        drop_held()
        transcript_snapshots._read.clear()
        kept_reads.open_store(kept_reads.store().path)
        state_reads.new_state()
        return contents(path, {"ZZTOP"})

    assert later_process() == ["x ZZTOP", "z ZZTOP"]
    assert later_process() == ["x ZZTOP", "z ZZTOP"]
    add(path, "w ZZTOP")
    assert later_process() == ["x ZZTOP", "z ZZTOP", "w ZZTOP"]


def test_kept_lines_of_a_transcript_rewritten_in_place(tmp_path: Path,
                                                       monkeypatch: pytest.MonkeyPatch) -> None:
    """A process that still holds the snapshot of a transcript from before
    it was written anew in place, at the same size, reads the lines of a
    kept record another process made of the new text from that text."""
    kept_reads = open_store(tmp_path, monkeypatch)
    path = tmp_path / "t.jsonl"
    add(path, "a ZZTOP", "b", "c ZZTOP")
    state_reads.new_state()
    assert contents(path, {"b"}) == ["b"]
    held = transcript_snapshots._read[path]
    later = path.stat().st_mtime_ns + 10**9
    rewritten(path, 0, 3, ["x", "z", "y ZZTOP"])
    os.utime(path, ns=(later, later))
    drop_held()
    transcript_snapshots._read.clear()
    state_reads.new_state()
    assert [c[:7] for c in contents(path, {"ZZTOP"})] == ["y ZZTOP"]
    kept_reads.flush()
    drop_held()
    transcript_snapshots._read[path] = held
    state_reads.new_state()
    assert [c[:7] for c in contents(path, {"ZZTOP"})] == ["y ZZTOP"]
