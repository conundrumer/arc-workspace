"""A ticket's log and its transitions: the lines of its `## Log`, the
moves between the directories of its statuses, and who holds it."""

import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path

from controlled_markdown import mctx
from ticket_files import FIELD, ticket_files, ticket_name, ticket_path, ticket_status
from ticket_form import HEADING, LOG, ticket_kind
from ticket_numbers import TICKET_NUMBER, TicketNumber, matched_number
from ticket_vocabulary import ticked
from operations.roles import AGENT_ID as AGENT_ID_FORM
from ticketing.times import utc_stamp
from ticketing.vocabulary import Kind, Note, Resolution, Status, Wait
from transcripts import Refused

AGENT_ID = re.compile(AGENT_ID_FORM)

SESSION_ID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
"""The form of the session id `CLAUDE_CODE_SESSION_ID` holds."""

HOLDER_ID = re.compile(rf"{AGENT_ID.pattern}|{SESSION_ID.pattern}")
"""The form of a holder id: an agent id, or the session id of a session
that holds a ticket itself."""


RESOLUTION_WORD = re.compile(r"[a-z]+(?:-[a-z]+)*")


CLOSED_BY = "{fixed} by {change} {number}: {note}"
"""The note of the line that closes a ticket that waits on a change closed
with `fixed`, with that change's number and note."""

UNBLOCKED_BY = "{change} {number} closed {resolution}"
"""The note of the line that moves into `open` a ticket that waits on a
change closed with another resolution, with that change's number and
resolution."""

class Moved(Refused):
    """A refusal of a call whose ticket another call moved first."""


VALIDATING = f"{Wait.VALIDATION} {{note}}"
"""The note of the line that leaves under `blocked`, waiting on
validation, a `request` that a line with the note `note` would close with
`fixed`."""


WAIT = re.compile(rf"(?:{Wait.USER}|{Wait.VALIDATION}|{Wait.CHANGE} (?P<change>{TICKET_NUMBER.pattern}))"
                  rf"(?![\w-])")
"""The opening of the note of a line into `blocked`."""


def waited_change(wait: re.Match[str]) -> TicketNumber | None:
    """The number of the change a match of `WAIT` gives, None where it
    gives another wait."""
    return None if wait["change"] is None else matched_number(wait)


def waited(wait: re.Match[str]) -> Wait:
    """What a match of `WAIT` gives the ticket as waiting on."""
    return Wait.CHANGE if wait["change"] is not None else Wait(wait.group())


LOG_LINE = re.compile(rf"^.*? (?P<status>{'|'.join(Status)}) \[(?P<agent>[^\]\s]+)"
                      rf"(?: (?P<id>{HOLDER_ID.pattern}))?\](?:: (?P<note>.*))?$", re.MULTILINE)
"""A log line, of whatever time form, as the command or a hand wrote it."""


def logged(text: str, status: Status, agent: str) -> str:
    """`text` with a `## Log` that gives its filing time."""
    return f"{text.rstrip(chr(10))}\n\n{LOG}\n{log_line(status, agent, None, Note.FILED)}"


def log_line(status: Status, agent: str, agent_id: str | None, note: str | None) -> str:
    """A log line, stamped now."""
    holder = f"{agent} {agent_id}" if agent_id else agent
    line = f"{utc_stamp(time.time())} {status} [{holder}]"
    return f"{line}: {note}\n" if note else f"{line}\n"


def read_ticket(path: Path) -> str:
    """The text of the ticket at `path`, refused where its file moved after
    `ticket_path` found it."""
    try:
        return path.read_text()
    except FileNotFoundError:
        raise Moved(mctx("{path} moved before this call could read it").format(path=path))


def resolution_of(note: str | None) -> Resolution | None:
    """The resolution `note` opens with, None where it opens with none."""
    word = RESOLUTION_WORD.match(note or "")
    return Resolution(word.group()) if word and word.group() in set(Resolution) else None


def is_change(path: Path) -> bool:
    """Whether the ticket at `path` is a `change`."""
    return ticket_kind(read_ticket(path)) is Kind.CHANGE


def check_line(status: Status, moves: bool, agent: str, agent_id: str | None,
               note: str | None) -> None:
    """Refuses a log line the ticket notes do not give."""
    if not FIELD.fullmatch(agent):
        raise Refused(mctx("`{agent}` is not kebab words").format(agent=agent))
    if agent_id is not None and not HOLDER_ID.fullmatch(agent_id):
        raise Refused(mctx("`{id}` is no agent id and no session id").format(id=agent_id))
    if agent_id is None and moves and status is Status.ASSIGNED:
        raise Refused(mctx("an `assigned` line takes your agent id, or the session id of a session "
                           "that takes the ticket itself, in `--id`"))
    if note is not None and (not note.strip() or "\n" in note or "\r" in note):
        raise Refused(mctx("the note is not one line of text"))
    if moves and status is Status.CLOSED and resolution_of(note) is None:
        raise Refused(mctx("the note of a move into `closed` opens with one of {resolutions}").format(
            resolutions=ticked(Resolution)))


def check_wait(tickets: Path, note: str | None) -> None:
    """Refuses the note of a line into `blocked` that does not open with
    what the ticket waits on, or that names as the change it waits on a
    ticket that is no `change`."""
    wait = WAIT.match(note or "")
    if wait is None:
        raise Refused(mctx("the note of a move into `{blocked}` opens with `{user}`, `{validation}` or "
                           "`{change} <number>`").format(
            blocked=Status.BLOCKED, user=Wait.USER, validation=Wait.VALIDATION, change=Wait.CHANGE))
    change = waited_change(wait)
    if change is None:
        return
    if not is_change(ticket_path(tickets, change)):
        raise Refused(mctx("ticket `{n}` is no `change`").format(n=change))


def log_lines(text: str) -> list[re.Match[str]]:
    """The lines of `text`'s log that have the form of a log line."""
    log = [m for m in HEADING.finditer(text) if m.group() == LOG]
    return list(LOG_LINE.finditer(text, log[-1].end())) if log else []


def current_wait(text: str) -> re.Match[str] | None:
    """The wait the last line of the ticket `text`'s log whose note opens
    with a wait gives, None where no line's note opens with one."""
    for line in reversed(log_lines(text)):
        if wait := WAIT.match(line["note"] or ""):
            return wait
    return None


def waits_on(text: str) -> TicketNumber | None:
    """The number of the change the ticket `text` waits on, None where it
    waits on no change."""
    wait = current_wait(text)
    return None if wait is None else waited_change(wait)


def awaits_validation(path: Path, status: Status, source: Status, note: str | None) -> bool:
    """Whether a line from `source` to `status` with `note` would close
    with `fixed` the ticket at `path` where it is a `request` that does
    not stand under `blocked` waiting on validation."""
    if status is not Status.CLOSED or source is Status.CLOSED or resolution_of(note) is not Resolution.FIXED:
        return False
    text = read_ticket(path)
    if ticket_kind(text) is not Kind.REQUEST:
        return False
    wait = current_wait(text)
    return not (source is Status.BLOCKED and wait is not None and waited(wait) is Wait.VALIDATION)


def holder(text: str) -> str | None:
    """The holder id of the holder of the ticket `text`: the id of the last
    `assigned` line that gives one, in its bracket or, in a line written
    before the bracket held it, as its note's first word, among the lines
    of the log's final run of `assigned` lines. None where none of them
    gives one."""
    for line in reversed(log_lines(text)):
        if line["status"] != Status.ASSIGNED:
            break
        if line["id"]:
            return line["id"]
        first = (line["note"] or "").split(" ", 1)[0].rstrip(";,.:")
        if HOLDER_ID.fullmatch(first):
            return first
    return None


def check_take(text: str, agent_id: str) -> None:
    """Refuses an `assigned` line that gives `agent_id` on a ticket already
    under `assigned`, unless `agent_id` holds it: such a line on a ticket
    another agent took is the move that fails."""
    held = holder(text)
    if held != agent_id:
        raise Refused(mctx("the ticket stands under `assigned`, held by {holder}").format(
            holder=f"`{held}`" if held else "no agent"))


def status_of(word: str) -> Status:
    try:
        return Status(word)
    except ValueError:
        raise Refused(mctx("`{status}` is no status: the statuses are {statuses}").format(
            status=word, statuses=ticked(Status)))


def check_status(path: Path, number: TicketNumber, status: Status) -> None:
    actual = ticket_status(path)
    if actual is not status:
        raise Moved(mctx("ticket `{ref}` stands in `{actual}`, not `{status}`").format(
            ref=number, actual=actual, status=status))


def write_log(tickets: Path, path: Path, number: TicketNumber, status: Status, agent: str,
              source: Status, agent_id: str | None, note: str | None) -> Path:
    """Moves ticket `number`, at `path`, from `source`'s directory to `status`'s where
    they differ, then appends a log line to it, and returns its path. The
    move is a rename, and a call refuses where the ticket no longer stands
    in `source`, so of two calls that move one file, the later one is
    refused, as `mv` from `source`'s directory would be."""
    check_status(path, number, source)
    moves = source is not status
    check_line(status, moves, agent, agent_id, note)
    if moves and status is Status.BLOCKED:
        check_wait(tickets, note)
    text = read_ticket(path)
    headings = HEADING.findall(text)
    if not headings or headings[-1] != LOG:
        raise Refused(mctx("`{log}` is not the last section of {path}").format(log=LOG, path=path))
    if not moves and status is Status.ASSIGNED and agent_id:
        check_take(text, agent_id)
    if moves:
        target = tickets / status / path.name
        target.parent.mkdir(exist_ok=True)
        try:
            os.rename(path, target)
        except FileNotFoundError:
            raise Moved(mctx("{path} moved before this call could move it").format(path=path))
        path = target
    with path.open("a") as f:
        # A line written by hand may lack its newline.
        if not path.read_text().endswith("\n"):
            f.write("\n")
        f.write(log_line(status, agent, agent_id, note))
    return path


@dataclass
class Moves:
    """What a call of `log_moves` did: the paths it moved tickets to, the
    ticket the call names first, and each ticket that waits on a change it
    closed whose move was refused, with its path and the reason."""
    moved: list[Path] = field(default_factory=list[Path])
    refused: list[tuple[Path, str]] = field(default_factory=list[tuple[Path, str]])

    def add(self, other: "Moves") -> None:
        self.moved += other.moved
        self.refused += other.refused


def log_moves(tickets: Path, number: TicketNumber, status: Status, agent: str, source: Status,
              agent_id: str | None, note: str | None) -> Moves:
    """Writes the log line as `write_log` does, refused as it refuses, and
    returns the ticket's path, followed, where the line moves a `change`
    into `closed`, by what `unblock` returns for it. A line that
    `awaits_validation` holds for is written into `blocked` instead, with
    the note `VALIDATING` gives."""
    path = ticket_path(tickets, number)
    if awaits_validation(path, status, source, note):
        status, note = Status.BLOCKED, VALIDATING.format(note=note)
    closes = status is Status.CLOSED and source is not Status.CLOSED and is_change(path)
    moves = Moves([write_log(tickets, path, number, status, agent, source, agent_id, note)])
    if not closes:
        return moves
    resolution = resolution_of(note)
    # `check_line` refuses a move into `closed` whose note opens with no resolution.
    assert note is not None and resolution is not None
    moves.add(unblock(tickets, number, agent, agent_id, resolution, note))
    return moves


def unblock(tickets: Path, change: TicketNumber, agent: str, agent_id: str | None,
            resolution: Resolution, note: str) -> Moves:
    """Carries out, for the change `change` closed with `resolution` and `note`,
    the moves of the tickets that wait on it that `file_ticket.LOG_RULES`
    gives, and returns what it did. Each line is as `log_moves` writes it."""
    moves = Moves()
    opened = UNBLOCKED_BY.format(change=Wait.CHANGE, number=change, resolution=resolution)
    closed = CLOSED_BY.format(fixed=resolution, change=Wait.CHANGE, number=change, note=note)
    for path in ticket_files(tickets, Status.BLOCKED):
        try:
            if waits_on(read_ticket(path)) == change:
                if resolution is Resolution.FIXED and not is_change(path):
                    to, line = Status.CLOSED, closed
                else:
                    to, line = Status.OPEN, opened
                moves.add(log_moves(tickets, ticket_name(path).number, to, agent, Status.BLOCKED,
                                    agent_id, line))
        except Moved:
            continue
        except Refused as e:
            moves.refused.append((path, str(e)))
    return moves
