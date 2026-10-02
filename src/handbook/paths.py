"""The locations the handbook's readers read and write, from the root of
the checkout."""

import sys
from pathlib import Path

from engine import checkout
from solver.vocabulary import LIB_FILE

REPO_ROOT = checkout.ROOT
"""The checkout the readers work in."""


def console_importable() -> None:
    """Puts the console's directory on `sys.path`, once, so that
    `solver_console` imports."""
    console = str(checkout.console())
    if console not in sys.path:
        sys.path.insert(0, console)


def lib_src() -> Path:
    """The lib the runner reads."""
    return checkout.programs() / LIB_FILE

