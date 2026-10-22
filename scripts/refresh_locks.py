"""The refresh locks of the sessions' kept reads: a file per session under
`checkout.caches()`, which a merge locks exclusively before the
fast-forward that makes the kept reads of its code stale, and releases once
that fast-forward has landed. A state read waits for its session's lock
(`wait_free`) while a merge is in progress, and a request of a resident
that meets the lock is replaced. `scripts/kept_refresh.py` then has each
session's resident read the state, so that the reads of the new code are
kept.

The module imports none of the state reads, so the merge call that takes
the locks does not import them."""

import fcntl
import subprocess
import time
from pathlib import Path
from typing import IO

import script_calls
import read_interrupts
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
"""The command, after `uv run python`, that has the residents of the sessions
it is given read the state."""


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


def try_shared(session: str) -> IO[str] | None:
    """Return an open shared lock, or None while an exclusive holder owns it."""
    path = lock_path(session)
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = path.open("a")
    try:
        fcntl.flock(lock, fcntl.LOCK_SH | fcntl.LOCK_NB)
    except BlockingIOError:
        lock.close()
        return None
    except BaseException:
        lock.close()
        raise
    return lock


def wait_free(session: str, deadline: float | None = None) -> bool:
    """Report whether the lock became free before an absolute monotonic deadline.

    Calls without a deadline wait at most `WAIT_SECONDS`.
    """
    end = time.monotonic() + WAIT_SECONDS if deadline is None else deadline
    while time.monotonic() < end:
        if (lock := try_shared(session)) is not None:
            lock.close()
            return True
        read_interrupts.sleep(min(POLL_SECONDS, max(end - time.monotonic(), 0)))
    return False


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
    (`take`), released once that fast-forward has landed (`mark_landed`)
    or at `close`, and the sessions whose locks a landed fast-forward
    released, whose residents the refresh reads (`start`)."""

    def __init__(self, main: Path, merging: str | None) -> None:
        self.main = main
        self.merging = merging
        self.files: dict[str, IO[str]] = {}
        self.landed: dict[str, None] = {}

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
        """Records a fast-forward that succeeded, where the locks are held,
        and releases them."""
        self.landed.update(dict.fromkeys(self.files))
        self.close()

    def start(self) -> subprocess.Popen[bytes] | None:
        """Starts the refresh in the main tree, as a process in a session
        of its own, for the sessions of the fast-forwards that landed, and
        releases any lock still held; None where no refresh starts."""
        self.close()
        if not self.landed:
            return None
        return subprocess.Popen(
            ("uv", "run", "python", *REFRESH, *self.landed), cwd=self.main,
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            start_new_session=True)

    def close(self) -> None:
        """Closes this process's copies of the locks' files."""
        for f in self.files.values():
            f.close()
        self.files = {}
