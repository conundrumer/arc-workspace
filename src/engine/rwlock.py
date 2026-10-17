"""The readers-writer lock over the repository's heavy commands, which
every worktree of the repository and every session on the machine share. A
`run_dl.py` command and a pytest run hold it shared, and run alongside each
other, and a holder that needs the machine to itself holds it exclusively.
`scripts/gate.py` gives the holds a gate run takes.

The writer has priority: a writer that waits marks itself pending, and a
reader that asks after the mark waits until the writer is done, so that a
steady flow of readers cannot starve it. The lock is two files in the
common git directory, each held through `flock`. A writer holds
`PENDING_FILE` exclusively from its request to its release, and that hold
is the mark. A reader holds `PENDING_FILE` shared only while it asks for
`LOCK_FILE`. A reader holds `LOCK_FILE` shared, and a writer holds it
exclusively. No writer holds `LOCK_FILE` while a reader holds `PENDING_FILE`, so a reader's hold of
`PENDING_FILE` lasts an instant, and a writer that asks for the mark gets
it once no reader is in that instant. The kernel releases a hold when its
process ends, however it ends, so a holder that crashes or is killed leaves
no hold behind, and the files themselves mean nothing.

A wait lasts as long as the holders it waits for: a writer waits for every
reader that holds the lock, and every reader that asks after it waits for
the writer too. A reader waits only where a writer holds the mark, and a
reader that asks while only readers hold the lock or ask for it does not
wait. A command that has to wait says so on stderr, once, before it waits,
and the holder of several holds that share a `Notice` says so once for all
of them, since the text of a wait names its holders.

A holder names its hold in `HOLD_ENV`, which every process it starts
inherits, and a gate run names each command's hold in that command's
environment. A process that starts under a hold runs under it and takes no
hold of its own, since a hold it waited for could wait behind a writer that
waits for its parent. A process that starts under a shared hold and asks
for the exclusive one is a fault (`NestedWriter`), since its parent's hold
is one it would wait for.

Beside it stands the merge lock, `MERGE_FILE` in the same directory, which
`scripts/merge_change.py` holds exclusively through `flock`, so that one
merge at a time moves `master`. Its holder writes into the file what it
merges, and a merge that has to wait says on stderr, once, that it waits
and what the holder wrote, where the holder has written it yet. A process
that starts under a hold of the heavy commands' lock does not wait for the
merge lock, for the reason it takes no heavy hold of its own: where another
merge holds it, the process stops (`MergeHeld`). The kernel releases that
hold too when its holder ends."""

import contextlib
import fcntl
import os
import sys
import threading
from collections.abc import Callable, Iterator
from enum import StrEnum
from pathlib import Path
from typing import IO

from controlled_markdown import mctx
from engine import checkout

LOCK_FILE = "arc-heavy.lock"
PENDING_FILE = "arc-heavy.pending"
MERGE_FILE = "arc-merge.lock"

HOLD_ENV = "ARC_HEAVY_HOLD"
"""The environment variable that names the hold a process runs under."""


class Hold(StrEnum):
    SHARED = "shared"
    EXCLUSIVE = "exclusive"


class NestedWriter(Exception):
    pass


class MergeHeld(Exception):
    pass


WAITS = {
    Hold.SHARED: mctx("The cold pass of a timed gate run holds {path} or waits for it, "
                      "so this command waits until that pass is done."),
    Hold.EXCLUSIVE: mctx("Other heavy commands hold {path}, so this timed gate run waits "
                         "until they are done."),
}

SKIP = mctx("skipped: another heavy command holds {path} or waits for it, so this timed "
            "run skips timing, runs no command, and leaves the records of timed runs as "
            "they are")


def inherited() -> Hold | None:
    """The hold the process started under, or None where it started under
    none. A value of `HOLD_ENV` that names no hold is a fault."""
    raw = os.environ.get(HOLD_ENV)
    return None if raw is None else Hold(raw)


class Notice:
    """A wait line printed on stderr before the first wait of the holds
    that share it, and not again."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.said = False

    def say(self, line: Callable[[], str]) -> None:
        with self.lock:
            if self.said:
                return
            self.said = True
        print(line(), file=sys.stderr, flush=True)


def _take(fh: IO[str], op: int, notice: Notice, line: Callable[[], str]) -> None:
    try:
        fcntl.flock(fh, op | fcntl.LOCK_NB)
    except BlockingIOError:
        notice.say(line)
        fcntl.flock(fh, op)


def lock_dir() -> Path:
    """The directory the repository's lock files stand in."""
    return checkout.git_common_dir(checkout.ROOT)


@contextlib.contextmanager
def opened(directory: Path) -> Iterator[tuple[IO[str], IO[str]]]:
    """The pending mark and the lock whose files stand in `directory`, open
    to append, the pending mark opened first."""
    with open(directory / PENDING_FILE, "a") as pending, open(directory / LOCK_FILE, "a") as lock:
        yield pending, lock


@contextlib.contextmanager
def lock_files(hold: Hold, directory: Path, notice: Notice) -> Iterator[None]:
    """`hold` on the lock whose files stand in `directory`, its wait said
    through `notice`."""
    path = directory / LOCK_FILE
    text = WAITS[hold].format(path=path)

    def line() -> str:
        return text

    with opened(directory) as (pending, lock):
        op = fcntl.LOCK_SH if hold is Hold.SHARED else fcntl.LOCK_EX
        _take(pending, op, notice, line)
        _take(lock, op, notice, line)
        if hold is Hold.SHARED:
            fcntl.flock(pending, fcntl.LOCK_UN)
        yield


def outer(hold: Hold) -> Hold | None:
    """The hold the process started under, which a request for `hold` runs
    under, or None where it started under none. A request for the exclusive
    hold under the shared one is a fault."""
    started = inherited()
    if started is Hold.SHARED and hold is Hold.EXCLUSIVE:
        raise NestedWriter(mctx("This command asks for the heavy commands' lock "
                                "exclusively, and it runs under a command that holds it "
                                "shared."))
    return started


@contextlib.contextmanager
def taken(hold: Hold, notice: Notice) -> Iterator[Hold]:
    """`hold` on the repository's lock, its wait said through `notice`, or
    the hold the process started under; the hold that the processes started
    under it run under."""
    started = outer(hold)
    if started is not None:
        yield started
        return
    with lock_files(hold, lock_dir(), notice):
        yield hold


@contextlib.contextmanager
def tried() -> Iterator[Hold | None]:
    """The exclusive hold on the repository's lock where it is free at
    once, or the hold the process started under; None where a holder or a
    pending writer stands. The mark is held only for the tries."""
    started = outer(Hold.EXCLUSIVE)
    if started is not None:
        yield started
        return
    with opened(lock_dir()) as (pending, lock):
        try:
            fcntl.flock(pending, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            yield None
            return
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            fcntl.flock(pending, fcntl.LOCK_UN)
            yield None
            return
        yield Hold.EXCLUSIVE


@contextlib.contextmanager
def held(hold: Hold) -> Iterator[None]:
    """`hold` on the repository's lock, named in `HOLD_ENV` while it lasts,
    or the hold the process started under."""
    started = inherited()
    with taken(hold, Notice()) as under:
        if started is not None:
            yield
            return
        os.environ[HOLD_ENV] = under
        try:
            yield
        finally:
            del os.environ[HOLD_ENV]


MERGE_WAIT = mctx("Another merge holds {path}, so this merge waits until it is done.")
MERGE_HOLDER = mctx("The holder wrote: {holder}")
MERGE_HELD = mctx("Another merge holds {path}, and this merge cannot wait for it, "
                  "since it runs under an inherited hold of the heavy commands' lock.")


@contextlib.contextmanager
def merge_lock(directory: Path, holder: str) -> Iterator[None]:
    """The merge lock whose file stands in `directory`, held exclusively,
    with `holder` written into the file while it lasts."""
    path = directory / MERGE_FILE

    def wait(text: str) -> str:
        written = path.read_text().strip()
        return text if not written else f"{text} {MERGE_HOLDER.format(holder=written)}"

    with open(path, "a") as fh:
        if inherited() is None:
            _take(fh, fcntl.LOCK_EX, Notice(), lambda: wait(MERGE_WAIT.format(path=path)))
        else:
            try:
                fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise MergeHeld(wait(MERGE_HELD.format(path=path))) from None
        fh.truncate(0)
        fh.write(holder + "\n")
        fh.flush()
        yield
