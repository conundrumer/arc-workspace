"""The transcripts of an agent (`transcripts.agent_paths`), held across
states, and the transcript `transcripts.find` gives an id within one
state: a held lookup that misses a transcript added since gives too few
transcripts, with no failure, and a refusal of `find` stops its caller on
an agent that has a transcript."""

import sys
from pathlib import Path

import pytest

from handbook.paths import scripts_importable
from tests.conftest import script

scripts_importable()
transcripts = script("transcripts")
state_reads = sys.modules["state_reads"]

A, B, C = (f"a{n:016x}" for n in (1, 2, 3))


def transcript(projects: Path, session: str, agent: str) -> Path:
    path = projects / "p" / session / "subagents" / f"agent-{agent}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("")
    return path


def test_new_transcripts_found(tmp_path: Path) -> None:
    """A transcript added after the lookups were held reaches the lookup of
    its agent at the next state, a new agent's and a known agent's alike,
    and the lookup of another agent gives what it gave."""
    dirs = (tmp_path,)
    a1 = transcript(tmp_path, "s1", A)
    b1 = transcript(tmp_path, "s1", B)
    state_reads.new_state()
    assert transcripts.agent_paths(dirs, A) == [a1]
    assert transcripts.agent_paths(dirs, C) == []
    held_b = transcripts.agent_paths(dirs, B)
    a2 = transcript(tmp_path, "s2", A)
    c2 = transcript(tmp_path, "s2", C)
    state_reads.new_state()
    assert transcripts.agent_paths(dirs, A) == [a1, a2]
    assert transcripts.agent_paths(dirs, C) == [c2]
    assert transcripts.agent_paths(dirs, B) == held_b == [b1]


def test_find_reads_again_at_each_miss(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """After a miss of `find` on one id, a transcript born for another id
    is found by `find` in the same state."""
    monkeypatch.setattr(transcripts, "project_dirs", lambda: [tmp_path])
    transcript(tmp_path, "s1", A)
    state_reads.new_state()
    with pytest.raises(transcripts.Refused):
        transcripts.find(B)
    c = transcript(tmp_path, "s1", C)
    assert transcripts.find(C) == c
