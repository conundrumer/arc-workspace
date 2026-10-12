"""The sessions in which no agent runs, and the main session, whose
operators act on the tickets of those sessions as on its own.

A session id is live where its main transcript, or a subagent transcript
under its `subagents/` directory, was modified within `constants.FOREGROUND_MS`, the
bound on each agent's foreground call, so an agent that runs writes its
transcript within it. An index is idle where none of the session ids
`tickets/sessions/<index>` gives is live. `file_ticket.py main --help-all`
gives the files `tickets/main` and `tickets/main-wanted`."""

import os
from dataclasses import dataclass
from pathlib import Path

from operations.constants import FOREGROUND_MS
from ticket_files import ticket_files, ticket_name
from controlled_markdown import mctx
from ticket_numbers import SESSIONS, indexes, link_new, staged
from ticketing.vocabulary import SETTLED, Status
from transcripts import Refused, project_dirs, session_directory, subagent_transcripts

MAIN = "main"

MAIN_WANTED = "main-wanted"


@dataclass(frozen=True)
class Sessions:
    """The read: `idle` holds each idle index, other than the reading
    session's, that holds a ticket outside `vocabulary.SETTLED`; `main` is whether the
    reading session is the main, and `main_live` whether a main is named
    and live."""
    idle: frozenset[int]
    main: bool
    main_live: bool

    @property
    def adopted(self) -> frozenset[int]:
        """The indexes of other sessions whose tickets the reading session's
        operators act on as on its own: the idle ones, where it is the
        main."""
        return self.idle if self.main else frozenset()


def modified(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except FileNotFoundError:
        return 0.0


def live(session: str, now: float) -> bool:
    since = now - FOREGROUND_MS / 1000
    for d in project_dirs():
        for transcript in d.glob(f"*/{session}.jsonl"):
            if modified(transcript) >= since:
                return True
            if any(modified(p) >= since for p in subagent_transcripts(session_directory(transcript))):
                return True
    return False


def read_session(path: Path) -> tuple[str, float] | None:
    """The stripped text of the session-id file at `path` with the time of
    its write, None where the file is missing or holds no text."""
    try:
        text, written = path.read_text().strip(), path.stat().st_mtime
    except FileNotFoundError:
        return None
    return (text, written) if text else None


def session_line(session: str) -> str:
    """The text a session-id file holds."""
    return f"{session}\n"


def named_main(tickets: Path) -> str | None:
    held = read_session(tickets / MAIN)
    return held[0] if held else None


def read_sessions(tickets: Path, index: int, now: float) -> Sessions:
    ids = indexes(tickets)
    held = {ticket_name(p).number.session for s in Status if s not in SETTLED
            for p in ticket_files(tickets, s)}
    idle = frozenset(i for i in held if i is not None and i != index
                     and not any(live(sid, now) for sid in ids.get(i, [])))
    main = named_main(tickets)
    return Sessions(idle=idle, main=main is not None and main in ids.get(index, []),
                    main_live=main is not None and live(main, now))


def want_main(tickets: Path, session: str) -> None:
    """Creates `MAIN_WANTED` with `session`, where no file holds that name."""
    with staged(tickets, session_line(session)) as tmp:
        link_new(tmp, tickets / MAIN_WANTED)


def main_wanted(tickets: Path) -> tuple[str, float] | None:
    """The session id `MAIN_WANTED` holds, with the time of its write, or
    None where there is no such file."""
    return read_session(tickets / MAIN_WANTED)


def name_main(tickets: Path, session: str) -> None:
    if not any(session in ids for ids in indexes(tickets).values()):
        raise Refused(mctx("no file under `tickets/{sessions}/` holds the session id `{session}`").format(
            sessions=SESSIONS, session=session))
    with staged(tickets, session_line(session)) as tmp:
        os.replace(tmp, tickets / MAIN)
    (tickets / MAIN_WANTED).unlink(missing_ok=True)
