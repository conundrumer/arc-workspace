"""The tickets an operator gives a ticket analyst to settle after a batch,
which `file_ticket.py to-settle --help-all` defines."""

from collections.abc import Collection, Iterable
from pathlib import Path

from controlled_markdown import mctx
from ticket_files import TicketName, ticket_files, ticket_name, ticket_path, ticket_status
from ticket_form import ticket_kind, title
from ticket_log import read_ticket
from ticket_numbers import TicketNumber, ticket_number
from ticketing.vocabulary import MANY_IDEAS, Domain, Kind, Status
from transcripts import Refused

def settled_elsewhere(tickets: Path, path: Path, name: TicketName) -> bool:
    """Whether the list of `to-settle` leaves out the open ticket at
    `path`, named `name`, refused where that command's help gives it
    refuses."""
    text = read_ticket(path)
    kind = ticket_kind(text)
    match kind:
        case None:
            raise Refused(mctx("{path} gives no kind in its front matter").format(path=path))
        case Kind.CHANGE:
            return True
        case Kind.QUESTION:
            return (name.domain is Domain.CHANGE and ticket_status(
                ticket_path(tickets, ticket_number(name.subject))) is not Status.CLOSED)
        case Kind.REFACTOR:
            return title(path, text).endswith(MANY_IDEAS)
        case _:
            return False


def to_settle(tickets: Path, session: int, adopted: Collection[int],
              given: Iterable[TicketNumber]) -> list[TicketNumber]:
    """The numbers of the list of `to-settle`, for the session with index
    `session`, the indexes it adopts (`idle_sessions.Sessions.adopted`) and
    the numbers `given`."""
    names = {p: ticket_name(p) for p in ticket_files(tickets, Status.OPEN)}
    paths = {p for p, name in names.items() if name.number.session == session
             or name.number.session in adopted}
    paths.update(p for p in (ticket_path(tickets, number) for number in given) if p in names)
    numbers = [names[p].number for p in sorted(paths) if not settled_elsewhere(tickets, p, names[p])]
    return sorted(numbers, key=lambda number: number.order)
