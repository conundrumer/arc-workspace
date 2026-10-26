"""The hold of the heavy commands' lock a run takes, and the checkout a test
runs the commands in."""

import contextlib
import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

from engine import checkout, rwlock

def pytest_configure(config: pytest.Config) -> None:
    """The run holds the heavy commands' lock shared from its start to its
    end. A worker of the run, and every command a test starts, runs under
    that hold."""
    hold = contextlib.ExitStack()
    hold.enter_context(rwlock.held(rwlock.Hold.SHARED))
    config.add_cleanup(hold.close)


def script(name: str) -> ModuleType:
    """The script `scripts/<name>.py`, loaded from its path: `scripts/` is no
    package. A script already in `sys.modules` under `name` that was loaded
    from the same path is returned, so a test process holds one module
    object for each script, as a real process does. A test that needs a
    fresh module reloads it with `importlib.reload`. `scripts/` is put on
    `sys.path` first, so the script imports its siblings."""
    from handbook.paths import scripts_importable
    scripts_importable()
    path = checkout.scripts() / f"{name}.py"
    loaded = sys.modules.get(name)
    if loaded is not None and getattr(loaded, "__file__", None) == str(path):
        return loaded
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A checkout under `tmp_path` whose solvers and witness directories
    start empty, with every other file the checkout's, and the checkout's
    run cache. The commands read and write the solvers and witness files
    there."""
    real = checkout.ROOT
    monkeypatch.setenv(checkout.CACHE_ENV, str(checkout.cache()))
    for entry in real.iterdir():
        if entry.name not in ("programs", "work", "tickets", ".cache", ".git"):
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


@pytest.fixture(autouse=True)
def attempt_journal(tmp_path, monkeypatch):
    """Keep lifecycle writes in each test's own filesystem."""
    attempt_record = script("attempt_record")
    monkeypatch.setattr(attempt_record, 'directory', lambda: tmp_path / '.attempts')


PAINT_STEM = "3c9b0459"
PAINT_SOLVER = f"""// {PAINT_STEM}
// @keywords: test
// input: a grid
// output: the grid

.type Paint = FieldPaint {{}} | StoredPaint {{}}
.type Choice = [pt: Paint]

.decl field(f: Color)
field(F) :- in(_, F).

.decl paint_of(pt: Paint, f: Color, col: Color)
paint_of($FieldPaint(), F, F) :- field(F).
paint_of($StoredPaint(), F, C) :- field(F), in(_, C), C != F.

.decl out(p: Position, col: Color, c: Choice)
out(P, C, [Pt]) :- in(P, F), paint_of(Pt, F, C).
"""
"""A solver whose relation `paint_of` repeats a column under the concept's
`FieldPaint` and has two columns under `StoredPaint`."""


@pytest.fixture
def paint(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """The solver file of `PAINT_SOLVER` under `tmp_path`, converted there;
    the converter's output is read from `tmp_path / "out"`."""
    import os
    import subprocess
    from arclog_convert import OUT_ENV
    programs = tmp_path / "programs"
    (programs / "solvers").mkdir(parents=True)
    for entry in (checkout.ROOT / "programs").iterdir():
        if entry.name != "solvers":
            (programs / entry.name).symlink_to(entry)
    file = programs / "solvers" / f"{PAINT_STEM}.dl"
    file.write_text(PAINT_SOLVER)
    subprocess.run([sys.executable, "-m", "arclog_convert.convert", 
                    "--out", str(tmp_path / "out"), PAINT_STEM],
                   cwd=checkout.ROOT, check=True, capture_output=True,
                   env={**os.environ, "ARCLOG_SOLVERS": str(programs / "solvers")})
    monkeypatch.setenv(OUT_ENV, str(tmp_path / "out"))
    return file
