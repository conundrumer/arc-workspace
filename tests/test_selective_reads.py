"""Selective transcript records must follow source edits and disk recall."""

import json
import sys
from pathlib import Path

from tests.conftest import script
from tests.test_profile_runs import A1, A2, answer, assistant, send, told, user, write_jsonl

reports = script("agent_reports")
resumes = script("agent_resumes")
state_reads = sys.modules["state_reads"]
kept_reads = sys.modules["kept_reads"]


def recall() -> None:
    kept_reads.flush()
    for info in state_reads._reads.values():
        info.held.clear()
    sys.modules["transcript_folds"]._folds.clear()
    sys.modules["transcript_snapshots"]._read.clear()
    kept_reads.open_store(kept_reads.store().path)
    state_reads.new_state()


def test_receipt_sources_change_after_memory_and_disk_reads(tmp_path, monkeypatch):
    monkeypatch.setattr(kept_reads, "_store", None)
    kept_reads.open_store(tmp_path / "store.sqlite")
    session = tmp_path / "s"
    main = session.with_suffix(".jsonl")
    write_jsonl(main, [user(1, told(A1, "call")), user(2, told(A2, "other"))])

    def times():
        return [e.time for e in reports.received_entries((session,), A1, "call")]

    base = 1791072000.0  # 2026-10-04 UTC.
    state_reads.new_state()
    assert times() == [base + 1]
    recall()
    assert times() == [base + 1]
    agents = session / "subagents"
    agents.mkdir(parents=True)
    other = agents / f"agent-{A2}.jsonl"
    write_jsonl(other, [user(3, told(A1, "call"))])
    state_reads.new_state()
    assert times() == [base + 1, base + 3]
    replacement = tmp_path / "replacement"
    write_jsonl(replacement, [user(4, told(A1, "call"))])
    replacement.replace(other)
    recall()
    assert times() == [base + 1, base + 4]
    other.write_text("")
    state_reads.new_state()
    assert times() == [base + 1]
    with other.open("a") as stream:
        stream.write(json.dumps(user(5, told(A1, "call"))))
    state_reads.new_state()
    assert times() == [base + 1, base + 5]
    with other.open("a") as stream:
        stream.write("\n")
    state_reads.new_state()
    assert times() == [base + 1, base + 5]
    other.with_suffix(".meta.json").write_text(json.dumps({"isFork": True, "toolUseId": "absent"}))
    state_reads.new_state()
    assert times() == [base + 1]
    other.with_suffix(".meta.json").write_text(json.dumps({"isFork": False}))
    recall()
    assert times() == [base + 1, base + 5]


def test_resume_pairing_follows_appends_and_replacement_results(tmp_path, monkeypatch):
    monkeypatch.setattr(kept_reads, "_store", None)
    kept_reads.open_store(tmp_path / "store.sqlite")
    path = tmp_path / "s.jsonl"
    entries = [assistant(1, send("call", "editor")),
               user(2, answer("call"), {"resumedAgentId": A1})]
    write_jsonl(path, entries)
    state_reads.new_state()
    found = resumes.transcript_resumes(path, frozenset({A1}))
    assert len(found) == 1 and found[0].agent == A1
    recall()
    assert resumes.transcript_resumes(path, frozenset({A1})) == found
    entries.append(user(3, answer("call"), {"resumedAgentId": A2}))
    write_jsonl(path, entries)
    state_reads.new_state()
    assert resumes.transcript_resumes(path, frozenset({A1})) == ()
    entries.extend([assistant(4, send("unknown", "editor")),
                    user(5, answer("unknown"), {"pin": {"id": A1}, "delivery": "unknown"})])
    write_jsonl(path, entries)
    state_reads.new_state()
    unknown = resumes.transcript_resumes(path, frozenset({A1}))
    assert len(unknown) == 1 and unknown[0].pin == A1 and unknown[0].note
    path.write_text("")
    recall()
    assert resumes.transcript_resumes(path, frozenset({A1})) == ()


def test_truncated_selection_restarts_before_an_unfinished_line(tmp_path, monkeypatch):
    monkeypatch.setattr(kept_reads, "_store", None)
    kept_reads.open_store(tmp_path / "store.sqlite")
    path = tmp_path / "s.jsonl"
    write_jsonl(path, [user(1, told(A1, "call")), user(2, told(A1, "call"))])

    def times():
        state_reads.new_state()
        return [e.time for e in reports.received_entries((path.with_suffix(""),), A1, "call")]

    base = 1791072000.0
    assert times() == [base + 1, base + 2]
    path.write_text(json.dumps(user(3, told(A1, "call"))))
    assert times() == [base + 3]
    recall()
    path.write_text(json.dumps(user(4, told(A1, "call"))) + "\n")
    assert times() == [base + 4]
    recall()
    assert times() == [base + 4]
    partial = json.dumps(user(5, told(A1, "call")))
    path.write_text(partial[:-3])
    assert times() == []
    recall()
    with path.open("a") as stream:
        stream.write(partial[-3:] + "\n")
    assert times() == [base + 5]
    recall()
    assert times() == [base + 5]
