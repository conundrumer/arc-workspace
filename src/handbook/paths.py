"""The locations the handbook's readers read and write, from the root of
the checkout."""

from pathlib import Path

from engine import checkout
from solver.vocabulary import LIB_FILE, PROPOSERS_FILE

REPO_ROOT = checkout.ROOT
"""The checkout the readers work in."""


def programs_dir() -> Path:
    return checkout.programs()


def lib_src() -> Path:
    """The lib the runner reads."""
    return programs_dir() / LIB_FILE


def proposers_src() -> Path:
    return programs_dir() / PROPOSERS_FILE
