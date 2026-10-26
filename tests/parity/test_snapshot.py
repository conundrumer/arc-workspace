"""A stored record is fresh while the files it rests on stand as they
stood when it was written, and not once one of them changes."""

import json
from pathlib import Path

import pytest

from engine import checkout
from parity import snapshot

STEM = "00dbd492"


def test_record_is_stale_once_its_solver_changes(root: Path, tmp_path: Path,
                                                 monkeypatch: pytest.MonkeyPatch) -> None:
    records = tmp_path / "parity"
    monkeypatch.setattr(snapshot, "parity_dir", lambda: records)
    monkeypatch.setattr(snapshot, "names_path", lambda stem: tmp_path / "names" / f"{stem}.json")
    solver = root / "programs" / "solvers" / f"{STEM}.dl"
    solver.write_text("// a solver\n")
    records.mkdir()
    snapshot.record_path(STEM).write_text(json.dumps({"key": snapshot.record_key(STEM)}))
    assert snapshot.fresh(STEM)
    solver.write_text("// the solver, changed\n")
    assert not snapshot.fresh(STEM)


def test_record_is_stale_once_arc_code_changes(tmp_path: Path,
                                              monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(checkout, "ROOT", tmp_path)
    records = tmp_path / "parity"
    monkeypatch.setattr(snapshot, "parity_dir", lambda: records)
    monkeypatch.setattr(snapshot, "names_path", lambda stem: tmp_path / "names" / f"{stem}.json")
    arc = tmp_path / "src" / "arc" / "task.py"
    arc.parent.mkdir(parents=True)
    arc.write_text("# arc code\n")
    records.mkdir()
    snapshot.record_path(STEM).write_text(json.dumps({"key": snapshot.record_key(STEM)}))
    assert snapshot.fresh(STEM)
    arc.write_text("# arc code, changed\n")
    assert not snapshot.fresh(STEM)


def source(component: list[str], relation: str, path: str) -> dict:
    return {"component": component, "relation": relation, "path": path}


def test_record_is_stale_only_once_the_name_map_changes_a_case_name(root: Path, tmp_path: Path,
                                                                    monkeypatch: pytest.MonkeyPatch) -> None:
    """The case names read the constructors, the parameters, and, with a
    `@store` line, the relations; a change to another relation leaves the
    record fresh."""
    records = tmp_path / "parity"
    names = tmp_path / "names" / f"{STEM}.json"
    monkeypatch.setattr(snapshot, "parity_dir", lambda: records)
    monkeypatch.setattr(snapshot, "names_path", lambda stem: names)
    solver = root / "programs" / "solvers" / f"{STEM}.dl"
    solver.write_text("// a solver\n")
    names.parent.mkdir()
    base = {"constructors": {"$A": "A"}, "unmapped": [], "instances": {}, "stores": False,
            "relations": {"&p": [source(["Params"], "p", "params.p")], "&r": [source([], "r", "r")]}}

    def write(**changes: object) -> None:
        names.write_text(json.dumps({**base, **changes}))

    write()
    records.mkdir()
    snapshot.record_path(STEM).write_text(json.dumps({"key": snapshot.record_key(STEM)}))
    assert snapshot.fresh(STEM)
    write(relations={**base["relations"], "&s": [source([], "s", "s")]})
    assert snapshot.fresh(STEM)
    write(relations={**base["relations"], "&q": [source(["Params"], "q", "params.q")]})
    assert not snapshot.fresh(STEM)
    write()
    assert snapshot.fresh(STEM)
    write(constructors={"$B": "B"})
    assert not snapshot.fresh(STEM)
    write(stores=True)
    snapshot.record_path(STEM).write_text(json.dumps({"key": snapshot.record_key(STEM)}))
    assert snapshot.fresh(STEM)
    write(stores=True, relations={**base["relations"], "&s": [source([], "s", "s")]})
    assert not snapshot.fresh(STEM)
