"""The sessions in which no agent runs, and the main session, whose
operators act on the tickets of those sessions as on its own, and alone
make the launches `operations.main_session.main_only` gives.

A session id is live where its main transcript, or a subagent transcript
under its `subagents/` directory, was modified within `constants.FOREGROUND_MS`, the
bound on each agent's foreground call, so an agent that runs writes its
transcript within it. An index is idle where none of the session ids
`tickets/sessions/<index>` gives is live. `file_ticket.py main --help-all`
gives the files `tickets/main` and `tickets/main-wanted`."""

import os
from pathlib import Path

from operations.constants import FOREGROUND_MS
from operations.state import SessionsRead
from ticket_files import listed_tickets, ticket_name
from controlled_markdown import mctx
from ticket_numbers import SESSIONS, indexes, link_new, session_index, session_line, staged
from ticketing.vocabulary import SETTLED, Status
from file_reads import state_stat
from process_readings import harness_sessions as harness_processes
from transcripts import mains_named, session_directory, session_subagents
from transcript_snapshots import Refused, SUBJECT_FAULTS

MAIN = "main"

MAIN_WANTED = "main-wanted"


def modified(path: Path) -> float:
    found = state_stat(str(path))
    return 0.0 if found is None else found.mtime


def live(session: str, now: float) -> bool:
    since = now - FOREGROUND_MS / 1000
    for transcript in mains_named(session):
        if modified(transcript) >= since:
            return True
        if any(modified(p) >= since for p in session_subagents(session_directory(transcript))):
            return True
    return False


def running(reader: str) -> frozenset[str] | None:
    """The ids of the sessions that run, by the process the harness's file
    on each gives, which a session that waits on the user keeps. None where
    `harness_processes` gives None, or `reader` is not among those
    sessions."""
    held = harness_processes()
    if held is None or reader not in held.values():
        return None
    return frozenset(held.values())


def read_session(path: Path) -> tuple[str, float] | None:
    try:
        text, written = path.read_text().strip(), path.stat().st_mtime
    except FileNotFoundError:
        return None
    return (text, written) if text else None


def named_main(tickets: Path) -> str | None:
    held = read_session(tickets / MAIN)
    return held[0] if held else None


def read_sessions(tickets: Path, index: int, session: str, now: float,
                  undecided: list[str] | None = None, me: str = "") -> SessionsRead:
    if undecided is None:
        undecided = []
    ids = indexes(tickets)
    held: set[int | None] = set()
    for status in Status:
        if status in SETTLED:
            continue
        for path in listed_tickets(tickets, status):
            try:
                held.add(ticket_name(path).number.session)
            except SUBJECT_FAULTS as exc:
                undecided.append(mctx("{run}: ticket {path} cannot be read ({error}), "
                                      "so its session is not counted as holding tickets").format(
                                          run=me, path=path, error=exc))
    known = {*ids, *(i for i in held if i is not None)}
    ended = frozenset(i for i in known if i != index
                      and not any(live(sid, now) for sid in ids.get(i, [])))
    idle = frozenset(i for i in held if i in ended)
    main = named_main(tickets)
    return SessionsRead(idle=idle, ended=ended, main=main == session,
                        main_live=main is not None and live(main, now),
                        main_wanted=main_wanted(tickets))


def create_session_file(path: Path, session: str) -> bool:
    """Creates `path` with `session`, where no file holds that name, and
    gives whether this call created it."""
    with staged(path.parent, session_line(session)) as tmp:
        return link_new(tmp, path)


def replace_session_file(path: Path, session: str) -> None:
    with staged(path.parent, session_line(session)) as tmp:
        os.replace(tmp, path)


def want_main(tickets: Path, session: str) -> None:
    create_session_file(tickets / MAIN_WANTED, session)


def main_wanted(tickets: Path) -> tuple[str, float] | None:
    """The session id `MAIN_WANTED` holds, with the time of its write, as `read_session` reads it."""
    return read_session(tickets / MAIN_WANTED)


def take_main(tickets: Path, session: str, sessions_running: frozenset[str] | None) -> str | None:
    """`file_ticket.py main --help-all` gives the rule. Of two sessions
    that find no main at once, the first to create `MAIN` wins. Where
    `sessions_running`, as `running` gives it, is None, it writes
    nothing."""
    held = named_main(tickets)
    if sessions_running is None or (held is not None and held in sessions_running):
        return held
    session_index(tickets, session)
    if held is None:
        create_session_file(tickets / MAIN, session)
    else:
        replace_session_file(tickets / MAIN, session)
    (tickets / MAIN_WANTED).unlink(missing_ok=True)
    return named_main(tickets)


def name_main(tickets: Path, session: str) -> None:
    if not any(session in ids for ids in indexes(tickets).values()):
        raise Refused(mctx("no file under `tickets/{sessions}/` holds the session id `{session}`").format(
            sessions=SESSIONS, session=session))
    replace_session_file(tickets / MAIN, session)
    (tickets / MAIN_WANTED).unlink(missing_ok=True)
