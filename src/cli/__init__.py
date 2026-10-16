"""The commands, each a few lines over the packages below: load the
solver, call the checks, surveys or solve functions it needs, render
through `checker`, and exit by the pass rule. `run.py` dispatches the
`run` command to the modules that hold its forms, and no module imports
it."""

from enum import StrEnum

HELP_FLAGS = ("-h", "--help")


class Command(StrEnum):
    """The commands, each a subparser of `parser.parser`. A script that
    labels a run of `run_dl.py` reads them here without loading the
    packages the commands run."""
    RUN = "run"
    LINT = "lint"
    GRID = "grid"
    RELATION = "relation"
    RECORD = "record"
    SWEEP = "sweep"
    DELETIONS = "deletions"
    AUDIT = "audit"
    DROP_ONE = "drop-one"
    DERIVED_CONSTANT = "derived-constant"
    WITNESS = "witness"
    DERIVE = "derive"
    STORE = "store"
    DETERMINATION_PLAN = "determination-plan"
    SIZE = "size"
    KEYWORDS = "keywords"
    SINCE = "since"
    EXPAND = "expand"


def command_args(argv: list[str]) -> list[str]:
    if not argv or argv[0] not in (*Command, *HELP_FLAGS):
        return [Command.RUN, *argv]
    return argv

