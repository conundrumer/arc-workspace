"""The tickets an operator gives a ticket analyst to settle after a batch,
which the help of `file_ticket.py to-settle` defines."""

from collections.abc import Iterable
from pathlib import Path

from controlled_markdown import mctx
from ticket_form import ticket_kind, ticket_name, title
from ticket_log import read_ticket
from ticket_numbers import number_order, number_parts, ticket_number, ticket_path
from ticket_vocabulary import Domain, Kind, Status
from transcripts import Refused

MANY_IDEAS = "many ideas in one place"
"""The end of the title of a `refactor` ticket on a module that holds more
than one subject."""


def settled_elsewhere(tickets: Path, path: Path) -> bool:
    """Whether the list of `to-settle` leaves out the open ticket at
    `path`, refused where that command's help gives it refuses."""
    text = read_ticket(path)
    kind = ticket_kind(text)
    match kind:
        case None:
            raise Refused(mctx("{path} gives no kind in its front matter").format(path=path))
        case Kind.CHANGE:
            return True
        case Kind.QUESTION:
            name = ticket_name(path)
            return (name.domain is Domain.CHANGE
                    and ticket_path(tickets, name.subject).parent.name != Status.CLOSED)
        case Kind.REFACTOR:
            return title(path, text).endswith(MANY_IDEAS)
        case _:
            return False


def to_settle(tickets: Path, session: int, given: Iterable[str]) -> list[str]:
    """The numbers of the list of `to-settle`, for the session with index
    `session` and the numbers `given`. A ticket filed before tickets had
    numbers belongs to no session."""
    open_dir = tickets / Status.OPEN
    paths = {p for p in open_dir.glob("*.md")
             if (number := ticket_number(p)) and number_parts(number)[0] == session}
    paths.update(p for p in (ticket_path(tickets, ref) for ref in given) if p.parent == open_dir)
    numbers = [ticket_name(p).number for p in sorted(paths) if not settled_elsewhere(tickets, p)]
    return sorted(numbers, key=number_order)
