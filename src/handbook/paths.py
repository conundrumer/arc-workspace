"""The locations the handbook's readers read and write, from the root of
the checkout. The documents the readers' contexts are rendered from are
read under `DOCUMENTS_ROOT`."""

import sys
from pathlib import Path

from engine import checkout

REPO_ROOT = checkout.ROOT
"""The checkout the readers work in."""

DOCUMENTS_ROOT = checkout.ROOT
"""The root the documents the contexts are rendered from are read under."""


def document(path: Path, root: Path = DOCUMENTS_ROOT) -> Path:
    """`path`, a path in the checkout, as the contexts read it under the
    documents root `root`: at the same place under it."""
    return root / path.relative_to(checkout.ROOT)


def repo_label(path: Path) -> str:
    """A path as the context prints it: from `DOCUMENTS_ROOT` where it
    stands under it, else from the checkout's root
    (`engine.checkout.shown`)."""
    under = checkout.shown(path, DOCUMENTS_ROOT)
    return str(checkout.shown(path) if under.is_absolute() else under)


def importable(directory: Path) -> None:
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))


def scripts_importable() -> None:
    """`scripts/` is no package, and a script is loaded by its path with
    `scripts/` off `sys.path`, so a script that imports from `scripts/`
    calls this first."""
    importable(checkout.scripts())
