"""Whether the usage limit is lifted, by the usage file of the Claude config
directory, as `operate.py --help next` gives it."""

import json
import os
from pathlib import Path

from controlled_markdown import mctx

USAGE_STALE = 10 * 60
"""How old, in seconds, the usage file (`usage_file`) may be to give the
usage limit as lifted."""


def usage_file() -> Path:
    """The usage file `operate.py --help next` gives."""
    home = os.environ.get("CLAUDE_CONFIG_DIR")
    return (Path(home) if home else Path.home() / ".claude") / "usage.json"


def limit_lifted(now: float, undecided: list[str]) -> float | None:
    """The time of the last write of the usage file, where that file gives
    the usage limit as lifted by the rule `operate.py --help next` gives,
    and otherwise None."""
    path = usage_file()
    try:
        written = path.stat().st_mtime
        windows = json.loads(path.read_text())
    except FileNotFoundError:
        undecided.append(mctx("{path} does not exist, so whether the usage limit is lifted "
                              "is unknown").format(path=path))
        return None
    except (OSError, ValueError) as e:
        undecided.append(mctx("{path}: it does not read as JSON ({why}), so whether "
                              "the usage limit is lifted is unknown").format(path=path, why=e))
        return None
    if now - written >= USAGE_STALE:
        return None
    found = [w.get("used_pct") if isinstance(w, dict) else None
             for w in (windows.values() if isinstance(windows, dict) else [None])]
    used = [u for u in found if isinstance(u, int | float)]
    if not used or len(used) < len(found):
        undecided.append(mctx("{path}: a window of it gives no numeric `used_pct`, so "
                              "whether the usage limit is lifted is unknown").format(path=path))
        return None
    return written if all(u < 100 for u in used) else None
