"""The records `run_store` holds across processes: a record held past a
change of a file it rests on gives a budget from a stale profile, with no
failure."""

import json
import sys
from pathlib import Path

import pytest

from engine import checkout
from tests.conftest import script

script("profile_runs")
run_store = sys.modules["run_store"]
transcripts = sys.modules["transcripts"]
FILED = sys.modules["operations.filing"].FILED

AGENT = "a0000000000000001"


def entry(kind: str, s: int, content: str) -> dict:
    return {"type": kind, "timestamp": f"2026-10-04T00:00:{s:02d}.000Z",
            "message": {"content": content}}


def test_stale(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A held profile stands while its transcripts and the files it read
    stand, and is computed again once one of them changes."""
    agents = tmp_path / "proj" / "s" / "subagents"
    agents.mkdir(parents=True)
    brief = tmp_path / "brief.md"
    brief.write_text("first brief")
    path = agents / f"agent-{AGENT}.jsonl"
    (agents / f"agent-{AGENT}.meta.json").write_text(json.dumps(
        {"agentType": "code-editor", "parentAgentId": "a0000000000000002"}))
    lines = [entry("user", 0, FILED.format(path=brief)), entry("assistant", 10, "a")]
    path.write_text("".join(json.dumps(e) + "\n" for e in lines))
    store_dir = tmp_path / "cache"
    monkeypatch.setattr(transcripts, "project_dirs", lambda: [tmp_path])
    monkeypatch.setattr(checkout, "caches", lambda: store_dir)
    computed: list[Path] = []
    profile = run_store.profile
    monkeypatch.setattr(run_store, "profile",
                        lambda p, undecided: computed.append(p) or profile(p, undecided))

    def read() -> tuple[float, str]:
        transcripts.new_state()
        store = run_store.RunStore()
        last, kind = store.last_and_type(AGENT)
        assert kind == "code-editor"
        run = store.profile(last, [])
        store.flush()
        return run.wall, run.messages[0].text

    try:
        assert read() == (10.0, "first brief")
        assert read() == (10.0, "first brief")
        assert len(computed) == 1
        with path.open("a") as f:
            f.write(json.dumps(entry("assistant", 30, "b")) + "\n")
        assert read() == (30.0, "first brief")
        brief.write_text("second brief")
        assert read() == (30.0, "second brief")
        assert len(computed) == 3
    finally:
        transcripts.new_state()
