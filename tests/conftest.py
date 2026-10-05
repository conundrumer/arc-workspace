"""The checkout a test runs the commands in, and the `data/upstream/`
submodules a test of the upstream tasks reads."""

import fcntl
import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

from engine import checkout

UPSTREAM_LOCK = "arc-upstream.lock"
"""The lock file, in the repository's common git directory, that one
submodule setup at a time holds."""


def script(name: str) -> ModuleType:
    """The script `scripts/<name>.py`, loaded from its path: `scripts/` is no
    package."""
    spec = importlib.util.spec_from_file_location(name, checkout.scripts() / f"{name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="session")
def upstream() -> None:
    """The checkout's `data/upstream/` submodules, set up where one is not
    checked out, as `scripts/merge_change.py` sets them up: from the main
    worktree's copies of their repositories, with no network. A worktree
    starts with them empty. Where the setup fails, the test fails with its
    cause."""
    merge_change = script("merge_change")
    root = checkout.ROOT
    with open(checkout.git_common_dir(root) / UPSTREAM_LOCK, "a") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        if all(merge_change.checked_out(root, sub)
               for sub in merge_change.submodules(root)):
            return
        try:
            merge_change.set_up_submodules(root, checkout.main_worktree(root))
        except merge_change.Refused as exc:
            pytest.fail(f"the data/upstream/ submodules are not checked out in {root}, "
                        f"and {exc}", pytrace=False)


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
