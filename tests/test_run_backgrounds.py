"""The files processes hold open (`run_backgrounds.open_files`), read from
`lsof`: a misread line gives a running command as ended, with no failure."""

import os
import stat
import sys
from pathlib import Path

import pytest

from handbook.paths import scripts_importable
from tests.conftest import script

scripts_importable()
run_backgrounds = script("run_backgrounds")
state_reads = sys.modules["state_reads"]
Refused = sys.modules["transcript_snapshots"].Refused

LISTING = "\n".join(["p10", "fcwd", "k3", "n/d", "f1", "k1", "n/d/held.output",
                     "f2", "k0", "n/d/gone.output", "f3", "nlocalhost:5000", ""])


def fake_lsof(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, out: str, err: str) -> None:
    (tmp_path / "out").write_text(out)
    (tmp_path / "err").write_text(err)
    lsof = tmp_path / "lsof"
    lsof.write_text(f"#!/bin/sh\ncat {tmp_path / 'out'}\ncat {tmp_path / 'err'} >&2\nexit 1\n")
    lsof.chmod(lsof.stat().st_mode | stat.S_IXUSR)
    monkeypatch.setenv("PATH", f"{tmp_path}{os.pathsep}{os.environ['PATH']}")
    state_reads.new_state()


def test_open_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Each path `lsof` gives is held open, and each whose link count is 0 is
    gone."""
    fake_lsof(tmp_path, monkeypatch, LISTING, "")
    files = run_backgrounds.open_files()
    assert files.paths == {"/d", "/d/held.output", "/d/gone.output", "localhost:5000"}
    assert files.gone == {"/d/gone.output"}


def test_open_files_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Where `lsof` writes to stderr, the open files are refused."""
    fake_lsof(tmp_path, monkeypatch, LISTING, "lsof: fault")
    with pytest.raises(Refused):
        run_backgrounds.open_files()
