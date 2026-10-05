"""The locations the handbook's readers read and write, from the root of
the checkout. The documents the readers' contexts are rendered from are
read under `DOCUMENTS_ROOT`, which an environment variable can move."""

import sys
from pathlib import Path

from engine import checkout
from solver.vocabulary import LIB_FILE

REPO_ROOT = checkout.ROOT
"""The checkout the readers work in."""

DOCUMENTS_ENV = "ARC_DOCUMENTS_DIR"
"""The environment variable that names a directory, laid out as the
checkout is, to read the documents the contexts are rendered from in place
of the checkout's root."""

DOCUMENTS_ROOT = checkout.from_env(DOCUMENTS_ENV, checkout.ROOT)
"""The root the documents the contexts are rendered from are read under."""


def document(path: Path) -> Path:
    """`path`, a path in the checkout, as the contexts read it: at the
    same place under `DOCUMENTS_ROOT`."""
    return DOCUMENTS_ROOT / path.relative_to(checkout.ROOT)


def console_importable() -> None:
    """Puts the console's directory on `sys.path`, once, so that
    `solver_console` imports."""
    console = str(checkout.console())
    if console not in sys.path:
        sys.path.insert(0, console)


def lib_src() -> Path:
    """The lib the runner reads."""
    return checkout.programs() / LIB_FILE
