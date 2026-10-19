"""Two filers that race for a ticket number must get two numbers, and a
filer that dies after its reservation must not cost a later ticket its
file: either fault would lose a ticket without a sign."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from tests.conftest import script

TICKET = "---\nkind: bug\n---\n# t: w\n\n## Impact\ne\n\n## Evidence\nv\n"


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
    numbers = [script("ticket_files").ticket_name(p).number for p in paths]
    assert {number.session for number in numbers} == {2}
    assert sorted(number.n for number in numbers) == list(range(4, 20))
    assert sorted(p.name for p in (tmp_path / "new").iterdir()) == sorted(p.name for p in paths)
    assert {p.read_text().split("\n\n## Log\n")[0] for p in paths} == {TICKET + f"{i}" for i in range(16)}
