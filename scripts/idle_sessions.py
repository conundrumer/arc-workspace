"""The sessions in which no agent runs, and the main session, whose
operators act on the tickets of those sessions as on its own.

A session id is live where its main transcript, or a subagent transcript
under its `subagents/` directory, was modified within `constants.FOREGROUND_MS`, the
bound on each agent's foreground call, so an agent that runs writes its
transcript within it. An index is idle where none of the session ids
`tickets/sessions/<index>` gives is live. `file_ticket.py main --help-all`
gives the files `tickets/main` and `tickets/main-wanted`."""

import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

from operations.constants import FOREGROUND_MS
from ticket_files import listed_tickets, ticket_name
from controlled_markdown import mctx
from ticket_numbers import SESSIONS, indexes, link_new, session_index, session_line, staged
from ticketing.vocabulary import SETTLED, Status
from file_reads import stat_read
from transcripts import mains_named, project_dirs, session_directory, session_subagents
from transcript_entries import Refused

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
    found = stat_read(path)
    return 0.0 if found is None else found.mtime


def live(session: str, now: float) -> bool:
    since = now - FOREGROUND_MS / 1000
    for transcript in mains_named(session):
        if modified(transcript) >= since:
            return True
        if any(modified(p) >= since for p in session_subagents(session_directory(transcript))):
            return True
    return False


HARNESS_SESSIONS = "sessions"
"""The directory, beside `projects/` in the harness's config directory, in
which the harness keeps a file `<pid>.json` for each running session, with
its `sessionId`, its `pid`, and its `procStart`, the start of that process
as `ps -o lstart=` prints it in UTC."""


def running(reader: str) -> frozenset[str] | None:
    """The ids of the sessions that run, by the process the harness's file
    on each gives, which a session that waits on the user keeps. A process
    counts only where it started when the file gives, so a `pid` another
    process has taken since does not count. None where no such file gives
    `reader`, which runs, or one of them is not readable or gives no
    `procStart`, as then those files are not read."""
    out: set[str] = set()
    for d in project_dirs():
        for path in (d.parent / HARNESS_SESSIONS).glob("*.json"):
            try:
                entry = json.loads(path.read_text())
            except FileNotFoundError:
                continue
            except json.JSONDecodeError:
                return None
            if "procStart" not in entry:
                return None
            if process_started(entry["pid"]) == entry["procStart"].split():
                out.add(entry["sessionId"])
    return frozenset(out) if reader in out else None


def process_started(pid: int) -> list[str] | None:
    """The words of the start of process `pid`, or None where it does not
    run."""
    done = subprocess.run(["ps", "-o", "lstart=", "-p", str(pid)], capture_output=True,
                          text=True, env={**os.environ, "TZ": "UTC"})
    return done.stdout.split() if done.returncode == 0 else None


def read_session(path: Path) -> tuple[str, float] | None:
    try:
        text, written = path.read_text().strip(), path.stat().st_mtime
    except FileNotFoundError:
        return None
    return (text, written) if text else None


def named_main(tickets: Path) -> str | None:
    held = read_session(tickets / MAIN)
    return held[0] if held else None


def read_sessions(tickets: Path, index: int, now: float) -> Sessions:
    ids = indexes(tickets)
    held = {ticket_name(p).number.session for s in Status if s not in SETTLED
            for p in listed_tickets(tickets, s)}
    idle = frozenset(i for i in held if i is not None and i != index
                     and not any(live(sid, now) for sid in ids.get(i, [])))
    main = named_main(tickets)
    return Sessions(idle=idle, main=main is not None and main in ids.get(index, []),
                    main_live=main is not None and live(main, now))


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
