"""The paths a section of a ticket gives, as `section_paths` reads them,
and the text of a ticket where it stands now, as `ticket_text` reads it."""

from pathlib import Path

from handbook.paths import scripts_importable

scripts_importable()

from ticket_files import ticket_path  # noqa: E402
from ticket_form import given_paths  # noqa: E402
from ticket_numbers import ticket_number  # noqa: E402
from transcript_snapshots import Refused  # noqa: E402

from operations.state import Ticket  # noqa: E402
from operations.task_work import task_paths  # noqa: E402
from solver.vocabulary import SOLVER_SUFFIX  # noqa: E402
from ticketing.text import SECTIONS  # noqa: E402
from ticketing.vocabulary import Kind  # noqa: E402

_, _, SCOPE, _ = SECTIONS[Kind.CHANGE]

def section_paths(text: str, name: str, root: Path) -> frozenset[str]:
    """The paths `ticket_form.given_paths` reads of the section `name` of
    the ticket text `text`, and, for each solver among them, that solver's
    witness file, since a solver and its witness file are edited
    together."""
    given = given_paths(text, name, root)
    pairs = (task_paths(Path(p).name.removesuffix(SOLVER_SUFFIX)) for p in given)
    return given | {str(w) for s, w in pairs if str(s) in given}


def ticket_text(t: Ticket) -> str | None:
    """The text of the ticket `t` where it stands now: at `t.path`, or,
    where it moved after the tracker read, at the path `ticket_path` gives
    it, read again for each later move. None where `ticket_path` refuses
    it."""
    path = t.path
    while True:
        try:
            return path.read_text()
        except FileNotFoundError:
            try:
                path = ticket_path(t.path.parent.parent, ticket_number(t.number))
            except Refused:
                return None


def scope_paths(t: Ticket, root: Path) -> frozenset[str]:
    """`section_paths` of the Scope of `t` where it stands now, none where
    it stands nowhere."""
    text = ticket_text(t)
    return frozenset() if text is None else section_paths(text, SCOPE, root)
