"""The kept plans and lint results are keyed on their solver file by its path
from the checkout's root, so that every checkout reads what another kept."""

import hashlib
from pathlib import Path

import pytest

from checker.plan_cache import hash_solver_files
from engine import checkout

TASK = "a2d730bd"


def _hash(root: Path, monkeypatch: pytest.MonkeyPatch, text: str) -> str:
    source = root / checkout.SOLVERS / f"{TASK}.dl"
    source.parent.mkdir(parents=True)
    source.write_text(text)
    monkeypatch.setattr(checkout, "ROOT", root)
    h = hashlib.sha256()
    hash_solver_files(h, source, TASK)
    return h.hexdigest()


def test_a_solver_file_in_two_checkout_roots_gives_one_hash(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    first = _hash(tmp_path / "a", monkeypatch, "o(1).\n")
    assert _hash(tmp_path / "b", monkeypatch, "o(1).\n") == first
    assert _hash(tmp_path / "c", monkeypatch, "o(2).\n") != first
