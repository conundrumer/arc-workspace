"""A ticket's file under the main tree's `tickets/`: the form of its name,
with the fields `TicketName` gives it and `ticket_name` reads from it, the
directory of each status the file moves between, and the path of a ticket
found by its number."""

import glob
import os
import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field, fields
from pathlib import Path

from controlled_markdown import mctx
from ticket_numbers import TICKET_NUMBER, TicketNumber, is_reserved, matched_number
from ticketing.vocabulary import Domain, Status
from file_reads import names_in
from state_reads import DERIVED, state_cache
from transcript_snapshots import Refused

FIELD = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
"""A field of a ticket's name: kebab words, with no `_`, which separates
the fields."""

SUFFIX = ".md"
"""The end of the name of each ticket's file."""


PATTERN = "pattern"
"""The key of the metadata of a field of `TicketName` that gives the
pattern its text in a ticket's file name matches."""


@dataclass(frozen=True)
class TicketName:
    """The fields of a ticket's file name, in their order in it."""
    number: TicketNumber = field(metadata={PATTERN: TICKET_NUMBER})
    domain: Domain = field(metadata={PATTERN: FIELD})
    subject: str = field(metadata={PATTERN: FIELD})
    agent: str = field(metadata={PATTERN: FIELD})

    @property
    def file_name(self) -> str:
        return joined_name(str(getattr(self, f.name)) for f in fields(self))


def joined_name(parts: Iterable[str], escape: Callable[[str], str] = str) -> str:
    return escape("_").join(parts) + escape(SUFFIX)


NAME_FORM = joined_name(f"<{f.name}>" for f in fields(TicketName))
"""The form of a ticket's file name, as a help text writes it."""

TICKET_NAME = re.compile(joined_name(
    (f"(?P<{f.name}>{f.metadata[PATTERN].pattern})" for f in fields(TicketName)), re.escape))


def ticket_name(path: Path) -> TicketName:
    name = TICKET_NAME.fullmatch(path.name)
    if name is not None and name["domain"] in set(Domain):
        return TicketName(number=matched_number(name), domain=Domain(name["domain"]),
                          subject=name["subject"], agent=name["agent"])
    raise Refused(mctx("{path} is not named `{form}`").format(path=path, form=NAME_FORM))


def statuses(tickets: Path) -> list[Path]:
    return [tickets / s for s in Status]


def ticket_status(path: Path) -> Status:
    """The status the ticket at `path`, a path `ticket_path` gives or one
    under the directory of a status, stands in."""
    return Status(path.parent.name)


def entry_names(directory: Path) -> list[str]:
    """The names of the entries of `directory`, none where there is none."""
    try:
        return os.listdir(directory)
    except FileNotFoundError:
        return []


def ticket_files(tickets: Path, status: Status,
                 names: Callable[[Path], Iterable[str]] = entry_names) -> list[Path]:
    """The files of a status's directory, of the names `names` gives of its
    entries. A closed file whose name `TICKET_NAME` does not match is left
    out: it is a ticket of an old form, which no ticket number finds."""
    directory = tickets / status
    found = [directory / n for n in sorted(names(directory)) if n.endswith(SUFFIX)]
    if status is Status.CLOSED:
        return [p for p in found if TICKET_NAME.fullmatch(p.name)]
    return found


@state_cache(DERIVED)
def listed_tickets(tickets: Path, status: Status) -> list[Path]:
    """`ticket_files` of the listing of the directory this state holds."""
    return ticket_files(tickets, status, names_in)


def ticket_path(tickets: Path, number: TicketNumber) -> Path:
    """The path of the ticket `number`, which the help of `file_ticket.py
    path` defines.

    The status directories are read one at a time, so a move of the ticket
    between two of those reads shows it at two paths or at none. Where a
    read finds not one file, a second read follows it, and only that second
    read can refuse."""
    pattern = joined_name((str(number), "*"), glob.escape)

    def found() -> list[Path]:
        return sorted(p for d in statuses(tickets) for p in d.glob(pattern))

    first = found()
    return only_ticket(tickets, number, first if len(first) == 1 else found())


def listed_ticket_path(tickets: Path, number: TicketNumber) -> Path:
    """`ticket_path`, from the listings of the status directories this
    state holds (`numbered_files`). Where those listings give not one file,
    as a move during the state's read can make them give, the path is
    `ticket_path`'s, from a read outside this state: that read is made only
    where these listings would refuse, and takes no part in a stamp."""
    listed = numbered_files(tickets).get(str(number), ())
    return listed[0] if len(listed) == 1 else ticket_path(tickets, number)


@state_cache(DERIVED)
def numbered_files(tickets: Path) -> dict[str, tuple[Path, ...]]:
    """The files of the status directories this state holds, each under the
    text before the first `_` of its name, which a ticket's number gives:
    the files the glob of `ticket_path` finds for that number, sorted."""
    found: dict[str, list[Path]] = {}
    for directory in statuses(tickets):
        for name in names_in(directory):
            head, sep, _ = name.partition("_")
            if sep and name.endswith(SUFFIX):
                found.setdefault(head, []).append(directory / name)
    return {head: tuple(sorted(paths)) for head, paths in found.items()}


def only_ticket(tickets: Path, number: TicketNumber, found: list[Path]) -> Path:
    """The one path of `found`, the files named for the ticket `number`,
    refused as the help of `file_ticket.py path` gives it where there is
    not one."""
    if len(found) == 1:
        return found[0]
    if found:
        raise Refused(mctx("ticket `{ref}` stands at more than one path: {paths}").format(
            ref=number, paths=", ".join(str(p) for p in found)))
    if is_reserved(tickets, number):
        raise Refused(mctx("ticket number `{ref}` is reserved, and no ticket has it").format(ref=number))
    raise Refused(mctx("no ticket is `{ref}`").format(ref=number))
