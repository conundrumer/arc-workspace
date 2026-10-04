"""An issue filed under a name already taken, in any status, must not
replace that file: the replaced issue would be lost without a sign."""

import importlib.util
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "file_issue.py"

ISSUE = "---\nkind: delay\n---\n# t: w\n\n## Effect\ne\n\n## Evidence\nv\n"


def test_taken_names_are_kept(tmp_path: Path) -> None:
    spec = importlib.util.spec_from_file_location("file_issue", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["file_issue"] = module
    spec.loader.exec_module(module)
    (tmp_path / "assigned").mkdir()
    (tmp_path / "assigned" / "7-s-a-1.md").write_text("assigned")
    first = module.file_issue(tmp_path, "7", "s", "a", ISSUE)
    second = module.file_issue(tmp_path, "7", "s", "a", ISSUE + "x\n")
    assert [first.name, second.name] == ["7-s-a-2.md", "7-s-a-3.md"]
    assert (tmp_path / "assigned" / "7-s-a-1.md").read_text() == "assigned"
    assert first.read_text() == ISSUE
    assert sorted(p.name for p in (tmp_path / "new").iterdir()) == ["7-s-a-2.md", "7-s-a-3.md"]
