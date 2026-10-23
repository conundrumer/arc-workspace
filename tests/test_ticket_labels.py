"""The label of a ticket (`operations.labels.label`) and the letters of the
ticket kinds."""

from pathlib import Path

from operations.labels import label
from operations.state import Ticket
from ticketing.vocabulary import LETTER, Kind, Status, Domain, lettered


def ticket(number: str, kind: Kind, title: str, motivation: tuple[str, ...] = (),
           goal: str | None = None, validates: str | None = None) -> Ticket:
    return Ticket(
        number=number, order=(0, 0), session=None, status=Status.NEW, kind=kind, domain=Domain.CHANGE,
        subject="s", filer="f", filed=0.0, title=title, depends_on=(), motivation=motivation, editors=None,
        after_merge=None, mechanical=False, log=(), allowers=(), holder=None, path=Path("x"),
        goal=goal, validates=validates)


def test_every_kind_has_its_own_letter() -> None:
    assert set(LETTER) == set(Kind)
    assert len(set(LETTER.values())) == len(Kind)
    assert lettered(Kind.CHANGE, "11-3451") == "C11-3451"


def test_change_and_validation_name_their_request() -> None:
    request = ticket("11-1", Kind.REQUEST, "request 11-1: x", goal="Show it")
    change = ticket("11-2", Kind.CHANGE, "src/a.py: the thing, more", motivation=("11-1",))
    validation = ticket("11-3", Kind.VALIDATION, "request 11-1: check it", validates="11-1")
    bug = ticket("11-4", Kind.BUG, "a.py: it breaks")
    all_ = {t.number: t for t in (request, change, validation, bug)}
    assert label(request, all_) == "R11-1 (Show it)"
    assert label(change, all_) == "C11-2 (The thing), for R11-1"
    assert label(validation, all_) == "V11-3 (Check it), for R11-1"
    assert label(bug, all_) == "B11-4 (It breaks)"
