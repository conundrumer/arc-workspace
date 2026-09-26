"""No command creates a task's witness file."""

from pathlib import Path

import dl.cli as cli

STEM = "a09f6c25"


def test_record_does_not_create_the_task_file(tmp_path: Path, monkeypatch):
    missing = tmp_path / f"{STEM}.wit.json"
    monkeypatch.setattr(cli, "witness_path", lambda _task_id: missing)
    monkeypatch.setattr(cli, "REPO_ROOT", tmp_path)
    grid = tmp_path / "grid.txt"
    grid.write_text("0 1\n1 0\n")
    assert cli.cmd_record(STEM, "probe", "probe", str(grid)) == 2
    assert not missing.exists()


def test_record_does_not_create_a_named_file_in_the_witness_dir(
        tmp_path: Path, monkeypatch):
    witness_dir = tmp_path / "witnesses"
    witness_dir.mkdir()
    missing = witness_dir / f"{STEM}.wit.json"
    monkeypatch.setattr(cli, "witness_path",
                        lambda task_id: witness_dir / f"{task_id}.wit.json")
    monkeypatch.setattr(cli, "REPO_ROOT", tmp_path)
    monkeypatch.chdir(tmp_path)
    grid = tmp_path / "grid.txt"
    grid.write_text("0 1\n1 0\n")
    named = "witnesses/../witnesses/" + missing.name
    assert cli.cmd_record(STEM, "probe", "probe", str(grid),
                          witness_file=named) == 2
    assert not missing.exists()
