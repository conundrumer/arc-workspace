"""A task's train replay record is fresh where its files and its sources or its binary are equal."""
import json
from pathlib import Path

import pytest
from arclog_convert import train_replay

SOURCES = "sources-digest"
BINARY = "binary-digest"


def setup(tmp_path: Path):
    gen, tasks, records = tmp_path / "gen", tmp_path / "tasks", tmp_path / "train_replay"
    for directory in (gen, tasks, records):
        directory.mkdir()
    (gen / "aaaa0001.arclog").write_text("log")
    (gen / "aaaa0001.arcdata").write_text("(representative bbbb0002)\n")
    (gen / "bbbb0002.arclog").write_text("rep log")
    (gen / "bbbb0002.arcdata").write_text("rep data")
    (tasks / "aaaa0001.json").write_text("{}")
    files = train_replay.files_digest("aaaa0001", gen, tasks)
    record = {"files": files, "sources": SOURCES, "binary": BINARY, "cases": []}
    (records / "aaaa0001.json").write_text(json.dumps(record))
    return gen, tasks, records


def stale(tmp_path: Path, sources: str = SOURCES, binary: str = BINARY) -> list[str]:
    gen, tasks, records = tmp_path / "gen", tmp_path / "tasks", tmp_path / "train_replay"
    return train_replay.stale_tasks(["aaaa0001"], gen, tasks, records, sources, lambda: binary)


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


def test_a_task_with_equal_files_and_equal_binary_is_fresh_and_gets_its_sources_rewritten(tmp_path):
    _, _, records = setup(tmp_path)
    assert stale(tmp_path, sources="other") == []
    assert json.loads((records / "aaaa0001.json").read_text())["sources"] == "other"


def test_a_task_with_equal_files_and_other_sources_and_binary_is_stale(tmp_path):
    setup(tmp_path)
    assert stale(tmp_path, sources="other", binary="other") == ["aaaa0001"]


def test_a_record_in_the_old_form_is_stale(tmp_path):
    _, _, records = setup(tmp_path)
    (records / "aaaa0001.json").write_text(json.dumps({"key": "k", "cases": []}))
    assert stale(tmp_path) == ["aaaa0001"]


def test_train_replay_takes_no_accept():
    with pytest.raises(SystemExit) as e:
        train_replay.main(["--accept"])
    assert e.value.code == 2


def test_convert_accept_with_no_train_replay_is_refused_before_any_conversion(tmp_path, monkeypatch):
    from arclog_convert import convert
    monkeypatch.setenv("ARCLOG_OUT", str(tmp_path))
    with pytest.raises(SystemExit) as e:
        convert.main(["--accept", "--no-train-replay"])
    assert e.value.code == 2
    assert list(tmp_path.iterdir()) == []
