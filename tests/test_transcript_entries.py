"""The lines of a transcript that hold a word (`transcript_entries.named_lines`),
held across the growth of the transcript: a held index that misses the
lines added since gives too few entries, with no failure."""

import json
import sys
from pathlib import Path

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
