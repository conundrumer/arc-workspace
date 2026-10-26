"""The heavy commands' lock, which every worktree of the repository and
every session on the machine share. A `run_dl.py` command holds it shared
(`held`, `taken`), and such commands run alongside each other. The lock is
a file in the common git directory, `LOCK_FILE`, held shared through
`flock`.

A holder sets `HOLD_ENV` to the value of its `Hold`, and every process it
starts inherits that variable. A process that starts under a hold runs
under it and takes no hold of its own.

Beside it stands a mutex (`Mutex`), a file held exclusively through
`flock`. The merge lock, `MERGE_FILE` in the same directory, is held by
`scripts/merge_change.py`, so that one merge at a time moves `master`. A
holder writes into the file what it does, and a process that has to wait
says on stderr that it waits and what the holder wrote, where the holder
has written it yet. A process that starts under a hold of the heavy
commands' lock waits for no mutex, since the holder it would wait for can
be the process it runs under: where another process holds it, the process
stops (`MergeHeld`).

The kernel releases each hold, of the lock and of the mutex, when its
holder ends, however it ends, so a holder that crashes or is killed leaves
no hold behind."""

import contextlib
import fcntl
import os
import sys
import threading
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import IO

from controlled_markdown import mctx
from engine import checkout

LOCK_FILE = "arc-heavy.lock"
MERGE_FILE = "arc-merge.lock"

HOLD_ENV = "ARC_HEAVY_HOLD"
"""The environment variable set to the value of the `Hold` a process runs
under."""


class Hold(StrEnum):
    SHARED = "shared"


class MergeHeld(Exception):
    pass


def inherited() -> Hold | None:
    """The hold the process started under, or None where it started under
    none. A value of `HOLD_ENV` that is no value of `Hold` is a fault."""
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
def taken(hold: Hold) -> Iterator[Hold]:
    """`hold` on the repository's lock, or the hold the process started
    under; the hold that the processes started under it run under."""
    started = inherited()
    if started is not None:
        yield started
        return
    with open(lock_dir() / LOCK_FILE, "a") as lock:
        fcntl.flock(lock, fcntl.LOCK_SH)
        yield hold


@contextlib.contextmanager
def held(hold: Hold) -> Iterator[None]:
    """`hold` on the repository's lock, with `HOLD_ENV` set to its value
    while it lasts, or the hold the process started under."""
    started = inherited()
    with taken(hold) as under:
        if started is not None:
            yield
            return
        os.environ[HOLD_ENV] = under
        try:
            yield
        finally:
            del os.environ[HOLD_ENV]


WAIT = mctx("Another process holds the lock whose file is {path}, so this {noun} waits "
            "until that process releases the lock.")
HOLDER = mctx("The holder wrote: {holder}")
HELD = mctx("Another process holds the lock whose file is {path}, and this {noun} stops. "
            "This {noun} runs inside a `run_dl.py` command, "
            "and that command may be the holder. Run this {noun} again outside that command.")


@dataclass(frozen=True)
class Mutex:
    """A lock one process holds at a time: its file's name, the noun of
    the process that holds it, which `WAIT` and `HELD` take, and the fault
    of a process that cannot wait."""
    file: str
    noun: str
    refused: type[Exception]


MERGE = Mutex(MERGE_FILE, mctx("merge"), MergeHeld)


@contextlib.contextmanager
def mutex_held(mutex: Mutex, directory: Path, holder: str) -> Iterator[None]:
    """`mutex`, whose file stands in `directory`, held exclusively, with
    `holder` written into the file while it lasts."""
    path = directory / mutex.file

    def wait(text: str) -> str:
        written = path.read_text().strip()
        return text if not written else f"{text} {HOLDER.format(holder=written)}"

    with open(path, "a") as fh:
        if inherited() is None:
            _take(fh, fcntl.LOCK_EX, Notice(),
                  lambda: wait(WAIT.format(noun=mutex.noun, path=path)))
        else:
            try:
                fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise mutex.refused(wait(HELD.format(noun=mutex.noun, path=path))) from None
        fh.truncate(0)
        fh.write(holder + "\n")
        fh.flush()
        yield


def merge_lock(directory: Path, holder: str) -> contextlib.AbstractContextManager[None]:
    """The merge lock whose file stands in `directory`, held as `mutex_held`
    gives."""
    return mutex_held(MERGE, directory, holder)
