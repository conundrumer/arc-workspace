"""The heavy commands' lock, which every worktree of the repository and
every session on the machine share. A `run_dl.py` command, a pytest run
and each command of a gate run hold it shared (`held`, `taken`), and run
alongside each other. The lock is a file in the common git directory,
`LOCK_FILE`, held shared through `flock`.

A holder sets `HOLD_ENV` to the value of its `Hold`, and every process it
starts inherits that variable; a gate run sets it in each command's
environment. A process that starts under a hold runs under it and takes no
hold of its own.

Beside it stand two mutexes (`Mutex`), each a file held exclusively
through `flock`. The merge lock, `MERGE_FILE` in the same directory, is held
by `scripts/merge_change.py`, so that one merge at a time moves `master`.
The gate lock, `GATE_FILE` in the git directory of one worktree
(`gate_lock_dir`), is held by `scripts/gate.py`, so that one gate run at a
time runs in that worktree. A holder writes into the file what it does, and
a process that has to wait says on stderr that it waits and what the
holder wrote, where the holder has written it yet. A process that starts
under a hold of the heavy commands' lock waits for neither mutex, since the
holder it would wait for can be the process it runs under: where another
process holds it, the process stops (`MergeHeld`, `GateHeld`).

The kernel releases each hold, of the lock and of each mutex, when its
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
GATE_FILE = "arc-gate.lock"

HOLD_ENV = "ARC_HEAVY_HOLD"
"""The environment variable set to the value of the `Hold` a process runs
under."""


class Hold(StrEnum):
    SHARED = "shared"


class MergeHeld(Exception):
    pass


class GateHeld(Exception):
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


WAIT = mctx("Another {noun} holds {path}, so this {noun} waits until it is done.")
HOLDER = mctx("The holder wrote: {holder}")
HELD = mctx("Another {noun} holds {path}, and this {noun} stops, since it runs inside "
            "a `run_dl.py` command, a pytest run or a gate command, which may be that "
            "holder. Run it again outside that command.")


@dataclass(frozen=True)
class Mutex:
    """A lock one process holds at a time: its file's name, the noun of
    the process that holds it, which `WAIT` and `HELD` take, and the fault
    of a process that cannot wait."""
    file: str
    noun: str
    refused: type[Exception]


MERGE = Mutex(MERGE_FILE, mctx("merge"), MergeHeld)
GATE = Mutex(GATE_FILE, mctx("gate run"), GateHeld)


def gate_lock_dir() -> Path:
    """The directory the gate lock of this checkout stands in: the
    checkout's own git directory, which no other worktree shares."""
    return Path(checkout.git_out(checkout.ROOT, "rev-parse", "--absolute-git-dir").strip())


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
