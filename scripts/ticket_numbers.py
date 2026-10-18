"""The numbering of tickets and of sessions, under the main tree's
`tickets/`: a ticket's number with its parts, each number and each index
reserved by an exclusive create of the first free name, and the files of a
filing written whole under the first free name."""

import fcntl
import itertools
import os
import re
import tempfile
from collections.abc import Callable, Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from controlled_markdown import mctx
from ticket_vocabulary import ticked
from ticketing.vocabulary import COUNT, TICKET_NUMBER
from transcripts import find
from transcript_entries import forked_from
from transcript_snapshots import Refused

IDS = "ids"
"""The directory under `tickets/` that holds one empty file per reserved
ticket number, named by the number."""

SESSIONS = "sessions"
"""The directory under `tickets/` that holds one file per reserved session
index, named by the index, whose lines are the ids of its sessions."""

SESSION_VAR = "CLAUDE_CODE_SESSION_ID"
"""The variable of an agent's shell that holds its session's id."""


@dataclass(frozen=True)
class TicketNumber:
    """A ticket's number: the index of the session that filed it, None for
    a bare number, which belongs to no session, and its `<n>`."""
    session: int | None
    n: int

    def __str__(self) -> str:
        return str(self.n) if self.session is None else f"{self.session}-{self.n}"

    @property
    def order(self) -> tuple[int, int]:
        """The key that orders ticket numbers as the `RULES` of `file_ticket`
        give."""
        return (0 if self.session is None else self.session, self.n)


def matched_number(parts: re.Match[str]) -> TicketNumber:
    """The number of a match of `TICKET_NUMBER`, or of a pattern that holds
    its groups."""
    return TicketNumber(int(parts["session"]) if parts["session"] else None, int(parts["n"]))


def parsed_number(text: str) -> TicketNumber | None:
    parts = TICKET_NUMBER.fullmatch(text)
    return None if parts is None else matched_number(parts)


def ticket_number(text: str) -> TicketNumber:
    number = parsed_number(text)
    if number is None:
        raise Refused(mctx("`{number}` is no ticket number").format(number=text))
    return number


def reserve(tickets: Path, session: int) -> TicketNumber:
    """Reserves the next number of a ticket of the session with index
    `session` by an exclusive create of its file under `tickets/ids/`."""
    ids = tickets / IDS
    taken = (number.n for p in ids.glob("*")
             if (number := parsed_number(p.name)) and number.session == session)
    return ticket_number(write_after(ids, "", taken, lambda n: str(TicketNumber(session, n))).name)


def session_line(session: str) -> str:
    """The text a session-id file holds."""
    return f"{session}\n"


@contextmanager
def staged(directory: Path, text: str) -> Iterator[Path]:
    """A file under `directory` that holds `text` whole, for `link_new` to
    give its names, removed on exit."""
    directory.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=directory, prefix=".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(text)
        yield Path(tmp)
    finally:
        Path(tmp).unlink(missing_ok=True)


def link_new(source: Path, path: Path) -> bool:
    try:
        os.link(source, path)
        return True
    except FileExistsError:
        return False


def write_new(directory: Path, text: str, names: Iterable[str]) -> Path:
    """Writes `text` under `directory` at the first name `names` yields
    that no file holds, and returns its path. The file appears whole or not
    at all, and an existing file is never replaced."""
    with staged(directory, text) as tmp:
        for name in names:
            if link_new(tmp, path := directory / name):
                return path
        raise AssertionError("`names` ended")


def write_after(directory: Path, text: str, taken: Iterable[int],
                name: Callable[[int], str]) -> Path:
    """Writes `text` as `write_new` does, at the name of the first number
    after the largest of `taken`, or of the next where a file holds it."""
    start = max(taken, default=0) + 1
    return write_new(directory, text, (name(n) for n in itertools.count(start)))


def session_id() -> str:
    session = os.environ.get(SESSION_VAR)
    if not session:
        raise Refused(mctx("the shell holds no session id in `{var}`").format(var=SESSION_VAR))
    return session


def indexes(tickets: Path) -> dict[int, list[str]]:
    directory = tickets / SESSIONS
    if not directory.is_dir():
        return {}
    return {int(p.name): p.read_text().split() for p in directory.iterdir() if COUNT.fullmatch(p.name)}


def indexed(reserved: dict[int, list[str]], session: str) -> int | None:
    held = [i for i, ids in reserved.items() if session in ids]
    if len(held) > 1:
        raise Refused(mctx("session `{session}` has more than one index: {held}").format(
            session=session, held=ticked(str(i) for i in sorted(held))))
    return held[0] if held else None


def session_index(tickets: Path, session: str) -> int:
    """The index of the session with id `session`, reserved where it has
    none: the index of the session it was forked from, with `session`
    added to that index's file, or else the next index, by a file created
    whole that holds `session`. Where another call created the file of the
    index tried first, the call looks again for an index of `session`
    before it tries the next."""
    found = indexed(indexes(tickets), session)
    if found is not None:
        return found
    parent = forked_from(find(session))
    if parent is not None:
        index = session_index(tickets, parent)
        add_session(tickets / SESSIONS / str(index), session)
        return index
    directory = tickets / SESSIONS
    with staged(directory, session_line(session)) as tmp:
        while True:
            reserved = indexes(tickets)
            found = indexed(reserved, session)
            if found is not None:
                return found
            n = max(reserved, default=0) + 1
            if link_new(tmp, directory / str(n)):
                return n


def add_session(path: Path, session: str) -> None:
    with path.open("a") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        if session not in path.read_text().split():
            f.write(session_line(session))


def is_reserved(tickets: Path, number: TicketNumber) -> bool:
    return (tickets / IDS / str(number)).exists()
