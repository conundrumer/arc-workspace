"""A session forked from the main shares the main's index; were it read as
the main too, both would launch the main's reviews and adopt the idle
sessions' tickets."""

from pathlib import Path

import pytest

from engine import checkout
from tests.conftest import script


def test_fork_of_main_is_not_main(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.syspath_prepend(str(checkout.scripts()))
    module = script("idle_sessions")
    (tmp_path / "sessions").mkdir()
    (tmp_path / "sessions" / "1").write_text("main-session\nfork-session\n")
    (tmp_path / "main").write_text("main-session\n")
    assert module.read_sessions(tmp_path, 1, "main-session", 0.0).main
    assert not module.read_sessions(tmp_path, 1, "fork-session", 0.0).main
