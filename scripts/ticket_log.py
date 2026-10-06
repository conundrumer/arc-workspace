"""A ticket's log and its transitions: the lines of its `## Log`, the
moves between the directories of its statuses, and who holds it."""

import os
import re
import time
from enum import StrEnum
from pathlib import Path

from controlled_markdown import mctx
from ticket_form import FIELD, FRONT, HEADING, LOG
from ticket_numbers import TICKET_NUMBER, ticket_path
from ticket_vocabulary import Kind, Resolution, Status, ticked
from transcripts import Refused

AGENT_ID = re.compile(r"a[0-9a-f]{16}")


TIME_FORM = "%Y-%m-%dT%H:%M:%SZ"
"""The form of a log line's time, in UTC."""


RESOLUTION_WORD = re.compile(r"[a-z]+(?:-[a-z]+)*")


class Wait(StrEnum):
    """What a ticket under `blocked` waits on, the word the note of the line
    into `blocked` opens with."""
    USER = "user"
    CHANGE = "change"


WAIT = re.compile(rf"(?:{Wait.USER}|{Wait.CHANGE} (?P<change>{TICKET_NUMBER.pattern}))(?![\w-])")
"""The opening of the note of a line into `blocked`."""


LOG_LINE = re.compile(rf"^.*? (?P<status>{'|'.join(Status)}) \[(?P<agent>[^\]\s]+)"
                      rf"(?: (?P<id>{AGENT_ID.pattern}))?\](?:: (?P<note>.*))?$", re.MULTILINE)
"""A log line, of whatever time form, as the command or a hand wrote it."""


def logged(text: str, status: Status, agent: str) -> str:
    """`text` with a `## Log` that gives its filing time."""
    return f"{text.rstrip(chr(10))}\n\n{LOG}\n{log_line(status, agent, None, 'filed')}"


def log_line(status: Status, agent: str, agent_id: str | None, note: str | None) -> str:
    """A log line, stamped now."""
    holder = f"{agent} {agent_id}" if agent_id else agent
    line = f"{time.strftime(TIME_FORM, time.gmtime())} {status} [{holder}]"
    return f"{line}: {note}\n" if note else f"{line}\n"


def read_ticket(path: Path) -> str:
    """The text of the ticket at `path`, refused where its file moved after
    `ticket_path` found it."""
    try:
        return path.read_text()
    except FileNotFoundError:
        raise Refused(mctx("{path} moved before this call could read it").format(path=path))


def check_line(status: Status, moves: bool, agent: str, agent_id: str | None,
               note: str | None) -> None:
    """Refuses a log line the ticket notes do not give."""
    if not FIELD.fullmatch(agent):
        raise Refused(mctx("`{agent}` is not kebab words").format(agent=agent))
    if agent_id is not None and not AGENT_ID.fullmatch(agent_id):
        raise Refused(mctx("`{id}` is no agent id").format(id=agent_id))
    if agent_id is None and status is Status.ASSIGNED:
        raise Refused(mctx("an `assigned` line takes your agent id in `--id`"))
    if note is not None and (not note.strip() or "\n" in note or "\r" in note):
        raise Refused(mctx("the note is not one line of text"))
    if moves and status is Status.CLOSED:
        word = RESOLUTION_WORD.match(note or "")
        if not word or word.group() not in set(Resolution):
            raise Refused(mctx("the note of a move into `closed` opens with one of {resolutions}").format(
                resolutions=ticked(Resolution)))


def check_wait(tickets: Path, note: str | None) -> None:
    """Refuses the note of a line into `blocked` that does not open with
    what the ticket waits on, or that names as the change it waits on a
    ticket that is no `change`."""
    wait = WAIT.match(note or "")
    if wait is None:
        raise Refused(mctx("the note of a move into `{blocked}` opens with `{user}` or `{change} <number>`").format(
            blocked=Status.BLOCKED, user=Wait.USER, change=Wait.CHANGE))
    if wait["change"] is None:
        return
    path = ticket_path(tickets, wait["change"])
    head = re.match(FRONT, read_ticket(path))
    if not head or head["kind"] != Kind.CHANGE:
        raise Refused(mctx("ticket `{n}` is no `change`").format(n=wait["change"]))


def log_lines(text: str) -> list[re.Match[str]]:
    """The lines of `text`'s log that have the form of a log line."""
    log = [m for m in HEADING.finditer(text) if m.group() == LOG]
    return list(LOG_LINE.finditer(text, log[-1].end())) if log else []


def holder(text: str) -> str | None:
    """The agent id of the holder of the ticket `text`: the id of the last
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
        if AGENT_ID.fullmatch(first):
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


def write_log(tickets: Path, ref: str, status: str, agent: str, source: str, agent_id: str | None,
              note: str | None) -> Path:
    """Moves ticket `ref` from `source`'s directory to `status`'s where
    they differ, then appends a log line to it, and returns its path. The
    move is a rename, and a call refuses where the ticket no longer stands
    in `source`, so of two calls that move one file, the later one is
    refused, as `mv` from `source`'s directory would be."""
    to, origin = status_of(status), status_of(source)
    path = ticket_path(tickets, ref)
    if path.parent.name != origin:
        raise Refused(mctx("ticket `{ref}` stands in `{actual}`, not `{origin}`").format(
            ref=ref, actual=path.parent.name, origin=origin))
    moves = origin != to
    check_line(to, moves, agent, agent_id, note)
    if moves and to is Status.BLOCKED:
        check_wait(tickets, note)
    text = read_ticket(path)
    headings = HEADING.findall(text)
    if not headings or headings[-1] != LOG:
        raise Refused(mctx("`{log}` is not the last section of {path}").format(log=LOG, path=path))
    if not moves and to is Status.ASSIGNED and agent_id:
        check_take(text, agent_id)
    if moves:
        target = tickets / to / path.name
        target.parent.mkdir(exist_ok=True)
        try:
            os.rename(path, target)
        except FileNotFoundError:
            raise Refused(mctx("{path} moved before this call could move it").format(path=path))
        path = target
    with path.open("a") as f:
        # A line written by hand may lack its newline.
        if not path.read_text().endswith("\n"):
            f.write("\n")
        f.write(log_line(to, agent, agent_id, note))
    return path
