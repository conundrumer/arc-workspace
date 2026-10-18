"""The read of the ticket tracker into the `Ticket` values the operator's
procedures read."""

import hashlib
import re
from collections.abc import Callable, Mapping
from pathlib import Path

from controlled_markdown import mctx
from ticket_files import listed_tickets, ticket_files, ticket_name
from ticket_form import FRONT, front_fields, list_items, section, section_head, title
from state_reads import DERIVED, Kept, state_cache
from ticket_log import (CLOSED_BY_LINE, DUPLICATE_OF_LINE, WAIT, Wait, held_log, holder_of,
                        line_time, log_lines, resolution_of, waited, waited_change)
from ticket_numbers import matched_number
from transcript_entries import Refused

from operations.roles import Role, editors_of
from operations.state import LogLine, Ticket, Unread
from ticketing.text import SECTIONS
from ticketing.vocabulary import TICKET_NUMBER, Domain, Kind, Status


_, MOTIVATION, _, _ = SECTIONS[Kind.CHANGE]

CITED_NUMBER = re.compile(rf"(?<![\w.:-]){TICKET_NUMBER.pattern}(?![\w:-]|\.\d)")
"""A ticket number in a ticket's prose, apart from the parts of a date, a
time or a decimal."""


def log_line(m: re.Match[str]) -> LogLine:
    note = m["note"] or ""
    wait = WAIT.match(note)
    change = None if wait is None else waited_change(wait)
    closed = CLOSED_BY_LINE.match(note)
    duplicate = DUPLICATE_OF_LINE.match(note)
    return LogLine(line_time(m), Status(m["status"]), m["agent"],
                   m["id"], note, wait is not None and waited(wait) is Wait.USER,
                   None if change is None else str(change), wait is not None, resolution_of(note),
                   None if closed is None else str(matched_number(closed)),
                   None if duplicate is None else str(matched_number(duplicate)))


def editors_field(fields: Mapping[str, str]) -> tuple[Role, ...] | None:
    """The roles the `editors` field of a ticket's front matter `fields`
    gives, or None where it has none. Raises ValueError on a name that is
    no role."""
    value = fields.get("editors")
    return None if value is None else editors_of(list_items(value))


def motivation(text: str) -> tuple[str, ...]:
    """The ticket numbers the `## Motivation` section of a ticket's `text`
    gives, in their order, none where it has no such section."""
    if section_head(text, MOTIVATION) is None:
        return ()
    return tuple(str(matched_number(m)) for m in CITED_NUMBER.finditer(section(text, MOTIVATION)))


def read_ticket(path: Path) -> Ticket:
    text = path.read_text()
    return ticket_of(path, text, log_lines(text))


@state_cache(DERIVED, kept=Kept.DISK)
def held_ticket(path: Path) -> Ticket:
    """`read_ticket` of the text and log lines `held_log` holds."""
    return ticket_of(path, *held_log(path))


def ticket_of(path: Path, text: str, found: list[re.Match[str]]) -> Ticket:
    """The ticket of the file at `path`, whose text is `text`, with the log
    lines `found`."""
    name = ticket_name(path)
    head = re.match(FRONT, text)
    if head is None:
        raise Refused(mctx("{path} has no front matter").format(path=path))
    fields = dict(front_fields(head))
    lines = tuple(log_line(m) for m in found)
    if not lines:
        raise Refused(mctx("{path} has no log line").format(path=path))
    return Ticket(
        number=str(name.number), order=name.number.order, session=name.number.session,
        status=Status(path.parent.name), kind=Kind(head["kind"]), domain=Domain(name.domain),
        subject=name.subject, filer=name.agent, filed=lines[0].time,
        title=title(path, text),
        depends_on=tuple(list_items(fields["depends-on"])) if "depends-on" in fields else (),
        motivation=motivation(text),
        editors=editors_field(fields),
        after_merge=fields.get("after-merge"), mechanical="mechanical" in fields,
        log=lines,
        holder=holder_of(found), path=path)


def read_tickets(tickets: Path) -> tuple[dict[str, Ticket], tuple[Unread, ...]]:
    """Each ticket of the tracker, and each ticket file whose read refused
    or failed other than for a move, which it leaves out of the tickets. A
    ticket that moves between the listing and its read is read again from
    a new listing: the first listing is the one this state holds, and each
    later one is read anew."""
    listing: Callable[[Path, Status], list[Path]] = listed_tickets
    for _ in range(3):
        try:
            out: dict[str, Ticket] = {}
            unread: list[Unread] = []
            for s in Status:
                for path in listing(tickets, s):
                    try:
                        t = held_ticket(path)
                    except FileNotFoundError:
                        raise
                    except (Refused, ValueError, OSError) as exc:
                        unread.append(unread_file(path, exc))
                        continue
                    out[t.number] = t
            return out, tuple(unread)
        except FileNotFoundError:
            listing = ticket_files
            continue
    raise Refused(mctx("the tickets moved during three reads of the tracker"))


def unread_file(path: Path, exc: Exception) -> Unread:
    """The file `path`, whose read failed with `exc`. A `FileNotFoundError`
    here is a move during the read. Where the file's bytes do not read,
    the digest is that of the failure's text, and where its time of last
    write does not read, that time is 0, so that its step waits on no
    write."""
    why = str(exc) or type(exc).__name__
    try:
        data = path.read_bytes()
    except FileNotFoundError:
        raise
    except OSError as failure:
        data = (str(failure) or type(failure).__name__).encode()
    try:
        modified = path.stat().st_mtime
    except FileNotFoundError:
        raise
    except OSError:
        modified = 0.0
    return Unread(path, why, hashlib.sha1(data).hexdigest(), modified)
