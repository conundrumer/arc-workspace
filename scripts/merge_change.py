"""Merge a worktree's change into `master`.

    uv run python scripts/merge_change.py <worktree> -m <message>

The worktree stands on a branch of its own. The script first sets up the
worktree's git submodules with `git submodule update --init`, cloning each
from the main tree's copy of it under `.git/modules/`, with every transport
but the local one refused, so that the setup uses no network. It then stages
the worktree's uncommitted changes, commits them on its branch with the
message given, rebases the branch onto `master`, and sets up the submodules
again, for the commits the rebased branch records. It then runs the
change's checks in the worktree, on the change as it will merge:

    uv run python -m controlled_markdown check     always
    uv run pyright                                 where the change touches
    uv run pytest -q                               src/, scripts/ or tests/
    uv run python scripts/gate.py --outputs-only <out>

A check passes when it exits 0. The gate writes into a new temporary
directory, which a failing gate names.

The gate runs with `--outputs-only`, so a merge judges no time. A `SLOW`
line of the timed gate run on `master` that follows a batch of merges is
filed as a `delay` issue, and blocks no merge.

When every check passes, the script fast-forwards `master` in the main
tree to the branch, runs
`uv run python scripts/context.py --write` in the main tree, and removes the
worktree and its branch. Since git removes a worktree that holds submodules
only by force, the removal is forced, after a check that the worktree holds
no change against its branch, counting changes and untracked files inside
its submodules.

The script refuses, and says why, where:

- the submodule setup fails;
- a check, or the submodule setup after the rebase, fails, in which case it
  moves the branch back to the `master` commit it was rebased onto, with
  the change left uncommitted in the worktree and nothing staged;
- the main tree has uncommitted changes to a path the change touches;
- a submodule of the worktree holds changes or untracked files, which no
  commit of the worktree's branch can hold;
- a gitlink in the worktree's index, once the changes are staged, is not
  listed in `.gitmodules`, or names a commit that the main tree's copy of
  that submodule's repository lacks. The removal of the worktree deletes
  the worktree's own copies of the submodules' repositories, so the commit
  would then exist nowhere. The refusal puts the index back as it was.
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

GITLINK_MODE = "160000"
"""The mode git gives an index entry that records a submodule's commit."""

TAIL = 40
"""Lines of a failed command's output a refusal shows."""


class Refused(Exception):
    """A reason the script does not merge the change."""


class Failed(Exception):
    """A step that did not complete, and what it left."""


@dataclass(frozen=True)
class Check:
    """A command run in the worktree."""

    argv: tuple[str, ...]


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
    tracked ones, each side of a rename, the untracked ones git does not
    ignore, and each submodule whose checkout differs from its commit, holds
    changes, or holds untracked files."""
    names = git_out(tree, "diff", "--name-only", "--no-renames",
                    "--ignore-submodules=none", "-z", base)
    new = git_out(tree, "ls-files", "--others", "--exclude-standard", "-z")
    return {p for p in (names + new).split("\0") if p}


@dataclass(frozen=True)
class Submodule:
    """A submodule `.gitmodules` lists: its name, and its path in the tree."""

    name: str
    path: str


def submodules(tree: Path) -> list[Submodule]:
    """The submodules the `.gitmodules` of `tree` lists, in its order."""
    listed = git_out(tree, "config", "-f", ".gitmodules", "-z",
                     "--get-regexp", r"^submodule\..*\.path$")
    found: list[Submodule] = []
    for entry in filter(None, listed.split("\0")):
        key, path = entry.split("\n", 1)
        found.append(Submodule(key.removeprefix("submodule.").removesuffix(".path"), path))
    return found


def main_gitdir(main: Path, sub: Submodule) -> str:
    """The git directory of submodule `sub` in the main tree, which holds
    the main tree's copy of its repository."""
    return git_out(main, "rev-parse", "--path-format=absolute",
                   "--git-path", f"modules/{sub.name}").strip()


def set_up_submodules(worktree: Path, main: Path) -> None:
    """Run `git submodule update --init` in the worktree, with each
    submodule's URL set to the main tree's copy of its repository, and every
    transport but the local one refused. A failure is a refusal."""
    print("merge_change: setting up the submodules from the main tree", flush=True)
    try:
        overrides: list[str] = []
        for sub in submodules(worktree):
            overrides += ["-c", f"submodule.{sub.name}.url={main_gitdir(main, sub)}"]
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
            Check(("uv", "run", "python", "scripts/gate.py", "--outputs-only", gate_out)),
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
    if done.returncode != 0:
        raise Refused(f"the check `{shown}` failed:\n{said(done)}")


def refuse_main_touched(main: Path, touched: set[str]) -> None:
    """Refuse where the main tree has uncommitted changes to a path the
    change touches."""
    hit = sorted(changed_paths(main, "HEAD") & touched)
    if hit:
        raise Refused(f"the main tree {main} has uncommitted changes the fast-forward "
                      "would touch:\n" + "\n".join(hit))


def refuse_dirty_submodules(worktree: Path) -> None:
    """Refuse where a submodule of the worktree holds changes or untracked
    files. A commit of the superproject records only the commit a submodule
    stands on, so that content would not merge, and the removal of the
    worktree would delete it."""
    held: list[str] = []
    for sub in submodules(worktree):
        checkout = worktree / sub.path
        if not checkout.is_dir() or Path(git_out(
                checkout, "rev-parse", "--show-toplevel").strip()) != checkout:
            raise Failed(f"the submodule {sub.path} is not checked out in {worktree}")
        held += sorted(f"{sub.path}/{p}" for p in changed_paths(checkout, "HEAD"))
    if held:
        raise Refused("the worktree's submodules hold changes or untracked files, "
                      "which no commit of its branch can hold:\n" + "\n".join(held))


def gitlinks(tree: Path) -> list[tuple[str, str]]:
    """The gitlinks of the index of `tree`: each one's path and commit, in
    the index's order."""
    found: list[tuple[str, str]] = []
    for entry in filter(None, git_out(tree, "ls-files", "-s", "-z").split("\0")):
        meta, path = entry.split("\t", 1)
        mode, commit, _stage = meta.split(" ")
        if mode == GITLINK_MODE:
            found.append((path, commit))
    return found


def refuse_gitlinks(worktree: Path, main: Path) -> None:
    """Refuse where a gitlink of the worktree's index is not listed in
    `.gitmodules`, or names a commit that the main tree's copy of that
    submodule's repository lacks. The removal of the worktree deletes the
    worktree's own copies of the submodules' repositories, so the commit
    would then exist nowhere."""
    listed = {sub.path: sub for sub in submodules(worktree)}
    unlisted: list[str] = []
    lacked: list[str] = []
    for path, commit in gitlinks(worktree):
        sub = listed.get(path)
        if sub is None:
            unlisted.append(f"{path} {commit}")
        elif git(main, "--git-dir", main_gitdir(main, sub), "cat-file", "-e",
                 f"{commit}^{{commit}}").returncode != 0:
            lacked.append(f"{path} {commit}")
    reasons: list[str] = []
    if unlisted:
        reasons.append("gitlinks that .gitmodules does not list:\n" + "\n".join(unlisted))
    if lacked:
        reasons.append("gitlinks to commits that the main tree's copies of the "
                       "submodules' repositories lack:\n" + "\n".join(lacked))
    if reasons:
        raise Refused("the worktree's index holds commits that the removal of the "
                      "worktree would delete; " + "\n".join(reasons))


def index_file(worktree: Path) -> Path:
    """The worktree's index file."""
    return Path(git_out(worktree, "rev-parse", "--path-format=absolute",
                        "--git-path", "index").strip())


def stage(worktree: Path, main: Path, backup: Path) -> None:
    """Stage every uncommitted change of the worktree, with a copy of its
    index kept at `backup` first, and refuse where `refuse_gitlinks` does,
    with the index put back."""
    shutil.copy2(index_file(worktree), backup)
    git_out(worktree, "add", "-A")
    try:
        refuse_gitlinks(worktree, main)
    except Refused:
        shutil.copy2(backup, index_file(worktree))
        raise


def rebase(worktree: Path, onto: str, before: str, backup: Path | None) -> None:
    """Rebase the worktree's branch onto the commit `onto`. On a conflict,
    abort the rebase, move the branch back to `before`, put back the index
    kept at `backup` where a commit was made, and refuse."""
    done = git(worktree, "rebase", onto)
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
    refuse_dirty_submodules(worktree)
    before = git_out(worktree, "rev-parse", "HEAD").strip()
    onto = git_out(worktree, "rev-parse", MASTER).strip()
    with tempfile.TemporaryDirectory(prefix="merge-change-") as tmp:
        backup = Path(tmp) / "index"
        committing = bool(changed_paths(worktree, "HEAD"))
        stage(worktree, main, backup)
        if committing:
            print(f"merge_change: committing on {branch}", flush=True)
            git_out(worktree, "commit", "-q", "-m", message)
        print(f"merge_change: rebasing {branch} onto {MASTER}", flush=True)
        rebase(worktree, onto, before, backup if committing else None)

    try:
        set_up_submodules(worktree, main)
        for check in checks(touched):
            run_check(worktree, check)
    except Refused as exc:
        git_out(worktree, "reset", "-q", "--mixed", onto)
        raise Refused(f"{exc}\n{branch} is moved back to {MASTER}'s commit {onto[:12]}, "
                      f"and the change stands uncommitted in {worktree}") from exc

    refuse_main_touched(main, touched)

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
