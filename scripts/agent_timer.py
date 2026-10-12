"""Starts and stops an agent's timers, by the agent's id and the timer's
kind. `HELP`, which `--help` prints, gives the usage forms and what each
action does.

The state of each timer is in files under `/tmp`, named by the timer's
kind and the agent's id, so a start or a stop from any worktree reaches the
same timer. The timer runs while its process holds an exclusive lock on
`/tmp/<kind>-<agent id>.timer`, which the system releases when that process
ends, however it ends. So a pid file left by a timer that ended, or a pid
that another process now has, never counts as a running timer.

What a start does where a timer of its kind runs, as `HELP` gives it,
rests on two reasons: an agent needs only one keep-alive timer to end, and
a budget counts from its own start, which a timer started earlier cannot
give."""

import argparse
import fcntl
import os
import re
import signal
import sys
import textwrap
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from types import FrameType

from controlled_markdown import mctx
from operations.constants import WAIT_SECONDS

STATE_DIR = Path("/tmp")
AGENT_ID = re.compile(r"[A-Za-z0-9_-]+")


class Kind(StrEnum):
    KEEP_ALIVE = "keep-alive"
    BUDGET = "budget"

    @property
    def fixed_seconds(self) -> int | None:
        """The seconds a timer of this kind sleeps, which its start does
        not give; None where its start gives them."""
        return WAIT_SECONDS if self is Kind.KEEP_ALIVE else None


class Action(StrEnum):
    START = "start"
    STOP = "stop"


class StateFile(StrEnum):
    """A file of a timer's state, by its suffix: the file whose lock the
    running timer holds, the lock that serializes the starts and stops of
    the timer, and the running timer's pid."""

    TIMER = "timer"
    LOCK = "lock"
    PID = "pid"


HELP = mctx("""
    - An agent has at most one timer of each kind.
        - A `keep-alive` timer sleeps {seconds} seconds, and a `budget` timer sleeps the seconds its start gives.
    - `start` starts a timer of its kind where none of the agent's runs, records its pid, and completes when that timer ends.
        - Where a keep-alive timer runs, a keep-alive start starts no second one, and waits until that one ends.
        - Where a budget timer runs, a budget start fails, and that timer runs on.
    - `stop` ends the running timer of its kind, and with it each start that waits on it, and completes once the timer has ended.
        - Where none runs, it does nothing.
    - The usage forms:
        ```
        uv run python scripts/agent_timer.py start keep-alive <agent id>
        uv run python scripts/agent_timer.py start budget <agent id> <seconds>
        uv run python scripts/agent_timer.py stop keep-alive <agent id>
        uv run python scripts/agent_timer.py stop budget <agent id>
        ```
    """)


@dataclass(frozen=True)
class Timer:
    kind: Kind
    agent: str

    def state_file(self, suffix: StateFile) -> Path:
        return STATE_DIR / f"{self.kind}-{self.agent}.{suffix}"

    def open(self) -> int:
        return os.open(self.state_file(StateFile.TIMER), os.O_RDWR | os.O_CREAT, 0o600)

    def status(self, line: str, **fields: object) -> str:
        return f"{self.kind} {self.agent}: {line.format(**fields)}"

    def say(self, line: str, **fields: object) -> None:
        print(self.status(line, **fields), flush=True)

    @contextmanager
    def serialized(self) -> Iterator[None]:
        """Holds the lock that serializes the starts and stops of this
        timer."""
        with open(self.state_file(StateFile.LOCK), "a") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)


def timer_runs(fd: int) -> bool:
    """Whether a process holds the exclusive lock on the timer file open as
    `fd`: a shared lock is refused only while one does."""
    try:
        fcntl.flock(fd, fcntl.LOCK_SH | fcntl.LOCK_NB)
    except BlockingIOError:
        return True
    fcntl.flock(fd, fcntl.LOCK_UN)
    return False


def wait_for_end(fd: int) -> None:
    """Blocks until no process holds the exclusive lock on `fd`."""
    fcntl.flock(fd, fcntl.LOCK_SH)
    fcntl.flock(fd, fcntl.LOCK_UN)


def on_term(signum: int, frame: FrameType | None) -> None:
    raise SystemExit(0)


def start(timer: Timer, seconds: int | None) -> None:
    if seconds is None:
        raise ValueError(f"a {timer.kind} start is given no seconds")
    fd = timer.open()
    pid_file = timer.state_file(StateFile.PID)
    with timer.serialized():
        runs = timer_runs(fd)
        holder = pid_file.read_text().strip() if runs else ""
        if not runs:
            # A start that waits on an ended timer may hold its shared lock
            # for a moment, so this lock blocks rather than fails.
            fcntl.flock(fd, fcntl.LOCK_EX)
            pid_file.write_text(f"{os.getpid()}\n")
    if runs and timer.kind is Kind.BUDGET:
        sys.exit(timer.status(mctx("a timer runs, pid {pid}, so this start fails"), pid=holder))
    if runs:
        timer.say(mctx("a timer runs, so this start waits for it to end"))
        wait_for_end(fd)
        timer.say(mctx("the timer ended"))
        return
    signal.signal(signal.SIGTERM, on_term)
    timer.say(mctx("timer started, pid {pid}, for {seconds} seconds"), pid=os.getpid(), seconds=seconds)
    try:
        time.sleep(seconds)
        timer.say(mctx("timer completed"))
    except SystemExit:
        timer.say(mctx("timer stopped"))
        raise
    finally:
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        with timer.serialized():
            pid_file.write_text("")
            os.close(fd)


def stop(timer: Timer, seconds: int | None) -> None:
    fd = timer.open()
    pid_file = timer.state_file(StateFile.PID)
    with timer.serialized():
        if not timer_runs(fd):
            pid_file.write_text("")
            timer.say(mctx("no timer runs"))
            return
        # The pid file was written by the process that holds the timer's
        # lock, which still runs, so its pid is that process's.
        pid = int(pid_file.read_text())
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    wait_for_end(fd)
    timer.say(mctx("timer {pid} stopped"), pid=pid)


ACTIONS: dict[Action, Callable[[Timer, int | None], None]] = {
    Action.START: start, Action.STOP: stop}


def main() -> None:
    parser = argparse.ArgumentParser(
        description=textwrap.dedent(HELP).format(seconds=WAIT_SECONDS),
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("action", choices=[str(a) for a in Action])
    parser.add_argument("kind", choices=[str(k) for k in Kind])
    parser.add_argument("agent_id")
    parser.add_argument("seconds", type=int, nargs="?")
    args = parser.parse_args()
    action = Action(args.action)
    kind = Kind(args.kind)
    agent: str = args.agent_id
    given: int | None = args.seconds
    if not AGENT_ID.fullmatch(agent):
        parser.error(mctx("`{agent}` is not an agent id").format(agent=agent))
    if (action is Action.START and kind.fixed_seconds is None) != (given is not None):
        parser.error(mctx("seconds are given with a start of {kinds}, and with no other call").format(
            kinds=" or ".join(f"`{k}`" for k in Kind if k.fixed_seconds is None)))
    if given is not None and given <= 0:
        parser.error(mctx("the seconds are {seconds}, not a positive number").format(seconds=given))
    ACTIONS[action](Timer(kind, agent), kind.fixed_seconds or given)


if __name__ == "__main__":
    main()
