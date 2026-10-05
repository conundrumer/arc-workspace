"""The readers-writer lock over the repository's heavy commands, which
every worktree of the repository and every session on the machine share. A
`run_dl.py` command, a pytest run and an `--outputs-only` gate run hold it
shared, and run alongside each other. A timed gate run holds it
exclusively, so that it shares the machine with no other heavy command.

The writer has priority: a writer that waits marks itself pending, and a
reader that asks after the mark waits until the writer is done, so that a
steady flow of readers cannot starve it. The lock is two files in the
common git directory, each held through `flock`. A writer holds
`PENDING_FILE` exclusively from its request to its release, and that hold
is the mark. A reader holds `PENDING_FILE` exclusively only while it asks
for `LOCK_FILE`. A reader holds `LOCK_FILE` shared, and a writer holds it
exclusively. The kernel releases a hold when its process ends, however it
ends, so a holder that crashes or is killed leaves no hold behind, and the
files themselves mean nothing.

A wait lasts as long as the holders it waits for: a writer waits for every
reader that holds the lock, and every reader that asks after it waits for
the writer too. A command that has to wait says so on stderr, once, before
it waits.

A holder names its hold in `HOLD_ENV`, which every process it starts
inherits. A process that starts under a hold runs under it and takes no
hold of its own, since a hold it waited for could wait behind a writer that
waits for its parent. A process that starts under a shared hold and asks
for the exclusive one is a fault (`NestedWriter`), since its parent's hold
is one it would wait for."""

import contextlib
import fcntl
import os
import sys
from collections.abc import Iterator
from enum import StrEnum
from pathlib import Path
from typing import IO

from controlled_markdown import mctx
from engine import checkout

LOCK_FILE = "arc-heavy.lock"
PENDING_FILE = "arc-heavy.pending"

HOLD_ENV = "ARC_HEAVY_HOLD"
"""The environment variable that names the hold a process runs under."""


class Hold(StrEnum):
    SHARED = "shared"
    EXCLUSIVE = "exclusive"


class NestedWriter(Exception):
    pass


WAITS = {
    Hold.SHARED: mctx("A timed gate run holds {path} or waits for it, so this command "
                      "waits until that run is done."),
    Hold.EXCLUSIVE: mctx("Other heavy commands hold {path}, so this timed gate run waits "
                         "until they are done."),
}


def inherited() -> Hold | None:
    """The hold the process started under, or None where it started under
    none. A value of `HOLD_ENV` that names no hold is a fault."""
    raw = os.environ.get(HOLD_ENV)
    return None if raw is None else Hold(raw)


def _take(fh: IO[str], op: int, said: list[bool], wait: str) -> None:
    try:
        fcntl.flock(fh, op | fcntl.LOCK_NB)
    except BlockingIOError:
        if not said[0]:
            print(wait, file=sys.stderr, flush=True)
            said[0] = True
        fcntl.flock(fh, op)


@contextlib.contextmanager
def lock_files(hold: Hold, directory: Path) -> Iterator[None]:
    """`hold` on the lock whose files stand in `directory`."""
    path = directory / LOCK_FILE
    wait = WAITS[hold].format(path=path)
    said = [False]
    with open(directory / PENDING_FILE, "a") as pending, open(path, "a") as lock:
        _take(pending, fcntl.LOCK_EX, said, wait)
        if hold is Hold.SHARED:
            _take(lock, fcntl.LOCK_SH, said, wait)
            fcntl.flock(pending, fcntl.LOCK_UN)
        else:
            _take(lock, fcntl.LOCK_EX, said, wait)
        yield


@contextlib.contextmanager
def held(hold: Hold) -> Iterator[None]:
    """`hold` on the repository's lock, named in `HOLD_ENV` while it lasts,
    or the hold the process started under."""
    outer = inherited()
    if outer is Hold.SHARED and hold is Hold.EXCLUSIVE:
        raise NestedWriter(mctx("This command asks for the heavy commands' lock "
                                "exclusively, and it runs under a command that holds it "
                                "shared."))
    if outer is not None:
        yield
        return
    with lock_files(hold, checkout.git_common_dir(checkout.ROOT)):
        os.environ[HOLD_ENV] = hold
        try:
            yield
        finally:
            del os.environ[HOLD_ENV]
