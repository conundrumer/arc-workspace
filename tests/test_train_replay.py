"""A task's train replay record is stale when a file its key rests on changes."""
import json
from pathlib import Path

from arclog_convert import train_replay

ENGINE = "engine-digest"


def setup(tmp_path: Path):
    gen, tasks, records = tmp_path / "gen", tmp_path / "tasks", tmp_path / "train_replay"
    for directory in (gen, tasks, records):
        directory.mkdir()
    (gen / "aaaa0001.arclog").write_text("log")
    (gen / "aaaa0001.arcdata").write_text("(representative bbbb0002)\n")
    (gen / "bbbb0002.arclog").write_text("rep log")
    (gen / "bbbb0002.arcdata").write_text("rep data")
    (tasks / "aaaa0001.json").write_text("{}")
    key = train_replay.record_key("aaaa0001", gen, tasks, ENGINE)
    (records / "aaaa0001.json").write_text(json.dumps({"key": key, "cases": []}))
    return gen, tasks, records


def stale(tmp_path: Path, engine: str = ENGINE) -> list[str]:
    gen, tasks, records = tmp_path / "gen", tmp_path / "tasks", tmp_path / "train_replay"
    return train_replay.stale_tasks(["aaaa0001"], gen, tasks, records, engine)


def test_a_task_whose_files_are_unchanged_is_fresh(tmp_path):
    setup(tmp_path)
    assert stale(tmp_path) == []


def test_a_change_to_its_representatives_arcdata_makes_it_stale(tmp_path):
    gen, _, _ = setup(tmp_path)
    (gen / "bbbb0002.arcdata").write_text("changed")
    assert stale(tmp_path) == ["aaaa0001"]


def test_a_task_with_no_record_is_stale(tmp_path):
    _, _, records = setup(tmp_path)
    (records / "aaaa0001.json").unlink()
    assert stale(tmp_path) == ["aaaa0001"]
