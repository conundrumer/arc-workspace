"""The checkout a test runs the commands in."""

from pathlib import Path

import pytest

from engine import checkout


@pytest.fixture
def root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A checkout under `tmp_path` whose solvers and witness directories
    start empty, with every other file the checkout's. The commands read
    and write the solvers and witness files there."""
    real = checkout.ROOT
    for entry in real.iterdir():
        if entry.name not in ("programs", ".scratch", ".git"):
            (tmp_path / entry.name).symlink_to(entry)
    programs = tmp_path / "programs"
    programs.mkdir()
    for entry in (real / "programs").iterdir():
        if entry.name not in ("solvers", "witnesses"):
            (programs / entry.name).symlink_to(entry)
    (programs / "solvers").mkdir()
    (programs / "witnesses").mkdir()
    monkeypatch.setattr(checkout, "ROOT", tmp_path)
    return tmp_path
