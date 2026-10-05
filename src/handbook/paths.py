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


def document(path: Path, root: Path = DOCUMENTS_ROOT) -> Path:
    """`path`, a path in the checkout, as the contexts read it under the
    documents root `root`: at the same place under it."""
    return root / path.relative_to(checkout.ROOT)


def importable(directory: Path) -> None:
    """Puts `directory` on `sys.path`, once, so that the modules in it
    import."""
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))


def console_importable() -> None:
    """Puts the console's directory on `sys.path`, so that `solver_console`
    imports."""
    importable(checkout.console())


def lib_src() -> Path:
    """The lib the runner reads."""
    return checkout.programs() / LIB_FILE
