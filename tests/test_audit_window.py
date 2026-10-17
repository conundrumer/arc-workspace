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
    audit_window._records.clear()
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
