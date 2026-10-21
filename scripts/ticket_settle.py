"""The tickets an operator gives a ticket analyst to settle after a batch,
which `file_ticket.py to-settle --help-all` defines."""

from collections.abc import Collection, Iterable
from pathlib import Path

from controlled_markdown import mctx
from operations.state import acted_on
from ticket_files import TicketName, listed_ticket_path, ticket_files, ticket_name, ticket_status
from ticket_form import depends_on, front, ticket_kind, title
from ticket_log import read_ticket
from ticket_numbers import TicketNumber, ticket_number
from ticketing.exits import Exit, exit_of
from ticketing.vocabulary import UNTAKEN, Domain, Kind, Status
from transcript_snapshots import Refused, SUBJECT_FAULTS

def settled_elsewhere(tickets: Path, path: Path, name: TicketName) -> bool:
    """Whether the list of `to-settle` leaves out the untaken ticket at
    `path`, named `name`, refused where that command's help gives it
    refuses."""
    text = read_ticket(path)
    kind = ticket_kind(text)
    if kind is None:
        raise Refused(mctx("{path} gives no kind in its front matter").format(path=path))
    def is_open(number: str) -> bool:
        return ticket_status(listed_ticket_path(tickets, ticket_number(number))) is not Status.CLOSED

    on_open_change = kind is Kind.QUESTION and name.domain is Domain.CHANGE and is_open(name.subject)
    exits = exit_of(ticket_status(path), kind, on_open_change=on_open_change, title=title(path, text))
    return Exit.TICKET_ANALYST not in exits.by or any(map(is_open, depends_on(front(text))))


def to_settle(tickets: Path, session: int, adopted: Collection[int],
              given: Iterable[TicketNumber], undecided: list[str] | None = None,
              me: str = "") -> list[TicketNumber]:
    """The numbers of the list of `to-settle`, for the session with index
    `session`, the indexes it adopts (`state.SessionsRead.adopted`) and
    the numbers `given`."""
    if undecided is None:
        undecided = []
    given = set(given)
    numbers: list[TicketNumber] = []
    for status in UNTAKEN:
        for path in ticket_files(tickets, status):
            try:
                name = ticket_name(path)
                if (acted_on(name.number.session, session, adopted) or name.number in given
                        ) and not settled_elsewhere(tickets, path, name):
                    numbers.append(name.number)
            except SUBJECT_FAULTS as exc:
                undecided.append(mctx("{run}: ticket {path} cannot be read ({error}), "
                                      "so it is left out of tickets to settle").format(
                                          run=me, path=path, error=exc))
    return sorted(numbers, key=lambda number: number.order)
