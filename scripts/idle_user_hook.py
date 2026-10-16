"""Stop hook of the main session: blocks the stop, and tells the session the
user is idle, where its last reply asks the user to unblock (`MARK`), an
earlier reply since the user's last message does too, and that message is
older than `IDLE`.

The transcript can be hundreds of MB, so it is read backward from its end
in chunks, up to the user's last message and no further than `CAP` bytes.
Where the cap is reached first, the user is taken as idle since before the
oldest entry read.

A stop the hook blocked is not blocked again (`stop_hook_active`), so a
session that still waits on what cannot be undone can stop."""

import os
import sys
import time
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import NamedTuple

from hook_entry import Hook, not_registered, run_subagent_stop
from subagent_paths import is_subagent

HOOK = "idle_user_hook"
MARK = "**Blocked on you.**"
IDLE = 30 * 60
CHUNK = 1 << 18
CAP = 4 << 20
HUMAN = b'"kind":"human"'
TIMESTAMP = b'"timestamp":"'


def lines_backward(path: str) -> Iterator[bytes]:
    """The whole lines of the file `path`, last first, within `CAP` bytes of
    its end."""
    with open(path, "rb") as f:
        pos = end = f.seek(0, os.SEEK_END)
        rest = b""
        while pos > 0 and end - pos < CAP:
            size = min(CHUNK, pos)
            pos -= size
            f.seek(pos)
            parts = (f.read(size) + rest).split(b"\n")
            rest = parts[0]
            yield from (line for line in reversed(parts[1:]) if line)
        if pos == 0 and rest:
            yield rest


class Scan(NamedTuple):
    """What the end of a transcript gives, back to the user's last message."""
    since: float | None
    """The time of the user's last message, None where the cap was reached
    first."""
    oldest: float | None
    """The time of the oldest entry read."""
    last: str | None
    """The text of the last assistant entry that has text."""
    marked: int
    """The assistant messages since the user's last message whose text holds
    `MARK`."""


def timestamp_of(line: bytes) -> float | None:
    k = line.rfind(TIMESTAMP)
    if k < 0:
        return None
    from transcript_entries import epoch

    k += len(TIMESTAMP)
    return epoch(line[k:line.index(b'"', k)].decode())


def scan(path: str) -> Scan:
    import json

    from run_reads import text_of
    from senders import Origin, origin

    last: str | None = None
    marked: set[str] = set()
    line = b""
    for line in lines_backward(path):
        if last is not None and MARK.encode() not in line and HUMAN not in line:
            continue
        entry = json.loads(line)
        if entry.get("type") == "assistant":
            message = entry.get("message") or {}
            text = text_of(message.get("content"))
            if not text:
                continue
            last = text if last is None else last
            if MARK in text:
                marked.add(message.get("id") or entry.get("uuid"))
        elif origin(entry)[1] is Origin.HUMAN:
            return Scan(timestamp_of(line), None, last, len(marked))
    return Scan(None, timestamp_of(line) if line else None, last, len(marked))


def reason(since: float | None, oldest: float | None, count: int) -> str | None:
    from controlled_markdown import mctx

    def at(t: float) -> str:
        return datetime.fromtimestamp(t, UTC).strftime("%Y-%m-%dT%H:%MZ")

    when = at(since) if since is not None else mctx("before {time}").format(time=at(oldest)) if oldest is not None else None
    if when is None:
        return None
    return mctx(
        "The user has sent no message since {time}, and {count} of your replies since then "
        "ask the user to unblock. The user is idle. Stop waiting: do what you judge best "
        "where it can be undone, and report it. Wait only on what cannot be undone."
    ).format(time=when, count=count)


def check(hook: Hook) -> str | None:
    """The reason to block the stop of the main session `hook` gives, None
    to let it pass."""
    event = hook.get("hook_event_name")
    if event != "Stop":
        raise not_registered("Stop", "event", event)
    path = hook["transcript_path"]
    if hook.get("agent_id") or hook.get("stop_hook_active") or is_subagent(path):
        return None
    found = scan(path)
    count, last = found.marked, found.last
    given = hook.get("last_assistant_message")
    if isinstance(given, str) and given.strip() != (last or "").strip():
        last, count = given, count + (MARK in given)
    if last is None or MARK not in last or count < 2:
        return None
    if found.since is not None and time.time() - found.since <= IDLE:
        return None
    return reason(found.since, found.oldest, count)


if __name__ == "__main__":
    sys.exit(run_subagent_stop(HOOK, check))
