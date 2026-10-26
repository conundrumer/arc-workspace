"""The name map of a solver (`parity.name_map`) holds the arclog relations
the converted program reads that no Souffle relation was written into."""

import json
from pathlib import Path

import pytest

import parity


def test_name_map_gives_the_unmapped_names(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(parity, "names_dir", lambda: tmp_path)
    (tmp_path / "s.json").write_text(json.dumps({
        "relations": {"&r": [{"component": [], "relation": "r", "path": "r"}]},
        "instances": {}, "constructors": {"$A": "A"}, "unmapped": ["&u", "&v"]}))
    names = parity.name_map("s")
    assert names is not None
    assert names.unmapped == ("&u", "&v")
    assert list(names.relations) == ["&r"]
