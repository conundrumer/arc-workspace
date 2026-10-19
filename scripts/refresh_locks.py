"""The refresh locks of the sessions' kept reads: a file per session under
`checkout.caches()`, which a merge locks exclusively before the
fast-forward that makes the kept reads of its code stale, and which
`scripts/kept_refresh.py` holds, once the merge hands it over, until it
has written that session's reads. A state read waits for its session's
lock (`wait_free`), so it reads those reads from the store in place of
computing them.

The module imports none of the state reads, so the merge call that takes
the locks does not import them."""

import fcntl
import os
import subprocess
import time
from pathlib import Path
from typing import IO

import script_calls
from engine import checkout

LOCKS = "kept-refresh"
"""The directory, under `checkout.caches()`, of the locks."""

WAIT_SECONDS = 120
"""How long a state read waits for its session's lock to be free, within
the bound on a foreground call."""

POLL_SECONDS = 0.2

LIVE_SECONDS = 1800
"""How far back a session's `operate.py next` call makes it live
(`live_sessions`), within `kept_reads.KEEP_SECONDS`."""

NEXT_KEY = script_calls.key("operate.py", ["next"])

REFRESH = ("scripts/kept_refresh.py",)
"""The command, after `uv run python`, that writes the kept reads of the
sessions whose locks it is handed."""


def lock_path(session: str) -> Path:
    """The file of the refresh lock of the session `session`."""
    return checkout.caches() / LOCKS / f"{session}.lock"


def hold(session: str) -> IO[str]:
    """The open file of the refresh lock of `session`, locked exclusively
    until every copy of its descriptor is closed."""
    path = lock_path(session)
    path.parent.mkdir(parents=True, exist_ok=True)
    f = open(path, "a")
    fcntl.flock(f, fcntl.LOCK_EX)
    return f


def wait_free(session: str) -> None:
    """Returns once no process holds the refresh lock of `session`, or
    once `WAIT_SECONDS` have passed."""
    try:
        fd = os.open(lock_path(session), os.O_RDONLY)
    except FileNotFoundError:
        return
    try:
        end = time.monotonic() + WAIT_SECONDS
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_SH | fcntl.LOCK_NB)
                return
            except BlockingIOError:
                if time.monotonic() >= end:
                    return
                time.sleep(POLL_SECONDS)
    finally:
        os.close(fd)


def live_sessions(main: Path, since: float) -> list[str]:
    """The sessions of the `operate.py next` calls that the script-call
    records of the main tree `main` give at or after `since`, in the order
    of each session's first such call."""
    calls = script_calls.read(str(main / script_calls.RECORDS), since)
    return list(dict.fromkeys(c.session for c in calls if c.key == NEXT_KEY and c.session))


class MergeLocks:
    """The refresh locks one merge call holds: those of the merging
    session, where one is given, first, and of the live sessions, taken
    before the first fast-forward of `master` that changes a `.py` file
    (`take`), and handed to the refresh once the merge lock is released
    (`start`), or released (`close`)."""

    def __init__(self, main: Path, merging: str | None) -> None:
        self.main = main
        self.merging = merging
        self.files: dict[str, IO[str]] = {}
        self.landed = False

    def take(self, top: str) -> None:
        """Takes the locks, where none is held and the commits from the
        main tree's `HEAD` to `top` change a `.py` file."""
        if self.files or not checkout.git_out(
                self.main, "diff", "--name-only", "HEAD", top, "--", "*.py").strip():
            return
        first = [self.merging] if self.merging is not None else []
        live = live_sessions(self.main, time.time() - LIVE_SECONDS)
        self.files = {s: hold(s) for s in dict.fromkeys([*first, *live])}

    def mark_landed(self) -> None:
        """Records a fast-forward that succeeded, where the locks are held."""
        self.landed = self.landed or bool(self.files)

    def start(self) -> subprocess.Popen[bytes] | None:
        """Starts the refresh in the main tree, as a process in a session
        of its own, with the locks held where `landed` is set, and then
        closes this process's copies; None where no refresh starts."""
        if not (self.files and self.landed):
            self.close()
            return None
        fds = {s: f.fileno() for s, f in self.files.items()}
        merging = ("--merging", self.merging) if self.merging is not None else ()
        held = [a for s, fd in fds.items() for a in ("--held", s, str(fd))]
        try:
            return subprocess.Popen(
                ("uv", "run", "python", *REFRESH, *merging, *held), cwd=self.main,
                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                pass_fds=tuple(fds.values()), start_new_session=True)
        finally:
            self.close()

    def close(self) -> None:
        """Closes this process's copies of the locks' files."""
        for f in self.files.values():
            f.close()
        self.files = {}
