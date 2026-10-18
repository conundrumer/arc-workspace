"""A ticket's log and its transitions: the lines of its `## Log`, the
moves between the directories of its statuses, and who holds it."""

import os
import re
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path

from controlled_markdown import mctx
from engine.memo import write_whole
from ticket_files import FIELD, TicketName, ticket_files, ticket_name, ticket_path, ticket_status
from ticket_form import (HEADING, LOG, TITLE_MARK, VALIDATES, section, section_head, ticket_kind,
                         title, without_section)
from ticket_numbers import TICKET_NUMBER, TicketNumber, matched_number, reserve, ticket_number, write_new
from ticket_vocabulary import ticked
from operations.roles import AGENT_ID as AGENT_ID_FORM
from ticketing.text import VALIDATION, heading
from ticketing.times import stamp_time, utc_stamp
from ticketing.vocabulary import WAIT_STATUSES, Domain, Kind, Note, Resolution, Status, Verdict, Wait, note_opening
from file_reads import file_text, stat_of
from state_reads import state_cache
from transcript_entries import Refused

AGENT_ID = re.compile(AGENT_ID_FORM)

SESSION_ID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
"""The form of the session id `CLAUDE_CODE_SESSION_ID` holds."""

HOLDER_ID = re.compile(rf"{AGENT_ID.pattern}|{SESSION_ID.pattern}")
"""The form of a holder id: an agent id, or the session id of a session
that holds a ticket itself."""


RESOLUTION = note_opening(*Resolution)


CLOSED_BY = "{fixed} by {change} {number}: {note}"
"""The note of the line that closes a ticket that waits on a change closed
with `fixed`, with that change's number and note."""

CLOSED_BY_LINE = re.compile(CLOSED_BY.format(fixed=Resolution.FIXED, change=Wait.CHANGE,
                                             number=f"(?P<change>{TICKET_NUMBER.pattern})", note=""))
"""The opening of a note of the form `CLOSED_BY`, whose literal words hold
no regular expression syntax."""

DUPLICATE_OF = "{duplicate} of {number}: {note}"
"""The note of the line that closes a ticket with `duplicate`, with the
number of the ticket it duplicates."""

DUPLICATE_OF_LINE = re.compile(DUPLICATE_OF.format(
    duplicate=Resolution.DUPLICATE, number=f"(?P<number>{TICKET_NUMBER.pattern})", note=""))
"""The opening of a note of the form `DUPLICATE_OF`."""

UNBLOCKED_BY = "{change} {number} closed {resolution}"
"""The note of the line that moves into `open` a ticket that waits on a
change closed with another resolution, with that change's number and
resolution."""

WAITS_ON_NEXT = "{change} {next}: {change} {number} closed {resolution}"
"""The note of the line that keeps under `waiting` a ticket that waits on
a change closed with `fixed`, where another change outside
`tickets/closed/` serves it: `next`, the number of the change it then waits on, and the closed
change's number and resolution."""

VALIDATED = f"{Resolution.FIXED}: {Verdict.VALIDATED}:"
"""The opening of the note of a line into `closed` that states that the
check of a `validation` ticket's `Validation` section held."""

VALIDATION_TITLE = "{request} {number}: {title}"
"""The title of the `validation` ticket of the request `number`, with
that request's title."""

VALIDATES_NOTE = "{filed}: validates {request} {number}"
"""The note of the line that files the `validation` ticket of the
request `number`."""


class Moved(Refused):
    """A refusal of a call whose ticket another call moved first."""


WAIT = note_opening(Wait.USER, rf"{Wait.CHANGE} (?P<change>{TICKET_NUMBER.pattern})")
"""The opening of the note of a line into `blocked` or `waiting`."""


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


def logged(text: str, status: Status, agent: str, note: str) -> str:
    """`text` with a `## Log` that gives its filing time, with the note
    `note`, which opens with `Note.FILED`."""
    return f"{text.rstrip(chr(10))}\n\n{LOG}\n{log_line(status, agent, None, note)}"


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


@state_cache(stat_of)
def held_log(path: Path) -> tuple[str, list[re.Match[str]]]:
    """The text of the ticket at `path`, with its log lines, read and
    parsed again only where the file's stat changed."""
    text = file_text(path)
    return text, log_lines(text)


def resolution_of(note: str | None) -> Resolution | None:
    """The resolution `note` opens with, None where it opens with none."""
    opening = RESOLUTION.match(note or "")
    return Resolution(opening.group()) if opening else None


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
    if (moves and status is Status.CLOSED and resolution_of(note) is Resolution.DUPLICATE
            and not DUPLICATE_OF_LINE.match(note or "")):
        raise Refused(mctx("the note of a move into `closed` with `{duplicate}` has the form "
                           "`{form}`").format(duplicate=Resolution.DUPLICATE, form=DUPLICATE_OF.format(
                               duplicate=Resolution.DUPLICATE, number="<number>", note="<note>")))


def check_wait(tickets: Path, status: Status, note: str | None) -> None:
    """Refuses the note of a line into `status` that does not open with
    the wait of that status, or that names as the change it waits on a
    ticket that is no `change`."""
    wait = WAIT.match(note or "")
    if wait is None or waited(wait).status is not status:
        raise Refused(mctx("the note of a move into `{blocked}` opens with `{user}`, and "
                           "the note of a move into `{waiting}` with `{change} <number>`").format(
            blocked=Status.BLOCKED, waiting=Status.WAITING, user=Wait.USER, change=Wait.CHANGE))
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


def holder(text: str) -> str | None:
    """The holder id of the holder of the ticket `text`: the id of the last
    `assigned` line that gives one, in its bracket or, in a line written
    before the bracket held it, as its note's first word, among the lines
    of the log's final run of `assigned` lines. None where none of them
    gives one."""
    return holder_of(log_lines(text))


def holder_of(lines: list[re.Match[str]]) -> str | None:
    """`holder` of the ticket whose log lines are `lines`."""
    for line in reversed(lines):
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
    if moves and status in WAIT_STATUSES:
        check_wait(tickets, status, note)
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
    ticket the call names first, with the path of each `validation` ticket
    it filed after the path of its request, and each ticket that waits on a change it
    closed whose move was refused, with its path and the reason."""
    moved: list[Path] = field(default_factory=list[Path])
    refused: list[tuple[Path, str]] = field(default_factory=list[tuple[Path, str]])

    def add(self, other: "Moves") -> None:
        self.moved += other.moved
        self.refused += other.refused


class Close(Enum):
    """What a line into `closed` does beyond the move, as
    `ticket_log_command.LOG_RULES` gives."""
    UNBLOCKS = auto()
    """It closes a `change`, and `unblock` moves the tickets that wait on it."""
    FILES_VALIDATION = auto()
    """It closes `fixed` a `request` that holds a `Validation` section, and
    `file_validation` moves that section into a new `validation` ticket."""
    DEFERS = auto()
    """It closes `fixed` a `validation` ticket, which moves into `deferred`
    in place of `closed`."""


def close_of(path: Path, status: Status, source: Status, note: str | None) -> Close | None:
    """What a line into `status` from `source` with `note` on the ticket at
    `path` does beyond the move, None where it does nothing more."""
    if status is not Status.CLOSED or source is Status.CLOSED:
        return None
    text = read_ticket(path)
    kind = ticket_kind(text)
    if kind is Kind.CHANGE:
        return Close.UNBLOCKS
    if resolution_of(note) is not Resolution.FIXED or (note or "").startswith(VALIDATED):
        return None
    if kind is Kind.VALIDATION:
        return Close.DEFERS
    if kind is Kind.REQUEST and section_head(text, VALIDATION) is not None:
        return Close.FILES_VALIDATION
    return None


def log_moves(tickets: Path, number: TicketNumber, status: Status, agent: str, source: Status,
              agent_id: str | None, note: str | None) -> Moves:
    """Writes the log line as `write_log` does, refused as it refuses, and
    returns the ticket's path, followed by what the line does beyond the
    move (`Close`): the path of the `validation` ticket `file_validation`
    files, or what `unblock` returns."""
    path = ticket_path(tickets, number)
    close = close_of(path, status, source, note)
    if close is Close.DEFERS:
        status = Status.DEFERRED
    if close is Close.FILES_VALIDATION and number.session is None:
        raise Refused(mctx("request `{number}` has a bare number, so its `validation` ticket "
                           "has no session to take its number from").format(number=number))
    moves = Moves([write_log(tickets, path, number, status, agent, source, agent_id, note)])
    match close:
        case None | Close.DEFERS:
            pass
        case Close.FILES_VALIDATION:
            moves.moved.append(file_validation(tickets, moves.moved[0], number, agent))
        case Close.UNBLOCKS:
            resolution = resolution_of(note)
            # `check_line` refuses a move into `closed` whose note opens with no resolution.
            assert note is not None and resolution is not None
            moves.add(unblock(tickets, number, agent, agent_id, resolution, note))
    return moves


def file_validation(tickets: Path, path: Path, request: TicketNumber, agent: str) -> Path:
    """Moves the `Validation` section of the closed request `request`, at
    `path`, into a new `validation` ticket under `tickets/deferred/`, filed
    by `agent`, and returns that ticket's path. The ticket is written
    before the section is cut, so a call that stops between them leaves
    the check in both."""
    # `close_of` gives `FILES_VALIDATION` only to a request with a session's number.
    assert request.session is not None
    text = read_ticket(path)
    named = VALIDATION_TITLE.format(request=Kind.REQUEST, number=request, title=title(path, text))
    note = VALIDATES_NOTE.format(filed=Note.FILED, request=Kind.REQUEST, number=request)
    validation = (f"---\nkind: {Kind.VALIDATION}\n{VALIDATES}: {request}\n---\n"
                  f"{TITLE_MARK}{named}\n\n{heading(VALIDATION)}\n{section(text, VALIDATION)}\n\n"
                  f"{LOG}\n{log_line(Status.DEFERRED, agent, None, note)}")
    number = reserve(tickets, request.session)
    name = TicketName(number, Domain.TICKET, str(request), agent).file_name
    filed = write_new(tickets / Status.DEFERRED, validation, [name])
    write_whole(path, without_section(text, VALIDATION).encode())
    return filed


def unblock(tickets: Path, change: TicketNumber, agent: str, agent_id: str | None,
            resolution: Resolution, note: str) -> Moves:
    """Carries out, for the change `change` closed with `resolution` and `note`,
    the moves of the tickets that wait on it that `ticket_log_command.LOG_RULES`
    gives, and returns what it did. Each line is as `log_moves` writes it."""
    moves = Moves()
    opened = UNBLOCKED_BY.format(change=Wait.CHANGE, number=change, resolution=resolution)
    closed = CLOSED_BY.format(fixed=resolution, change=Wait.CHANGE, number=change, note=note)
    served: dict[TicketNumber, list[TicketNumber]] | None = None
    for path in ticket_files(tickets, Status.WAITING):
        try:
            if waits_on(read_ticket(path)) == change:
                if resolution is Resolution.FIXED and not is_change(path):
                    if served is None:
                        served = served_by(tickets, change)
                    following = served.get(ticket_name(path).number)
                    if following:
                        to, line = Status.WAITING, WAITS_ON_NEXT.format(
                            change=Wait.CHANGE, next=min(following, key=lambda n: n.order),
                            number=change, resolution=resolution)
                    else:
                        to, line = Status.CLOSED, closed
                else:
                    to, line = Status.OPEN, opened
                moves.add(log_moves(tickets, ticket_name(path).number, to, agent, Status.WAITING,
                                    agent_id, line))
        except Moved:
            continue
        except Refused as e:
            moves.refused.append((path, str(e)))
    return moves


def served_by(tickets: Path, change: TicketNumber) -> dict[TicketNumber, list[TicketNumber]]:
    """The changes outside `tickets/closed/`, other than `change`, whose
    `Motivation` gives a ticket's number, by that number. A change whose
    file moves while this reads it is left out."""
    from ticket_reads import motivation

    served: dict[TicketNumber, list[TicketNumber]] = {}
    for status in Status:
        if status is Status.CLOSED:
            continue
        for path in ticket_files(tickets, status):
            number = ticket_name(path).number
            try:
                text = read_ticket(path)
            except Moved:
                continue
            if number == change or ticket_kind(text) is not Kind.CHANGE:
                continue
            for cited in motivation(text):
                served.setdefault(ticket_number(cited), []).append(number)
    return served


def line_time(line: re.Match[str]) -> float:
    """The time of a match of `LOG_LINE`."""
    text = line.group().split(" ", 1)[0]
    try:
        return stamp_time(text)
    except ValueError:
        raise Refused(mctx("`{text}` is no log line's time").format(text=text)) from None
