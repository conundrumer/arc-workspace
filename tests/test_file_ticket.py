"""Two filers that race for a ticket number must get two numbers, and a
filer that dies after its reservation must not cost a later ticket its
file: either fault would lose a ticket without a sign. A name already
taken, in any status, must not be replaced."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from tests.conftest import script

TICKET = "---\nkind: bug\n---\n# t: w\n\n## Impact\ne\n\n## Evidence\nv\n"
ISSUE = "---\nkind: undecided\n---\n# t: w\n\n## Effect\ne\n\n## Evidence\nv\n"


def test_racing_filers_get_distinct_numbers(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    module = script("file_ticket")
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "session-a")
    (tmp_path / "sessions").mkdir()
    (tmp_path / "sessions" / "2").write_text("session-a\n")
    (tmp_path / "ids").mkdir()
    (tmp_path / "ids" / "2-3").touch()
    with ThreadPoolExecutor(8) as pool:
        paths = list(pool.map(lambda i: module.file_ticket(
            tmp_path, "agent", "a" + "0" * 16, "code-editor", TICKET + f"{i}\n"), range(16)))
    files, numbering = script("ticket_files"), script("ticket_numbers")
    numbers = [numbering.number_parts(files.ticket_number(p)) for p in paths]
    assert {session for session, _ in numbers} == {2}
    assert sorted(n for _, n in numbers) == list(range(4, 20))
    assert sorted(p.name for p in (tmp_path / "open").iterdir()) == sorted(p.name for p in paths)
    assert {p.read_text().split("\n\n## Log\n")[0] for p in paths} == {TICKET + f"{i}" for i in range(16)}


def test_legacy_taken_names_are_kept(tmp_path: Path) -> None:
    module = script("file_issue")
    (tmp_path / "assigned").mkdir()
    (tmp_path / "assigned" / "7-s-a-1.md").write_text("assigned")
    first = module.file_legacy(tmp_path, "7", "s", "a", ISSUE)
    second = module.file_legacy(tmp_path, "7", "s", "a", ISSUE + "x\n")
    assert [first.name, second.name] == ["7-s-a-2.md", "7-s-a-3.md"]
    assert (tmp_path / "assigned" / "7-s-a-1.md").read_text() == "assigned"
    assert first.read_text().startswith(TICKET.replace("bug", "question"))
    assert sorted(p.name for p in (tmp_path / "open").iterdir()) == ["7-s-a-2.md", "7-s-a-3.md"]
