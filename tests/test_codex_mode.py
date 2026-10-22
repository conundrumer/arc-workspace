"""The switch and the launch fields it gives, as the build brief requires."""

from pathlib import Path

import pytest

from operations import codex_mode


@pytest.fixture
def switch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "synthetic-session")
    return tmp_path


@pytest.mark.parametrize("text", ["", "yes", "on off"])
def test_switch_refuses_invalid_file(switch: Path, text: str):
    path = codex_mode.SWITCH.path(switch)
    assert path is not None
    path.parent.mkdir(parents=True)
    path.write_text(text)
    with pytest.raises(ValueError):
        codex_mode.read(switch)
