"""A state read searches the text of each transcript of a session once,
whatever the number of agents it looks up reports and signs of."""

import sys
from collections import Counter
from pathlib import Path

from tests.conftest import script
from tests.test_profile_runs import A1, A2, A3, told, user, write_jsonl

reports = script("agent_reports")
pending = script("agents_pending")
state_reads = sys.modules["state_reads"]
kept_reads = sys.modules["kept_reads"]
transcript_folds = sys.modules["transcript_folds"]
transcript_snapshots = sys.modules["transcript_snapshots"]


def scratch_session(tmp_path: Path) -> Path:
    """A session of a main transcript and a subagent transcript, each
    holding a notification of each of three agents."""
    session = tmp_path / "s"
    (session / "subagents").mkdir(parents=True)
    write_jsonl(session.with_suffix(".jsonl"),
                [user(n, told(a, f"call{n}")) for n, a in enumerate((A1, A2, A3), 1)])
    write_jsonl(session / "subagents" / f"agent-{A1}.jsonl",
                [user(n, told(a, f"call{n}")) for n, a in enumerate((A1, A2, A3), 4)])
    return session


def passes(session: Path, store: Path, agents: tuple[str, ...], monkeypatch) -> Counter[Path]:
    """The passes over the text of each transcript that looking up the
    reports and signs of `agents`, from a process that has read nothing,
    makes."""
    monkeypatch.setattr(kept_reads, "_store", None)
    kept_reads.open_store(store)
    for info in state_reads._reads.values():
        info.held.clear()
    transcript_folds._folds.clear()
    transcript_snapshots._read.clear()
    state_reads.new_state()
    counts: Counter[Path] = Counter()
    chunks = transcript_snapshots.Snapshot.chunks

    def counting(self):
        counts[self.path] += 1
        return chunks(self)

    with monkeypatch.context() as patch:
        patch.setattr(transcript_snapshots.Snapshot, "chunks", counting)
        for agent in agents:
            assert reports.received_entries((session,), agent, None)
        assert pending.signs_since((session,), 0.0, frozenset(agents))
    return counts


def test_looking_up_three_agents_searches_each_transcript_as_often_as_looking_up_one(
        tmp_path, monkeypatch):
    session = scratch_session(tmp_path)
    one = passes(session, tmp_path / "one.sqlite", (A1,), monkeypatch)
    three = passes(session, tmp_path / "three.sqlite", (A1, A2, A3), monkeypatch)
    assert len(one) == 2 and one
    assert three == one
