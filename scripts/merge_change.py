"""Merge a worktree's change into `master`.

    uv run python scripts/merge_change.py <worktree> -m <message>

The worktree stands on a branch of its own. The script first sets up the
worktree's git submodules with `git submodule update --init`, cloning each
from the main tree's copy of it under `.git/modules/`, with every transport
but the local one refused, so that the setup uses no network. It then runs
the change's checks in the worktree, on the files as they stand there:

    uv run python -m controlled_markdown check     always
    uv run pyright                                 where the change touches
    uv run pytest -q                               src/, scripts/ or tests/
    uv run python scripts/gate.py <out>

A check passes when it exits 0, and the gate passes only when its last line
is `gate: 0 DIFF, 0 SLOW, 0 NOTIME` as well. The gate writes into a new
temporary directory, which a failing gate names.

When every check passes, the script commits the worktree's uncommitted
changes on its branch with the message given, rebases the branch onto
`master`, fast-forwards `master` in the main tree to the branch, runs
`uv run python scripts/context.py --write` in the main tree, and removes the
worktree and its branch. Since git removes a worktree that holds submodules
only by force, the removal is forced, after a check that the worktree holds
no change against its branch.

The script refuses, and says why, where:

- the submodule setup fails;
- a check fails;
- the main tree has uncommitted changes to a path the change touches;
- the rebase conflicts, in which case it aborts the rebase and leaves the
  worktree as it was before the commit.

It pushes nothing and moves no branch but `master` and the worktree's own.
It prints a line per step on stdout, and a refusal on stderr.

Exit status: 0 when the change is merged, 1 on a refusal or a failed step,
2 when the call itself is malformed.
"""

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

MASTER = "master"
"""The branch a change merges into."""

CODE_DIRS = ("src", "scripts", "tests")
"""The top-level directories whose change runs the code checks."""

GATE_PASS = "gate: 0 DIFF, 0 SLOW, 0 NOTIME"
"""The last line of a gate run that passes."""

TAIL = 40
"""Lines of a failed command's output a refusal shows."""


class Refused(Exception):
    """A reason the script does not merge the change."""


class Failed(Exception):
    """A step that did not complete, and what it left."""


@dataclass(frozen=True)
class Check:
    """A command run in the worktree, and the last line it must print to
    pass, where it must print one."""

    argv: tuple[str, ...]
    last_line: str | None = None


def git(cwd: Path, *argv: str,
        env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    """One git command in `cwd`, in the environment `env` where one is given."""
    return subprocess.run(["git", *argv], cwd=cwd, env=env, capture_output=True,
                          text=True)


def git_out(cwd: Path, *argv: str, env: dict[str, str] | None = None) -> str:
    """The stdout of a git command in `cwd`, which must succeed."""
    done = git(cwd, *argv, env=env)
    if done.returncode != 0:
        raise Failed(f"git {' '.join(argv)} failed in {cwd}: {said(done)}")
    return done.stdout


def said(done: subprocess.CompletedProcess[str]) -> str:
    """What a command wrote, its last `TAIL` lines."""
    lines = (done.stdout + done.stderr).strip().splitlines()
    return "\n".join(lines[-TAIL:]) or f"exit status {done.returncode}"


def main_tree(worktree: Path) -> Path:
    """The main worktree of the repo `worktree` belongs to."""
    common = Path(git_out(worktree, "rev-parse", "--path-format=absolute",
                          "--git-common-dir").strip())
    return common.parent


def branch_of(tree: Path) -> str:
    """The branch checked out in `tree`. A detached HEAD is a refusal."""
    done = git(tree, "symbolic-ref", "--short", "-q", "HEAD")
    if done.returncode != 0:
        raise Refused(f"{tree} stands on no branch")
    return done.stdout.strip()


def changed_paths(tree: Path, base: str) -> set[str]:
    """The paths whose content in `tree` differs from commit `base`: the
    tracked ones, each side of a rename, and the untracked ones git does not
    ignore."""
    names = git_out(tree, "diff", "--name-only", "--no-renames", "-z", base)
    new = git_out(tree, "ls-files", "--others", "--exclude-standard", "-z")
    return {p for p in (names + new).split("\0") if p}


def set_up_submodules(worktree: Path, main: Path) -> None:
    """Run `git submodule update --init` in the worktree, with each
    submodule's URL set to the main tree's copy of its repository, and every
    transport but the local one refused. A failure is a refusal."""
    print("merge_change: setting up the submodules from the main tree", flush=True)
    try:
        listed = git_out(worktree, "config", "-f", ".gitmodules", "-z",
                         "--get-regexp", r"^submodule\..*\.path$")
        overrides: list[str] = []
        for entry in filter(None, listed.split("\0")):
            key = entry.split("\n", 1)[0]
            name = key.removeprefix("submodule.").removesuffix(".path")
            source = git_out(main, "rev-parse", "--path-format=absolute",
                             "--git-path", f"modules/{name}").strip()
            overrides += ["-c", f"submodule.{name}.url={source}"]
        git_out(worktree, *overrides, "submodule", "update", "--init",
                env={**os.environ, "GIT_ALLOW_PROTOCOL": "file"})
    except Failed as exc:
        raise Refused(f"setting up the submodules from {main} failed: {exc}") from exc


def checks(touched: set[str]) -> list[Check]:
    """The checks a change that touches `touched` runs. The gate writes into
    a new temporary directory."""
    run = [Check(("uv", "run", "python", "-m", "controlled_markdown", "check"))]
    if any(p.split("/", 1)[0] in CODE_DIRS for p in touched):
        gate_out = tempfile.mkdtemp(prefix="merge-change-gate-")
        run += [
            Check(("uv", "run", "pyright")),
            Check(("uv", "run", "pytest", "-q")),
            Check(("uv", "run", "python", "scripts/gate.py", gate_out), GATE_PASS),
        ]
    return run


def run_in(tree: Path, argv: Sequence[str]) -> subprocess.CompletedProcess[str]:
    """A `uv run` command in `tree`, in that tree's own environment."""
    env = {k: v for k, v in os.environ.items() if k != "VIRTUAL_ENV"}
    return subprocess.run(list(argv), cwd=tree, env=env, capture_output=True, text=True)


def run_check(worktree: Path, check: Check) -> None:
    """Run `check` in the worktree. A failure is a refusal."""
    shown = " ".join(check.argv)
    print(f"merge_change: running {shown}", flush=True)
    done = run_in(worktree, check.argv)
    lines = done.stdout.strip().splitlines()
    last = lines[-1] if lines else ""
    if done.returncode != 0:
        raise Refused(f"the check `{shown}` failed:\n{said(done)}")
    if check.last_line is not None and last != check.last_line:
        raise Refused(f"the check `{shown}` printed `{last}` as its last line, "
                      f"not `{check.last_line}`:\n{said(done)}")


def refuse_main_touched(main: Path, touched: set[str]) -> None:
    """Refuse where the main tree has uncommitted changes to a path the
    change touches."""
    hit = sorted(changed_paths(main, "HEAD") & touched)
    if hit:
        raise Refused(f"the main tree {main} has uncommitted changes the fast-forward "
                      "would touch:\n" + "\n".join(hit))


def index_file(worktree: Path) -> Path:
    """The worktree's index file."""
    return Path(git_out(worktree, "rev-parse", "--path-format=absolute",
                        "--git-path", "index").strip())


def commit(worktree: Path, message: str, backup: Path) -> None:
    """Commit every uncommitted change of the worktree, with a copy of its
    index kept at `backup` first."""
    shutil.copy2(index_file(worktree), backup)
    git_out(worktree, "add", "-A")
    git_out(worktree, "commit", "-q", "-m", message)


def rebase(worktree: Path, before: str, backup: Path | None) -> None:
    """Rebase the worktree's branch onto `MASTER`. On a conflict, abort the
    rebase, move the branch back to `before`, put back the index kept at
    `backup` where a commit was made, and refuse."""
    done = git(worktree, "rebase", MASTER)
    if done.returncode == 0:
        return
    git_out(worktree, "rebase", "--abort")
    if backup is not None:
        git_out(worktree, "reset", "-q", "--soft", before)
        shutil.copy2(backup, index_file(worktree))
    raise Refused(f"rebasing onto {MASTER} conflicts; the rebase is aborted and the "
                  f"worktree is as it was:\n{said(done)}")


def merge(worktree: Path, message: str) -> None:
    """Merge the worktree's change into `MASTER`, or refuse."""
    main = main_tree(worktree)
    top = Path(git_out(worktree, "rev-parse", "--show-toplevel").strip())
    if top.resolve() != worktree:
        raise Refused(f"{worktree} is no worktree's top directory; {top} is")
    if worktree == main.resolve():
        raise Refused(f"{worktree} is the main tree")
    branch = branch_of(worktree)
    if branch == MASTER:
        raise Refused(f"{worktree} stands on {MASTER}")
    main_branch = branch_of(main)
    if main_branch != MASTER:
        raise Refused(f"the main tree {main} stands on {main_branch}, not {MASTER}")
    base = git_out(worktree, "merge-base", MASTER, "HEAD").strip()
    touched = changed_paths(worktree, base)
    if not touched:
        raise Refused(f"{branch} holds no change against {MASTER}")
    refuse_main_touched(main, touched)

    set_up_submodules(worktree, main)
    for check in checks(touched):
        run_check(worktree, check)

    refuse_main_touched(main, touched)
    before = git_out(worktree, "rev-parse", "HEAD").strip()
    with tempfile.TemporaryDirectory(prefix="merge-change-") as tmp:
        backup = None
        if changed_paths(worktree, "HEAD"):
            backup = Path(tmp) / "index"
            print(f"merge_change: committing on {branch}", flush=True)
            commit(worktree, message, backup)
        print(f"merge_change: rebasing {branch} onto {MASTER}", flush=True)
        rebase(worktree, before, backup)

    print(f"merge_change: fast-forwarding {MASTER} to {branch}", flush=True)
    done = git(main, "merge", "--ff-only", "-q", branch)
    if done.returncode != 0:
        raise Failed(f"fast-forwarding {MASTER} failed; {branch} is committed and "
                      f"rebased in {worktree}:\n{said(done)}")

    print("merge_change: running scripts/context.py --write in the main tree", flush=True)
    done = run_in(main, ("uv", "run", "python", "scripts/context.py", "--write"))
    if done.returncode != 0:
        raise Failed(f"{MASTER} is fast-forwarded, and scripts/context.py --write failed "
                      f"in {main}; {worktree} and {branch} stay:\n{said(done)}")

    print(f"merge_change: removing {worktree} and {branch}", flush=True)
    left = sorted(changed_paths(worktree, "HEAD"))
    if left:
        raise Failed(f"{MASTER} is fast-forwarded, and {worktree} holds changes made "
                     f"after the commit, so it and {branch} stay:\n" + "\n".join(left))
    git_out(main, "worktree", "remove", "--force", str(worktree))
    git_out(main, "branch", "-q", "-d", branch)
    print(f"merge_change: merged {branch} into {MASTER}")


def main(argv: Sequence[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("worktree", type=Path, help="the worktree of the change")
    ap.add_argument("-m", "--message", required=True,
                    help="the message of the commit of the worktree's uncommitted changes")
    a = ap.parse_args(argv)
    worktree = a.worktree.resolve()
    if not worktree.is_dir():
        ap.error(f"{a.worktree} is no directory")
    try:
        merge(worktree, a.message)
    except Refused as exc:
        print(f"merge_change: refused: {exc}", file=sys.stderr)
        return 1
    except Failed as exc:
        print(f"merge_change: failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
