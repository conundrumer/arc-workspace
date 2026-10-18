"""The transcripts of an agent (`transcripts.agent_paths`), held across
states: a held lookup that misses a transcript added since gives too few
transcripts, with no failure."""

import sys
from pathlib import Path

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
