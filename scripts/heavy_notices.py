"""The messages that the resource daemon (`scripts/resource_daemon.py`)
sends the Claude Code session that owns a process: the texts, and the rule on
how many go out.

The daemon acts on a process and a reason once (`Notices.once`), and sends the
messages for one session that fall within `FOLD_SECONDS` as one.

Standard library only, Python 3.9. `mctx` is `controlled_markdown.mctx`,
which it cannot import: the check of prose in code reads a call by its name."""

from __future__ import annotations

import enum
import json
import textwrap
from typing import Dict, List, Set, Tuple

FOLD_SECONDS = 60
COMMAND_CHARS = 200
GATE_FORM = "<checkout>/scripts/run_heavy.py"


class Reason(enum.Enum):
    """Why the daemon acts on a process, at most once for each process."""
    ADOPTED = "adopted"
    WARN = "warn"
    MEMORY = "memory"
    CPU = "cpu"
    TIME = "time"
    KILLED = "killed"


def mctx(prose: str) -> str:
    """A string the program puts in an agent's context."""
    return textwrap.dedent(prose).strip()


def short(command: str) -> str:
    return command if len(command) <= COMMAND_CHARS else command[:COMMAND_CHARS] + "..."


def gated_form(command: str, cpus: int, gib: int) -> str:
    """The call that runs `command` under the gate, at the figures measured."""
    return f"{GATE_FORM} --cpus {cpus} --gib {gib} --minutes <m> --need <need> {command}"


def adopted(pid: int, command: str, cpus: int, gib: int) -> str:
    return mctx(
        "pid {pid} (`{command}`) runs in this session outside the gate, at {cpus} CPUs and {gib} "
        "GiB, and now counts against the machine's budget. Stop it and run it as `{form}`, and "
        "add its program to `HEAVY` in scripts/heavy_command_hook.py."
    ).format(pid=pid, command=short(command), cpus=cpus, gib=gib, form=gated_form(command, cpus, gib))


def warned(pid: int, command: str, gib: int) -> str:
    return mctx(
        "The machine's memory pressure is at warn, and nothing new starts. pid {pid} "
        "(`{command}`) runs in this session outside the gate and holds {gib} GiB, and is the "
        "first to be killed if the pressure turns critical."
    ).format(pid=pid, command=short(command), gib=gib)


def memory_overrun(pid: int, command: str, held: int, declared: int) -> str:
    return mctx(
        "pid {pid} (`{command}`) holds {held} GiB, over the {declared} GiB its gate call "
        "declares. It counts as {held} GiB against the budget, and is killed before the jobs "
        "within their declarations if the memory pressure turns critical. Declare at least {held} "
        "with `--gib` the next time."
    ).format(pid=pid, command=short(command), held=held, declared=declared)


def cpu_overrun(pid: int, command: str, used: float, declared: int) -> str:
    return mctx(
        "pid {pid} (`{command}`) has run at {used:.1f} CPUs for a minute, over twice the "
        "{declared} its gate call declares, so a child of it does not honor `ARC_HEAVY_CPUS`."
    ).format(pid=pid, command=short(command), used=used, declared=declared)


def time_overrun(pid: int, command: str, minutes: float, declared: float) -> str:
    return mctx(
        "pid {pid} (`{command}`) has run {minutes:.0f} minutes, over twice the {declared:g} its "
        "gate call declares. Declare more with `--minutes` the next time, so the queue's expected "
        "starts hold."
    ).format(pid=pid, command=short(command), minutes=minutes, declared=declared)


def killed(pid: int, command: str, cpus: int, gib: int, reason: str) -> str:
    return mctx(
        "pid {pid} (`{command}`) and its children were killed: {reason}. It held {gib} GiB. Run "
        "it again as `{form}` once the pressure is gone."
    ).format(pid=pid, command=short(command), gib=gib, reason=reason, form=gated_form(command, cpus, gib))


def message_line(text: str) -> str:
    """The line to write to a session's socket, which delivers `text` as a user message."""
    return json.dumps({"type": "user", "message": {"role": "user", "content": text}}) + "\n"


class Notices:
    """The messages that wait to go out, by session."""

    def __init__(self) -> None:
        self.seen: Set[Tuple[int, float, Reason]] = set()
        self.pending: Dict[str, List[str]] = {}
        self.sent: Dict[str, float] = {}

    def once(self, pid: int, start: float, reason: Reason) -> bool:
        """Whether this is the first call for the process and the reason."""
        key = (pid, start, reason)
        if key in self.seen:
            return False
        self.seen.add(key)
        return True

    def add(self, session: str, text: str) -> None:
        """Queue `text` for `session`."""
        self.pending.setdefault(session, []).append(text)

    def due(self, now: float) -> List[Tuple[str, str]]:
        """Each session that has messages queued and was sent none within `FOLD_SECONDS`, with
        one message that holds its queue."""
        out = []
        for session in sorted(self.pending):
            if session in self.sent and now - self.sent[session] < FOLD_SECONDS:
                continue
            texts = self.pending.pop(session)
            body = texts[0] if len(texts) == 1 else "\n".join(f"{n}. {t}" for n, t in enumerate(texts, 1))
            out.append((session, "Resource daemon: " + body))
            self.sent[session] = now
        return out

    def forget(self, pid: int, start: float) -> None:
        self.seen = {key for key in self.seen if key[:2] != (pid, start)}
