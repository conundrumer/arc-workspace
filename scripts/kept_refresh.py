"""Write into the store of `kept_reads` the state reads of the sessions a
merge hands over, so that the first `operate.py next` call of each session
after the merge reads them from the store and does not compute them.

    uv run python scripts/kept_refresh.py [--held <session> <fd> ...]
    uv run python scripts/kept_refresh.py read <operator>

`scripts/merge_change.py` runs the first form once the merge lock is
released, with each `--held` an open descriptor `<fd>` of the refresh lock
of `<session>` (`refresh_locks`), locked since before the merge's
fast-forward, and the merging session's first. The script refreshes each
session through its resident service, where one owns it, and otherwise by
a child of the second form with `CLAUDE_CODE_SESSION_ID` set to that
session. It releases the session's lock once that refresh ends, whether
the resident or the child did it. A session where no operator ran
`operate.py next` has no child.

The second form opens the store, reads the state of `<operator>` in the
session `CLAUDE_CODE_SESSION_ID` gives (`state_assembly.read_state`), and
writes the store's records at its exit.

Neither form prints a step or starts a run."""

import argparse
import os
import subprocess
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import IO

import script_calls
from handbook.paths import scripts_importable

scripts_importable()

import kept_reads  # noqa: E402
import operate_service  # noqa: E402
import state_assembly  # noqa: E402
from operator_reads import operator_runs  # noqa: E402
from refresh_locks import REFRESH  # noqa: E402
from tree_reads import main_tree  # noqa: E402


def refresh_session(main: Path, session: str) -> None:
    """Refresh the last operator of `session` through its resident or a child."""
    runs = operator_runs(session, "")
    if runs:
        def standalone() -> None:
            subprocess.run(("uv", "run", "python", *REFRESH, "read", runs[-1][0]), cwd=main,
                           env={**os.environ, script_calls.SESSION_ENV: session},
                           stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL)
        operate_service.refresh_resident(main, session, runs[-1][0], standalone)


def refresh(main: Path, held: Mapping[str, IO[str]]) -> None:
    """Refreshes each session of `held`, in its order, closing its lock's
    file once its resident or child refresh ends, as the module docstring gives."""
    locks = dict(held)
    try:
        for session in list(locks):
            try:
                refresh_session(main, session)
            finally:
                locks.pop(session).close()
    finally:
        for f in locks.values():
            f.close()


def read(operator: str) -> None:
    """The child: reads the state of `operator` with the store open."""
    kept_reads.open_store()
    try:
        state_assembly.read_state(operator)
    finally:
        kept_reads.flush()


def main(argv: Sequence[str]) -> int:
    if argv[:1] == ["read"]:
        ap = argparse.ArgumentParser(prog="kept_refresh.py read")
        ap.add_argument("operator", help="the agent id of the operator whose state is read")
        read(ap.parse_args(argv[1:]).operator)
        return 0
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--held", nargs=2, action="append", default=[], metavar=("SESSION", "FD"),
                    help="a session and the descriptor of its refresh lock, held")
    a = ap.parse_args(argv)
    refresh(main_tree(), {s: os.fdopen(int(fd), "a") for s, fd in a.held})
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
