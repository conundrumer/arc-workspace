"""An editor whose launch an operator's transcript gives, and whose own
transcript is not written yet, is read as one that launched no check."""

import sys
from pathlib import Path

import pytest

from tests.conftest import script

elsewhere_reads = script("elsewhere_reads")
transcripts = sys.modules["transcripts"]


def test_an_editor_with_no_transcript_yet_gives_no_checks(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from operations.roles import Role
    from operations.state import Agent
    monkeypatch.setattr(transcripts, "project_dirs", lambda: [tmp_path])
    transcripts.new_state()
    editor = Agent("a0000000000000001", "aef519b953a4e20ed", Role.CODE_EDITOR, "9-1", "",
                   0.0, 0.0, None, (), True)
    undecided: list[str] = []
    read = elsewhere_reads.editor_checks([editor], tmp_path, undecided)
    assert read.agents == ()
