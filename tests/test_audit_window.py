"""The spend of a cost audit's window (`audit_window`), kept on disk across
processes: a record folded on past a change of its transcript gives a wrong
spend, with no failure."""

import json
import sys
from pathlib import Path

import pytest

from handbook.paths import scripts_importable
from tests.conftest import script

scripts_importable()
script("audit_window")
audit_window = sys.modules["audit_window"]
audit_records = sys.modules["audit_records"]
kept_reads = sys.modules["kept_reads"]
state_reads = sys.modules["state_reads"]
token_prices = sys.modules["token_prices"]
epoch = sys.modules["transcript_entries"].epoch

START = "2026-10-16T10:00:00Z"


def entry(message: str, at: str, output: int) -> dict[str, object]:
    return {"type": "assistant", "timestamp": at,
            "message": {"id": message, "model": "claude-opus-5-5",
                        "usage": {"input_tokens": 1000, "output_tokens": output}}}


def new_process() -> None:
    """Write the records, and drop what this process holds, as a new
    process starts with none."""
    kept_reads.flush()
    audit_records._records.clear()
    state_reads._held.clear()
    for info in state_reads._reads.values():
        info.held.clear()
    kept_reads.open_store(kept_reads.store().path)
    state_reads.new_state()


def spend(root: Path) -> float:
    new_process()
    return audit_window.window(root, epoch(START), []).spend


def cost(entries: list[dict[str, object]]) -> float:
    inside = [e for e in entries if epoch(str(e["timestamp"])) >= epoch(START)]
    return token_prices.run_cost(inside, [])


def test_fold(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The spend of a transcript folded on from its record, after it grew
    with a request's entries on both sides of the record's offset, and
    after it was written anew shorter, is the cost of its entries in the
    window as they stand."""
    monkeypatch.setattr(kept_reads, "_store", None)
    kept_reads.open_store(tmp_path / "store.sqlite")
    root = tmp_path / "projects"
    path = root / "session" / "t.jsonl"
    path.parent.mkdir(parents=True)
    entries = [entry("m0", "2026-10-16T09:00:00Z", 10), entry("m1", "2026-10-16T10:01:00Z", 10),
               entry("m2", "2026-10-16T10:02:00Z", 10)]
    path.write_text("".join(json.dumps(e) + "\n" for e in entries))
    assert spend(root) == pytest.approx(cost(entries))

    more = [entry("m2", "2026-10-16T10:02:01Z", 500), entry("m3", "2026-10-16T10:03:00Z", 20)]
    with path.open("a") as fh:
        fh.write("".join(json.dumps(e) + "\n" for e in more))
    assert spend(root) == pytest.approx(cost(entries + more))
    assert spend(root) == pytest.approx(cost(entries + more))

    path.write_text(json.dumps(entries[1]) + "\n")
    assert spend(root) == pytest.approx(cost(entries[1:2]))


def test_new_audit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A cost audit launched in a directory the record of the start was
    listed with starts the window at the next call."""
    monkeypatch.setattr(kept_reads, "_store", None)
    kept_reads.open_store(tmp_path / "store.sqlite")
    root = tmp_path / "projects"
    agents = root / "session" / "subagents"
    agents.mkdir(parents=True)

    def run(agent: str, description: str, at: str) -> None:
        (agents / f"agent-{agent}.meta.json").write_text(json.dumps({"description": description}))
        (agents / f"agent-{agent}.jsonl").write_text(json.dumps(entry("m", at, 10)) + "\n")

    run("a1", "op editor x", "2026-10-16T10:10:00Z")
    new_process()
    assert audit_window.window(root, epoch(START), []).start == epoch(START)
    run("a2", "op cost-audit x", "2026-10-16T10:30:00Z")
    new_process()
    assert audit_window.window(root, epoch(START), []).start == epoch("2026-10-16T10:30:00Z")


def test_audit_after_state_opened(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A cost audit launched after a state brought the held directory
    listings up to date, and before that state's read of the window, starts
    the window at a later call."""
    monkeypatch.setattr(kept_reads, "_store", None)
    kept_reads.open_store(tmp_path / "store.sqlite")
    root = tmp_path / "projects"
    agents = root / "session" / "subagents"
    agents.mkdir(parents=True)
    (agents / "agent-a1.meta.json").write_text(json.dumps({"description": "op editor x"}))
    (agents / "agent-a1.jsonl").write_text(json.dumps(entry("m", "2026-10-16T10:10:00Z", 10)) + "\n")
    new_process()
    audit_window.window(root, epoch(START), [])
    state_reads.new_state()
    (agents / "agent-a2.meta.json").write_text(json.dumps({"description": "op cost-audit x"}))
    (agents / "agent-a2.jsonl").write_text(json.dumps(entry("m", "2026-10-16T10:30:00Z", 10)) + "\n")
    audit_window.window(root, epoch(START), [])
    new_process()
    assert audit_window.window(root, epoch(START), []).start == epoch("2026-10-16T10:30:00Z")
