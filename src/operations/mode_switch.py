"""A mode switch shared by the launches of one command run."""

from functools import cache
from pathlib import Path

from engine import checkout


class ModeSwitch:
    """A main-tree switch whose first read holds for the command run."""

    def __init__(self, name: str):
        self.override = Path(".cache") / name

    def read(self, main: Path) -> bool:
        """An absent switch is off. Refuse a file with no switch value."""
        path = main / self.override
        try:
            text = path.read_text().strip()
        except FileNotFoundError:
            return False
        if text not in ("on", "off"):
            raise ValueError(f"{path}: expected on or off")
        return text == "on"

    @cache
    def enabled(self) -> bool:
        """Hold the first read for the command, including its later polls."""
        return self.read(checkout.main_worktree(checkout.ROOT))
