"""The read of the ticket tracker into the `Ticket` values the operator's
procedures read."""

import hashlib
import re
import sys
from collections.abc import Callable, Mapping
from pathlib import Path

from controlled_markdown import mctx
from ticket_files import listed_tickets, ticket_files, ticket_name
from ticket_form import FRONT, VALIDATES, depends_on, front_fields, goal, list_items, section, section_head, title
from state_reads import DERIVED, Kept, state_cache
from file_reads import stat_of
from ticket_log import (CLOSED_BY_LINE, DUPLICATE_OF_LINE, WAIT, Wait, allowers, holder_of, is_allow,
                        line_time, log_lines, resolution_of, waited, waited_change)
from ticket_numbers import matched_number
from transcript_snapshots import Refused

from operations.reports import TOP_ITEM, section_items
from operations.roles import Role, editors_of
from operations.state import LogLine, Ticket, Unread
from ticketing.text import DESIGN, SECTIONS, heading
from ticketing.vocabulary import TICKET_NUMBER, Domain, Kind, Status


_, MOTIVATION, SCOPE, _ = SECTIONS[Kind.CHANGE]

AFTER_MERGE = re.compile(rf"{TOP_ITEM.pattern}After the merge")
"""The opening of the item of a change's Scope that gives its steps and
checks at or after its merge, by the `change` form of `filing_help.FORMS`."""

CITED_NUMBER = re.compile(rf"(?<![\w.:-]){TICKET_NUMBER.pattern}(?![\w:-]|\.\d)")
"""A ticket number in a ticket's prose, apart from the parts of a date, a
time or a decimal."""


def log_line(m: re.Match[str]) -> LogLine:
    note = m["note"] or ""
    wait = WAIT.match(note)
    change = None if wait is None else waited_change(wait)
    closed = CLOSED_BY_LINE.match(note)
    duplicate = DUPLICATE_OF_LINE.match(note)
    return LogLine(line_time(m), Status(m["status"]), sys.intern(m["agent"]),
                   None if m["id"] is None else sys.intern(m["id"]), note,
                   wait is not None and waited(wait) is Wait.USER,
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


def after_merge(text: str) -> str | None:
    """Each top-level item of the `## Scope` section of a ticket's `text`
    that `AFTER_MERGE` opens, with the lines nested under it, in their
    order, or None where that section holds no such item."""
    items = [i for i in section_items(text, heading(SCOPE)) if AFTER_MERGE.match(i)]
    return "\n".join(items) if items else None


COST = re.compile(r"\bCost:(?P<cost>.*)")
"""The Cost line of a change's Design, from the words after its `Cost:`."""

COST_END = re.compile(r"\boverhead\b|\bGain\b")
"""What ends the part of a Cost line that gives the change's own cost: the
change's overhead, which its budget holds already, or the line's gain."""

DOLLARS = re.compile(r"\$(?P<dollars>[0-9][0-9,]*(?:\.[0-9]+)?)")


def design_cost(text: str) -> float | None:
    """The top of the dollar range of the first Cost line of the `## Design`
    section of a ticket's `text`: the largest dollar figure after its
    `Cost:` and before `COST_END`, or None where the ticket has no such
    section, no such line, or no figure there."""
    if section_head(text, DESIGN) is None:
        return None
    line = COST.search(section(text, DESIGN))
    if line is None:
        return None
    own = COST_END.split(line["cost"], maxsplit=1)[0]
    return max((float(f.replace(",", "")) for f in DOLLARS.findall(own)), default=None)


def read_ticket(path: Path) -> Ticket:
    text = path.read_text()
    return ticket_of(path, text, log_lines(text))


@state_cache(DERIVED, kept=Kept.DISK)
def held_ticket(path: Path) -> Ticket:
    """`read_ticket` of the file at `path`, which rests on the file's stat
    (`file_reads.stat_read`), so that a call holds the `Ticket` alone."""
    stat_of(path)
    return read_ticket(path)


def ticket_of(path: Path, text: str, found: list[re.Match[str]]) -> Ticket:
    """The ticket of the file at `path`, whose text is `text`, with the log
    lines `found`."""
    name = ticket_name(path)
    head = re.match(FRONT, text)
    if head is None:
        raise Refused(mctx("{path} has no front matter").format(path=path))
    fields = dict(front_fields(head))
    lines = tuple(log_line(m) for m in found if not is_allow(m))
    if not lines:
        raise Refused(mctx("{path} has no log line").format(path=path))
    return Ticket(
        number=str(name.number), order=name.number.order, session=name.number.session,
        status=Status(path.parent.name), kind=Kind(head["kind"]), domain=Domain(name.domain),
        subject=name.subject, filer=name.agent, filed=lines[0].time,
        title=title(path, text),
        depends_on=tuple(depends_on(fields)),
        motivation=motivation(text),
        editors=editors_field(fields),
        after_merge=after_merge(text), mechanical="mechanical" in fields,
        log=lines,
        allowers=allowers(found),
        holder=holder_of(found), path=path, goal=goal(text),
        cost=design_cost(text), validates=fields.get(VALIDATES))


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
    return Unread(path, why, hashlib.sha1(data).hexdigest(), modified, name_session(path))


def name_session(path: Path) -> int | None:
    """`Unread.session` of the ticket file `path`."""
    try:
        return ticket_name(path).number.session
    except Refused:
        return None
