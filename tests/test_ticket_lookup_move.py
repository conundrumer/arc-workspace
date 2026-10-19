"""A lookup of a ticket by its number, made while a rename moves the ticket
from one status directory to another, must give the ticket's one path: a
refusal there fails the command that made the lookup, and `ticket_text`
gives a changed ticket an empty Scope with no report."""

import os
from pathlib import Path

import pytest

from handbook.paths import scripts_importable
from tests.conftest import script

NAME = "11-7_ticket_t_code-editor.md"


class Directory:
    """A status directory whose first read, where it is `released`, is followed
    by the rename of the ticket from `source` to `target`."""

    def __init__(self, path: Path, source: str, target: str, moves: list[bool]) -> None:
        self.path, self.source, self.target, self.moves = path, source, target, moves

    def glob(self, pattern: str) -> list[Path]:
        found = list(self.path.glob(pattern))
        if self.path.name == "released" and not self.moves[0]:
            self.moves[0] = True
            os.rename(self.path.parent / self.source / NAME, self.path.parent / self.target / NAME)
        return found


@pytest.mark.parametrize("source,target", [("released", "assigned"), ("assigned", "released")])
def test_ticket_path_reads_again_after_a_move(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                                              source: str, target: str) -> None:
    """`released` is read before `assigned`, so the move shows the ticket at
    two paths where it goes to `assigned`, and at none where it goes to
    `released`."""
    scripts_importable()
    module = script("ticket_files")
    for status in module.Status:
        (tmp_path / status).mkdir()
    (tmp_path / source / NAME).touch()
    moves = [False]
    monkeypatch.setattr(module, "statuses",
                        lambda tickets: [Directory(tickets / s, source, target, moves) for s in module.Status])
    number = module.ticket_name(tmp_path / source / NAME).number
    assert module.ticket_path(tmp_path, number) == tmp_path / target / NAME
    assert moves == [True]


def test_listed_ticket_path_reads_again_on_a_torn_listing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    scripts_importable()
    module = script("ticket_files")
    for status in module.Status:
        (tmp_path / status).mkdir()
    (tmp_path / "assigned" / NAME).touch()
    number = module.ticket_name(tmp_path / "assigned" / NAME).number
    torn = {str(number): (tmp_path / "assigned" / NAME, tmp_path / "released" / NAME)}
    monkeypatch.setattr(module, "numbered_files", lambda tickets: torn)
    assert module.listed_ticket_path(tmp_path, number) == tmp_path / "assigned" / NAME
