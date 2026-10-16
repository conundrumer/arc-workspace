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
    package."""
    spec = importlib.util.spec_from_file_location(name, checkout.scripts() / f"{name}.py")
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
