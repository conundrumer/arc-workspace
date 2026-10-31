"""The checks `merge_change.py` runs on the top of its stack, before the
fast-forward under its `--block` and on the landed commit otherwise, and
the steps it runs in the main tree after the fast-forward, run in the tree
this script is run in.

    uv run python scripts/merge_steps.py checks [--engine-passed <commit>] <base> [<gate-out>]
    uv run python scripts/merge_steps.py after [<gate-out>]

The `--help` of `merge_change.py` says which checks and steps these are,
when it runs each form, which copy of this script it runs, and what
`<base>` is. The checks do not read `<base>`. `<gate-out>` is accepted and
unused: the `merge_change.py` on `master` before the gate was removed
passes it. `--engine-passed <commit>` is accepted and unused as well: an
older copy of `merge_change.py` passes it.

`checks` runs the checks concurrently.

Each line that shows a check's name as it starts, and each step line
(`engine.duration.STEP`) a check writes, goes on stderr as it comes, and
the output of each check that fails goes on stdout.

`after` runs the steps in order, stops at the first that fails, and prints
the stdout of each step it runs. For a step that fails, it then prints the
step's command and the last lines of its output.

Exit status: 0 where each check or step passes, 1 where one fails, 2 when
the call itself is malformed.
"""

import argparse
import contextlib
import sys
from collections.abc import Sequence
from pathlib import Path

from engine import checkout
from handbook.paths import scripts_importable

scripts_importable()

from change_checks import Check, failures, run_in, said  # noqa: E402
from operations.merging import CONTEXT_WRITE, DOCUMENT_CHECKS  # noqa: E402

DOCUMENT_PASS = ("scripts/document_pass.py",)
"""The command, after `uv run python`, that files a whole-document pass."""


def checks(tree: Path) -> list[str]:
    """Run the checks in `tree`: the output of each that fails."""
    with contextlib.redirect_stdout(sys.stderr):
        return failures(tree, [*map(Check, DOCUMENT_CHECKS),
                               Check(("uv", "run", "python", "scripts/generate_study_meanings.py",
                                      "--check"))])


def after(tree: Path) -> bool:
    """Run in `tree` the steps after the fast-forward, in order, up to the
    first that fails; whether each passes."""
    for argv in (CONTEXT_WRITE, DOCUMENT_PASS):
        shown = " ".join(argv)
        done = run_in(tree, ("uv", "run", "python", *argv))
        print(done.stdout, end="", flush=True)
        if done.returncode != 0:
            print(f"{shown}:\n{said(done)}", flush=True)
            return False
    return True


def main(argv: Sequence[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    forms = ap.add_subparsers(dest="form", required=True)
    on_checks = forms.add_parser("checks", help="run the checks on the changes")
    on_checks.add_argument("--engine-passed", metavar="COMMIT", help="accepted and unused")
    on_checks.add_argument("base", help="the commit the changes stand on, unused")
    on_checks.add_argument("gate_out", nargs="?", help="accepted and unused")
    on_after = forms.add_parser("after", help="run the steps after the fast-forward")
    on_after.add_argument("gate_out", nargs="?", help="accepted and unused")
    a = ap.parse_args(argv)
    tree = Path(checkout.git_out(Path.cwd(), "rev-parse", "--show-toplevel").strip())
    if a.form == "after":
        return 0 if after(tree) else 1
    failed = checks(tree)
    print("\n".join(failed), end="\n" if failed else "")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
