"""Whether the usage limit is lifted, by the usage file of the Claude config
directory, as `operate.py --help next` gives it, and the `pacing.Usage`
that file gives."""

import json
from pathlib import Path
from typing import Any

from claude_config import config_dir
from controlled_markdown import mctx
from operations.pacing import Usage, Window

USAGE_STALE = 10 * 60
"""How old, in seconds, the usage file (`usage_file`) may be to give the
usage limit as lifted, or a window to a `Usage`."""


def usage_file() -> Path:
    """The usage file `operate.py --help next` gives."""
    return config_dir() / "usage.json"


def read_usage(now: float, undecided: list[str]) -> tuple[float | None, Usage]:
    """The time of the last write of the usage file, where that file gives
    the usage limit as lifted by the rule `operate.py --help next` gives,
    and otherwise None; with the `Usage` at `now` it gives, each window of
    it with a number in each field, where it was written less than
    `USAGE_STALE` seconds ago."""
    path = usage_file()
    try:
        written = path.stat().st_mtime
        windows = json.loads(path.read_text())
    except FileNotFoundError:
        undecided.append(mctx("{path} does not exist, so whether the usage limit is lifted "
                              "is unknown").format(path=path))
        return None, Usage(now, {})
    except (OSError, ValueError) as e:
        undecided.append(mctx("{path}: it does not read as JSON ({why}), so whether "
                              "the usage limit is lifted is unknown").format(path=path, why=e))
        return None, Usage(now, {})
    if now - written >= USAGE_STALE:
        return None, Usage(now, {})
    return lifted(path, written, windows, undecided), Usage(now, read_windows(windows))


def read_windows(windows: Any) -> dict[str, Window]:
    out: dict[str, Window] = {}
    for name, w in (windows.items() if isinstance(windows, dict) else []):
        fields = [w.get(k) if isinstance(w, dict) else None
                  for k in ("used_pct", "elapsed_pct", "resets_at_epoch")]
        numbers = [float(f) for f in fields if isinstance(f, int | float)]
        if len(numbers) == len(fields):
            out[name] = Window(*numbers)
    return out


def lifted(path: Path, written: float, windows: Any, undecided: list[str]) -> float | None:
    found = [w.get("used_pct") if isinstance(w, dict) else None
             for w in (windows.values() if isinstance(windows, dict) else [None])]
    used = [u for u in found if isinstance(u, int | float)]
    if not used or len(used) < len(found):
        undecided.append(mctx("{path}: a window of it gives no numeric `used_pct`, so "
                              "whether the usage limit is lifted is unknown").format(path=path))
        return None
    return written if all(u < 100 for u in used) else None
