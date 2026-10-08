"""The read of the ticket tracker into the `Ticket` values the operator's
procedures read."""

import re
from datetime import UTC, datetime
from pathlib import Path

from controlled_markdown import mctx
from ticket_files import TICKET_NAME, ticket_files, ticket_name
from ticket_form import DEFAULT_PRIORITY, FRONT, front_fields, list_items, title
from ticket_log import WAIT, holder, log_lines, waited_change
from transcripts import Refused

from operations.roles import editors_of
from operations.state import LogLine, Ticket
from ticketing.times import TIME_FORM
from ticketing.vocabulary import Domain, Kind, Status


def log_time(text: str) -> float:
    """The time of a log line, which the log gives to the second."""
    try:
        return datetime.strptime(text, TIME_FORM).replace(tzinfo=UTC).timestamp()
    except ValueError:
        raise Refused(mctx("`{text}` is no log line's time").format(text=text)) from None


def log_line(m: re.Match[str]) -> LogLine:
    note = m["note"] or ""
    wait = WAIT.match(note)
    change = None if wait is None else waited_change(wait)
    return LogLine(log_time(m.group().split(" ", 1)[0]), Status(m["status"]), m["agent"],
                   m["id"], note, wait is not None and change is None,
                   None if change is None else str(change))


def read_ticket(path: Path) -> Ticket:
    name = ticket_name(path)
    text = path.read_text()
    head = re.match(FRONT, text)
    if head is None:
        raise Refused(mctx("{path} has no front matter").format(path=path))
    fields = dict(front_fields(head))
    lines = tuple(log_line(m) for m in log_lines(text))
    if not lines:
        raise Refused(mctx("{path} has no log line").format(path=path))
    editors = fields.get("editors")
    return Ticket(
        number=str(name.number), order=name.number.order, session=name.number.session,
        status=Status(path.parent.name), kind=Kind(head["kind"]), domain=Domain(name.domain),
        subject=name.subject, filer=name.agent, filed=lines[0].time,
        title=title(path, text),
        depends_on=tuple(list_items(fields["depends-on"])) if "depends-on" in fields else (),
        priority=int(fields["priority"]) if "priority" in fields else DEFAULT_PRIORITY,
        editors=None if editors is None else editors_of(list_items(editors)),
        after_merge=fields.get("after-merge"), mechanical="mechanical" in fields, log=lines, holder=holder(text), path=path)


def read_tickets(tickets: Path) -> dict[str, Ticket]:
    """Each ticket of the tracker. A ticket that moves between the listing
    and its read is read again from a new listing. A closed ticket whose
    name has no number in the form `ticket_files.TICKET_NAME` gives is one
    no number finds, so no procedure reads it."""
    for _ in range(3):
        try:
            out = {}
            for s in Status:
                for path in ticket_files(tickets, s):
                    if s is Status.CLOSED and not TICKET_NAME.fullmatch(path.name):
                        continue
                    t = read_ticket(path)
                    out[t.number] = t
            return out
        except FileNotFoundError:
            continue
    raise Refused(mctx("the tickets moved during three reads of the tracker"))
