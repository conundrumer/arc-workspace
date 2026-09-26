"""Two runs that write one witness file at the same time."""

import threading
import time
from pathlib import Path

import dl.witness as witness


def _entry(entry_id: str) -> dict:
    return {"id": entry_id, "separates": "x", "input": [[0]],
            "output": [{"cases": ["concept"], "grid": [[1]]}]}


def test_concurrent_records_keep_both_entries(tmp_path: Path, monkeypatch):
    path = tmp_path / "race.wit.json"
    read = witness.read_witness_data

    def slow_read(task_id: str, p: Path | None = None) -> dict:
        data = read(task_id, p)
        time.sleep(0.3)  # the other writer's read lands in this gap
        return data

    monkeypatch.setattr(witness, "read_witness_data", slow_read)
    runs = [threading.Thread(target=witness.write_entries,
                             args=("aa62e3f4", path, [_entry(i)]))
            for i in ("race-one", "race-two")]
    for t in runs:
        t.start()
    for t in runs:
        t.join()
    ids = {e["id"] for e in read("aa62e3f4", path)["witnesses"]}
    assert ids == {"race-one", "race-two"}
