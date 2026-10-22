"""A mode switch shared by the launches of one command run."""

import os
from enum import Enum
from functools import cache
from pathlib import Path

from engine import checkout
from script_calls import SESSION_ENV


class Scope(Enum):
    GLOBAL = "global"
    SESSION = "session"


class ModeSwitch:
    """A main-tree switch whose first read holds for the command run."""

    def __init__(self, name: str, scope: Scope = Scope.GLOBAL):
        self.name = name
        self.scope = scope
        self.override = Path(".cache") / (f"{name}-sessions" if scope is Scope.SESSION else name)

    def path(self, main: Path) -> Path | None:
        if self.scope is Scope.SESSION:
            session = os.environ.get(SESSION_ENV)
            return main / self.override / session if session else None
        return main / self.override

    def read(self, main: Path) -> bool:
        """An absent switch is off. Refuse a file with no switch value."""
        path = self.path(main)
        if path is None:
            return False
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
