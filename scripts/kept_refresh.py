"""Have the resident of each session read the state, so that the first
`operate.py next` call of the session after a merge reads the reads of the
new code from the store and does not compute them.

    uv run python scripts/kept_refresh.py [<session> ...]

`scripts/merge_change.py` runs it once its fast-forward has landed and its
refresh locks (`refresh_locks`) are released, with the sessions it locked,
the merging session first. For each session where an operator ran
`operate.py next`, the script starts the session's resident service where
none runs, and asks it to read the state of that session's last operator.
The resident answers once it accepts the request, and the read goes on in
the resident: a `next` call that arrives during it waits in the resident's
queue, and gets the step, or the line that says the read runs, within its
bound. The script does not wait for a read. It exits 1 where a session's
request failed, after it has asked every other session.

It prints no step and starts no run."""

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from handbook.paths import scripts_importable

scripts_importable()

import operate_service  # noqa: E402
from operator_reads import operator_runs  # noqa: E402
from tree_reads import main_tree  # noqa: E402


def refresh_session(main: Path, session: str) -> None:
    """Have the resident of `session` read the state of the session's last operator."""
    runs = operator_runs(session, "")
    if runs:
        operate_service.refresh_resident(main, session, runs[-1][0])


def refresh(main: Path, sessions: Sequence[str]) -> bool:
    """Ask the resident of each session of `sessions`, in order, and whether every request was accepted."""
    done = True
    for session in sessions:
        try:
            refresh_session(main, session)
        except (OSError, ValueError, RuntimeError, operate_service.Expired,
                operate_service.Unavailable) as exc:
            print(f"kept_refresh: {session}: {exc}", file=sys.stderr)
            done = False
    return done


def main(argv: Sequence[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("sessions", nargs="*", metavar="SESSION", help="a session whose resident reads the state")
    return 0 if refresh(main_tree(), ap.parse_args(argv).sessions) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
