"""A settled unknown spend under `tickets/spends/` is read as no known spend,
with no read of its change's runs."""

from pathlib import Path
from typing import Any

import pytest

from handbook.paths import scripts_importable
from tests.conftest import script


def test_settled_unknown_record_reads_no_runs(tmp_path: Path,
                                              monkeypatch: pytest.MonkeyPatch) -> None:
    scripts_importable()
    module: Any = script("spends")
    (tmp_path / "closed").mkdir()
    path = tmp_path / "closed" / "9-1_change_slow_code-editor.md"
    path.write_text("---\nkind: change\neditors: code-editor\n---\n# t: w\n\n## Log\n"
                    "2026-10-17T00:00:00Z closed [operator]: fixed 9-1 abc\n")
    (tmp_path / module.SPENDS).mkdir()
    (tmp_path / module.SPENDS / "9-1.json").write_text("null\n")

    def read_runs(*_: object) -> None:
        raise AssertionError("runs read")

    monkeypatch.setattr(module, "owners", read_runs)
    assert module.recorded_spend(path) is module.Unknown.SPEND
    assert module.change_spend(path, []) is None
    assert module.like_changes(tmp_path, frozenset(), float("inf"), []) == []
