"""Whether the usage limit is lifted, by the usage cache of the Claude config
directory, as `operate.py --help next` gives it, and the `pacing.Usage`
that cache gives. A read first refreshes the cache (`refresh`)."""

import json
import re
import subprocess
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from claude_config import config_dir
from controlled_markdown import mctx
from operations.pacing import WINDOW_SECONDS, Usage, Window, WindowName, iso_time

USAGE_STALE = 10 * 60
"""How old, in seconds, the reading of the usage cache (`usage_file`) may
be to give the usage limit as lifted, or a window to a `Usage`."""

FETCH = Path.home() / ".claude" / "scripts" / "fetch-usage-api.sh"
"""The script that writes the usage cache, at most once in `FETCH_TTL`
seconds."""

FETCH_TTL = 300
"""The age, in seconds, from which `FETCH` fetches the cache again."""

FETCH_TIMEOUT = 15
"""How long, in seconds, a read waits on `FETCH`, a little over the 10 s
its `curl --max-time` gives."""

FABLE = re.compile("fable", re.IGNORECASE)
"""The model name of the `limits` entry that gives the `fable_weekly`
window."""


def usage_file() -> Path:
    """The usage cache `operate.py --help next` gives."""
    return config_dir() / "usage-api.json"


class Limit(Enum):
    """What a reading gives of the usage limit: in force (a fresh reading
    with a window at `used_pct` 100 or more), lifted (a fresh reading
    with each window under 100), or unknown (no fresh reading, or a window
    it cannot read)."""
    IN_FORCE = "in force"
    LIFTED = "lifted"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class Reading:
    """A reading of the usage cache: what it gives of the limit, the time
    of its fetch, where it gives one, and the `Usage` it gives."""
    limit: Limit
    fetched: float | None
    usage: Usage


def refresh(now: float) -> None:
    """Runs `FETCH`, under `FETCH_TIMEOUT`, where the usage cache is
    missing or its fetch is at least `FETCH_TTL` seconds old. A run that
    fails leaves the cache as it was."""
    try:
        fetched = json.loads(usage_file().read_text())["fetched_at"]
        if isinstance(fetched, int | float) and now - fetched < FETCH_TTL:
            return
    except (OSError, ValueError, KeyError, TypeError):
        pass
    try:
        subprocess.run(["bash", str(FETCH)], capture_output=True, timeout=FETCH_TIMEOUT,
                       check=False)
    except (OSError, subprocess.TimeoutExpired):
        pass


def read(now: float, undecided: list[str]) -> Reading:
    """The reading of the usage cache at `now`, once `refresh` has run,
    adding to `undecided` why the limit is unknown where the cache is
    missing or a part of it does not read."""
    refresh(now)
    path = usage_file()
    unknown = Reading(Limit.UNKNOWN, None, Usage(now, {}))
    try:
        cache = json.loads(path.read_text())
    except FileNotFoundError:
        undecided.append(mctx("{path} does not exist, so whether the usage limit is lifted "
                              "is unknown").format(path=path))
        return unknown
    except (OSError, ValueError) as e:
        undecided.append(mctx("{path}: it does not read as JSON ({why}), so whether "
                              "the usage limit is lifted is unknown").format(path=path, why=e))
        return unknown
    fetched = cache.get("fetched_at") if isinstance(cache, dict) else None
    if not isinstance(fetched, int | float):
        undecided.append(mctx("{path}: it gives no numeric `fetched_at`, so whether the usage "
                              "limit is lifted is unknown").format(path=path))
        return unknown
    if now - fetched >= USAGE_STALE:
        return unknown
    windows = read_windows(cache.get("data"), now)
    if not windows:
        undecided.append(mctx("{path}: it gives no window that reads, so whether "
                              "the usage limit is lifted is unknown").format(path=path))
        return unknown
    limit = Limit.LIFTED if all(w.used_pct < 100 for w in windows.values()) else Limit.IN_FORCE
    return Reading(limit, fetched, Usage(now, windows))


def read_usage(now: float, undecided: list[str]) -> tuple[float | None, Usage]:
    """The time of the fetch of the usage cache, where `read` gives the
    usage limit as lifted, and otherwise None; with the `Usage` it gives."""
    r = read(now, undecided)
    return (r.fetched if r.limit is Limit.LIFTED else None), r.usage


def read_windows(data: Any, now: float) -> dict[str, Window] | None:
    """Each window of the usage API's response `data` that is not `null`,
    by its `WindowName`, or None where one does not read."""
    if not isinstance(data, dict):
        return None
    found: dict[WindowName, Any] = {WindowName.FIVE_HOUR: data.get("five_hour"),
                                    WindowName.SEVEN_DAY: data.get("seven_day")}
    limits = data.get("limits")
    fable = [e for e in (limits if isinstance(limits, list) else [])
             if isinstance(e, dict) and FABLE.search(model_name(e)) is not None]
    found[WindowName.FABLE_WEEKLY] = fable[0] if fable else None
    out: dict[str, Window] = {}
    for name, raw in found.items():
        if raw is None:
            continue
        w = window(raw, "percent" if name is WindowName.FABLE_WEEKLY else "utilization",
                   WINDOW_SECONDS[name], now)
        if w is None:
            return None
        out[name] = w
    return out


def model_name(entry: dict[str, Any]) -> str:
    scope = entry.get("scope")
    model = scope.get("model") if isinstance(scope, dict) else None
    name = model.get("display_name") if isinstance(model, dict) else None
    return name if isinstance(name, str) else ""


def window(raw: Any, used_key: str, seconds: int, now: float) -> Window | None:
    """The `Window` at `now` of the API's window `raw`, whose used share is
    `used_key` and whose length is `seconds`: its `elapsed_pct` from its
    `resets_at`, and, once that time has passed, a `used_pct` of 0. None
    where `raw` does not read."""
    used = raw.get(used_key) if isinstance(raw, dict) else None
    resets = raw.get("resets_at") if isinstance(raw, dict) else None
    if not isinstance(used, int | float) or not isinstance(resets, str):
        return None
    try:
        at = iso_time(resets)
    except ValueError:
        return None
    elapsed = min(100.0, max(0.0, 100 * (now - (at - seconds)) / seconds))
    return Window(0.0 if at <= now else float(used), elapsed, at)
