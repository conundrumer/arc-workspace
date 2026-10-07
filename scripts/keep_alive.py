"""Starts and stops an agent's keep-alive timer, by the agent's id. `HELP`,
which `--help` prints, says how an agent calls it.

The state of each agent's timer is in files under `/tmp`, so a start or a
stop from any worktree reaches the same timer. The timer runs while its
process holds an exclusive lock on `/tmp/keep-alive-<agent id>.timer`, which
the system releases when that process ends, however it ends. So a pid file
left by a timer that ended, or a pid that another process now has, never
counts as a running timer."""

import argparse
import fcntl
import os
import re
import signal
import sys
import textwrap
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from types import FrameType

from controlled_markdown import mctx

SECONDS = 240
STATE_DIR = Path("/tmp")
AGENT_ID = re.compile(r"[A-Za-z0-9_-]+")

HELP = mctx("""
    - An agent has at most one keep-alive timer, which sleeps {seconds} seconds.
    - `start` starts the timer where none of the agent's runs, and records its pid. Where one runs, it starts no second timer, and waits until that timer ends, so it completes when that timer does.
    - `stop` ends the running timer, and with it each `start` that waits on it, and completes once the timer has ended. Where no timer runs, it does nothing.
    - Run a start in the background, led by `: 'unattended-wait: keep-alive timer';`:
        ```
        : 'unattended-wait: keep-alive timer'; uv run python scripts/keep_alive.py start <agent id>
        ```
    - Run a stop in the foreground:
        ```
        uv run python scripts/keep_alive.py stop <agent id>
        ```
    """)


def state_file(agent: str, suffix: str) -> Path:
    return STATE_DIR / f"keep-alive-{agent}.{suffix}"


def open_timer(agent: str) -> int:
    return os.open(state_file(agent, "timer"), os.O_RDWR | os.O_CREAT, 0o600)


@contextmanager
def serialized(agent: str) -> Iterator[None]:
    """Holds the lock that serializes the starts and stops of `agent`."""
    with open(state_file(agent, "lock"), "a") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def timer_runs(timer: int) -> bool:
    """Whether a process holds the exclusive lock on the timer file open as
    `timer`: a shared lock is refused only while one does."""
    try:
        fcntl.flock(timer, fcntl.LOCK_SH | fcntl.LOCK_NB)
    except BlockingIOError:
        return True
    fcntl.flock(timer, fcntl.LOCK_UN)
    return False


def wait_for_end(timer: int) -> None:
    """Blocks until no process holds the exclusive lock on `timer`."""
    fcntl.flock(timer, fcntl.LOCK_SH)
    fcntl.flock(timer, fcntl.LOCK_UN)


def on_term(signum: int, frame: FrameType | None) -> None:
    raise SystemExit(0)


def start(agent: str) -> None:
    timer = open_timer(agent)
    pid_file = state_file(agent, "pid")
    with serialized(agent):
        joins = timer_runs(timer)
        if not joins:
            # A start that waits on an ended timer may hold its shared lock
            # for a moment, so this lock blocks rather than fails.
            fcntl.flock(timer, fcntl.LOCK_EX)
            pid_file.write_text(f"{os.getpid()}\n")
    if joins:
        print(mctx("keep-alive {agent}: a timer runs, so this start waits for it to end").format(agent=agent))
        wait_for_end(timer)
        print(mctx("keep-alive {agent}: the timer ended").format(agent=agent))
        return
    signal.signal(signal.SIGTERM, on_term)
    print(mctx("keep-alive {agent}: timer started, pid {pid}").format(agent=agent, pid=os.getpid()))
    try:
        time.sleep(SECONDS)
        print(mctx("keep-alive {agent}: timer completed").format(agent=agent))
    except SystemExit:
        print(mctx("keep-alive {agent}: timer stopped").format(agent=agent))
        raise
    finally:
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        with serialized(agent):
            pid_file.write_text("")
            os.close(timer)


def stop(agent: str) -> None:
    timer = open_timer(agent)
    pid_file = state_file(agent, "pid")
    with serialized(agent):
        if not timer_runs(timer):
            pid_file.write_text("")
            print(mctx("keep-alive {agent}: no timer runs").format(agent=agent))
            return
        # The pid file was written by the process that holds the timer's
        # lock, which still runs, so its pid is that process's.
        pid = int(pid_file.read_text())
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    wait_for_end(timer)
    print(mctx("keep-alive {agent}: timer {pid} stopped").format(agent=agent, pid=pid))


def main() -> None:
    parser = argparse.ArgumentParser(
        description=textwrap.dedent(HELP).format(seconds=SECONDS), formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("action", choices=["start", "stop"])
    parser.add_argument("agent_id")
    args = parser.parse_args()
    agent: str = args.agent_id
    if not AGENT_ID.fullmatch(agent):
        sys.exit(mctx("keep-alive: `{agent}` is not an agent id").format(agent=agent))
    {"start": start, "stop": stop}[args.action](agent)


if __name__ == "__main__":
    main()
