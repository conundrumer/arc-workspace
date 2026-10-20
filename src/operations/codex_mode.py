"""The Codex switch shared by the launches of one command run."""

from functools import cache
from pathlib import Path

from engine import checkout

OVERRIDE = Path(".cache") / "codex"


def read(main: Path) -> bool:
    """An absent switch is off. Refuse a file with no switch value."""
    try:
        text = (main / OVERRIDE).read_text().strip()
    except FileNotFoundError:
        return False
    if text not in ("on", "off"):
        raise ValueError(f"{main / OVERRIDE}: expected on or off")
    return text == "on"


@cache
def enabled() -> bool:
    """Hold the first read for the command, including its later polls."""
    return read(checkout.main_worktree(checkout.ROOT))
