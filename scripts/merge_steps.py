"""The checks `merge_change.py` runs on the top of its stack, and the steps
it runs in the main tree after the fast-forward, run in the tree this
script is run in.

    uv run python scripts/merge_steps.py checks <base> <gate-out>
    uv run python scripts/merge_steps.py after <gate-out>

The `--help` of `merge_change.py` says which checks and steps these are,
when it runs each form, which copy of this script it runs, and what
`<base>` and `<gate-out>` are.

`checks` runs the checks concurrently. Each line that shows a check's
name as it starts, and each step line (`engine.duration.STEP`) a check
writes, goes on stderr as it comes, and the output of each check that
fails goes on stdout.

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

from change_checks import Check, changed_outside_work, failures, run_in, said  # noqa: E402
from operations.merging import CONTEXT_WRITE, DOCUMENT_CHECKS  # noqa: E402

DOCUMENT_PASS = ("scripts/document_pass.py",)
"""The command, after `uv run python`, that files a whole-document pass."""

ENGINE = "engine/"
"""The directory of the Cargo workspace."""

ENGINE_CHECK = ("cargo", "test", "--manifest-path", f"{ENGINE}Cargo.toml",
                "--workspace", "--offline", "--no-fail-fast")
"""The check that compiles every target of each crate of the workspace
under `ENGINE`, from the crates already fetched, and runs every test of
those crates, giving each test that fails."""

ENGINE_DOC_CHECK = ("env", "RUSTDOCFLAGS=-D warnings", "cargo", "doc", "--manifest-path",
                    f"{ENGINE}Cargo.toml", "--workspace", "--no-deps", "--offline")
"""The check that builds the documentation of each crate of the workspace
under `ENGINE`, from the crates already fetched, and fails on each
rustdoc warning, such as a link from a public item's doc to a private
item."""


def checks(tree: Path, base: str, gate_out: str) -> list[str]:
    """Run in `tree` the checks of changes from the commit `base`: the
    output of each that fails. The compile and the tests of the engine
    (`ENGINE_CHECK`) and its documentation build (`ENGINE_DOC_CHECK`) are
    among them where the changes touch a path under `ENGINE`."""
    engine = any(p.startswith(ENGINE) for p in changed_outside_work(tree, base))
    with contextlib.redirect_stdout(sys.stderr):
        return failures(tree, [*map(Check, DOCUMENT_CHECKS),
                               Check(("uv", "run", "python", "scripts/gate.py", "--affected", base, gate_out)),
                               *(map(Check, (ENGINE_CHECK, ENGINE_DOC_CHECK)) if engine else ())])


def after(tree: Path, gate_out: str) -> bool:
    """Run in `tree` the steps after the fast-forward, in order, up to the
    first that fails; whether each passes."""
    for argv in (CONTEXT_WRITE, DOCUMENT_PASS, ("scripts/gate.py", "--adopt", gate_out)):
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
    on_checks.add_argument("base", help="the commit the changes stand on")
    on_checks.add_argument("gate_out", help="the gate's out-dir")
    on_after = forms.add_parser("after", help="run the steps after the fast-forward")
    on_after.add_argument("gate_out", help="the out-dir of the gate that checked the changes")
    a = ap.parse_args(argv)
    tree = Path(checkout.git_out(Path.cwd(), "rev-parse", "--show-toplevel").strip())
    if a.form == "after":
        return 0 if after(tree, a.gate_out) else 1
    failed = checks(tree, a.base, a.gate_out)
    print("\n".join(failed), end="\n" if failed else "")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
