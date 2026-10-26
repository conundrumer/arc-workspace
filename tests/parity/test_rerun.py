"""The kept JSON of a rerun (`parity.rerun.kept_json`): it stands while the
key it was made under stands, and a rerun that gives no rows leaves none."""

from collections.abc import Mapping
from pathlib import Path

import pytest

from engine import Rows, RunFailure
from parity import rerun, snapshot
from solver.undefined import Undefined

Outcome = Mapping[str, Rows] | Undefined | RunFailure


class Stub:
    """Replaces the parts of a rerun that run Souffle and read the
    solver, and counts the runs."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        self.calls = 0
        self.outcome: Outcome = {"r": ()}
        self.key = "a"
        monkeypatch.setattr(snapshot, "parity_dir", lambda: tmp_path)
        monkeypatch.setattr(snapshot, "record_key", lambda stem: {"k": self.key})
        monkeypatch.setattr(rerun, "relations", self.relations)
        monkeypatch.setattr(rerun, "rerun_json", lambda stem, got: f"json {self.key}")

    def relations(self, stem: str, case: str, pair: str) -> Outcome:
        self.calls += 1
        return self.outcome


@pytest.fixture
def stub(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Stub:
    return Stub(monkeypatch, tmp_path)


def test_same_key_runs_once(stub: Stub) -> None:
    assert rerun.kept_json("s", "c", "train 0") == "json a"
    assert rerun.kept_json("s", "c", "train 0") == "json a"
    assert stub.calls == 1


def test_changed_key_runs_again(stub: Stub) -> None:
    rerun.kept_json("s", "c", "train 0")
    stub.key = "b"
    assert rerun.kept_json("s", "c", "train 0") == "json b"
    assert stub.calls == 2


def test_other_pair_runs_again(stub: Stub) -> None:
    rerun.kept_json("s", "c", "train 0")
    rerun.kept_json("s", "c", "train 1")
    assert stub.calls == 2


def test_no_rows_are_not_kept(stub: Stub) -> None:
    stub.outcome = Undefined()
    assert isinstance(rerun.kept_json("s", "c", "train 0"), Undefined)
    assert isinstance(rerun.kept_json("s", "c", "train 0"), Undefined)
    assert stub.calls == 2

