"""The numbering of tickets and of sessions, under the main tree's
`tickets/`: each number and each index reserved by an exclusive create of
the first free name, the files of a filing written whole under the first
free name, and the path of a ticket found by its number or by the name it
was filed under before tickets had numbers."""

import fcntl
import itertools
import os
import re
import tempfile
from collections.abc import Callable, Iterable, Iterator
from contextlib import contextmanager
from pathlib import Path

from controlled_markdown import mctx
from ticket_vocabulary import Status, ticked
from transcripts import Refused, find, forked_from

IDS = "ids"
"""The directory under `tickets/` that holds one empty file per reserved
ticket number, named by the number."""

SESSIONS = "sessions"
"""The directory under `tickets/` that holds one file per reserved session
index, named by the index, whose lines are the ids of its sessions."""

SESSION_VAR = "CLAUDE_CODE_SESSION_ID"
"""The variable of an agent's shell that holds its session's id."""

COUNT = re.compile(r"[1-9]\d*")
"""A session's index, the `<n>` of a ticket's number, or a bare number."""

TICKET_NUMBER = re.compile(rf"(?:(?P<session>{COUNT.pattern})-)?(?P<n>{COUNT.pattern})")
"""A ticket's number, `<session>-<n>`, or the bare number of a ticket filed
before a number gave the filing session's index."""


def number_parts(number: str) -> tuple[int | None, int]:
    """The session index and the `<n>` of the ticket number `number`, with
    None as the index of a bare number, which belongs to no session."""
    parts = TICKET_NUMBER.fullmatch(number)
    if parts is None:
        raise Refused(mctx("`{number}` is no ticket number").format(number=number))
    return matched_parts(parts)


def matched_parts(parts: re.Match[str]) -> tuple[int | None, int]:
    """The parts `number_parts` gives, of a match of `TICKET_NUMBER`."""
    return (int(parts["session"]) if parts["session"] else None, int(parts["n"]))


def number_order(number: str) -> tuple[int, int]:
    """The key that orders ticket numbers as the `HELP` of `file_ticket`
    gives."""
    session, n = number_parts(number)
    return (0 if session is None else session, n)


def reserve(tickets: Path, session: int) -> str:
    """Reserves the next number of a ticket of the session with index
    `session` by an exclusive create of its file under `tickets/ids/`."""
    ids = tickets / IDS
    taken = (n for p in ids.glob("*") if (number := TICKET_NUMBER.fullmatch(p.name))
             for s, n in [matched_parts(number)] if s == session)
    return write_after(ids, "", taken, lambda n: f"{session}-{n}").name


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
    with staged(directory, f"{session}\n") as tmp:
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
            f.write(f"{session}\n")


def statuses(tickets: Path) -> list[Path]:
    return [tickets / s for s in Status]


def ticket_status(path: Path) -> Status:
    """The status the ticket at `path`, a path `ticket_path` gives or one
    under the directory of a status, stands in."""
    return Status(path.parent.name)


def ticket_path(tickets: Path, ref: str) -> Path:
    """The path of the ticket numbered `ref`, or named `ref` where it was
    filed before tickets had numbers, in whichever status it stands."""
    stem = ref.removesuffix(".md")
    if not re.fullmatch(r"[\w.-]+", stem):
        raise Refused(mctx("`{ref}` is no ticket number or name").format(ref=ref))
    numbered = bool(TICKET_NUMBER.fullmatch(stem))
    pattern = f"{stem}_*.md" if numbered else f"{stem}.md"
    found = sorted(p for d in statuses(tickets) for p in d.glob(pattern))
    if len(found) == 1:
        return found[0]
    if found:
        raise Refused(mctx("ticket `{ref}` stands at more than one path: {paths}").format(
            ref=ref, paths=", ".join(str(p) for p in found)))
    if numbered and (tickets / IDS / stem).exists():
        raise Refused(mctx("ticket number `{ref}` is reserved, and no ticket has it").format(ref=ref))
    raise Refused(mctx("no ticket is `{ref}`").format(ref=ref))
