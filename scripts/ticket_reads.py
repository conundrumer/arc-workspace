"""The read of the ticket tracker into the `Ticket` values the operator's
procedures read."""

import re
from datetime import UTC, datetime
from pathlib import Path

from controlled_markdown import mctx
from ticket_files import TICKET_NAME, ticket_files, ticket_name
from ticket_form import DEFAULT_PRIORITY, FRONT, title
from ticket_log import TIME_FORM, holder, log_lines
from transcripts import Refused

from operating.roles import editors_of
from operating.state import LogLine, Ticket
from ticketing.vocabulary import Domain, Kind, Status


def log_time(text: str) -> float:
    """The time of a log line, which the log gives to the second."""
    try:
        return datetime.strptime(text, TIME_FORM).replace(tzinfo=UTC).timestamp()
    except ValueError:
        raise Refused(mctx("`{text}` is no log line's time").format(text=text)) from None


def read_ticket(path: Path) -> Ticket:
    name = ticket_name(path)
    text = path.read_text()
    head = re.match(FRONT, text)
    if head is None:
        raise Refused(mctx("{path} has no front matter").format(path=path))
    fields = dict(line.split(": ", 1) for line in head.group("fields").splitlines())
    lines = tuple(LogLine(log_time(m.group().split(" ", 1)[0]), Status(m["status"]),
                          m["agent"], m["id"], m["note"] or "") for m in log_lines(text))
    editors = fields.get("editors")
    return Ticket(
        number=str(name.number), order=name.number.order, session=name.number.session,
        status=Status(path.parent.name), kind=Kind(head["kind"]), domain=Domain(name.domain),
        subject=name.subject, filer=name.agent, filed=lines[0].time if lines else 0.0,
        title=title(path, text),
        depends_on=tuple(d.strip() for d in fields.get("depends-on", "").split(",") if d.strip()),
        priority=int(fields["priority"]) if "priority" in fields else DEFAULT_PRIORITY,
        editors=None if editors is None else editors_of(editors),
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
