"""Merge the changes of one or more worktrees into `master`.

    uv run python scripts/merge_change.py <worktree> -m <message> [<worktree> -m <message> ...]

The paragraphs below say how the script commits, rebases, checks and lands
the changes, the merge lock it holds, the cases where it refuses a change,
what it prints, and its exit status. The arguments and options follow them.

Each worktree stands on a branch of its own, and the message given after
it is the message of its commit. For each worktree in turn, the script
first sets up the worktree's git submodules with `git submodule update
--init`, cloning each from the main tree's copy of it under `.git/modules/`,
with every transport but the local one refused, so that the setup uses no
network. It then stages the worktree's uncommitted changes and commits them
on its branch with its message.

One invocation at a time merges, across every worktree of the repository:
once the commits are made, the script holds the merge lock
(`engine.rwlock.merge_lock`) until the changes are landed or refused, and an
invocation that finds it held waits for it. So each rebase is onto the
`master` the merge before it left, and the checks run on the changes as
they land. The kernel releases the lock when its holder ends, however it
ends. The merge lock is taken before the shared holds of the heavy
commands' lock that the gate takes for its commands.

The script then rebases the branches, in the order given, onto `master` as
one stack: the first onto `master`, and each next one onto the one before
it. It sets up the submodules of the top of the stack again, for the
commits its branch records, and runs the checks there, on the changes as
they will merge:

    uv run python -m controlled_markdown check     always
    uv run python scripts/gate.py --outputs-only --affected <base> <out>
                                                   always
    uv run pyright                                 where a change touches
    uv run pytest -q                               a path whose content
                                                   their results can depend on

The checks run concurrently. A check passes when it exits 0, and a refusal
names every check that fails. The paths whose content the results of
pyright and pytest can depend on are those under src/, scripts/, tests/
and data/tasks/, those `cli.common.SOURCES` matches, pyproject.toml and
uv.lock. The gate's dependency record decides which of its commands a
change affects, so the gate runs on every change, with `<base>` the
`master` commit the stack is rebased onto. It writes into a new
temporary directory, which a failing gate names. Its `--help` says which
commands `--affected` runs and how the gate's times are judged.

The top of the stack holds every change committed, so where the gate runs
every command, it traces them and writes a dependency record of that
commit into its directory.

When every check passes, the script fast-forwards `master` in the main tree
to the top of the stack, and runs in the main tree
`uv run python scripts/context.py --write` and
`uv run python scripts/gate.py --adopt-record <out>`, with `<out>` the
directory of the gate that checked the stack, so that a record the gate
wrote stands as the dependency record of the new `master`. It then removes
each worktree and its branch.

Where the stack's rebase conflicts or a check fails on the top of the stack,
and the stack holds more than one change, the script moves each branch back
to its commit before the rebase, and then merges the changes one at a time,
in the order given, each as a stack of one: it rebases the branch onto
`master`, runs the checks on it, and fast-forwards `master` to it. So the
change that fails is the one refused, and every check runs on every change
before `master` moves.

Since git removes a worktree that holds submodules only by force, the
removal is forced, after a check that the worktree holds no change against
its branch, counting changes and untracked files inside its submodules. A
worktree locked by a Claude agent, whose lock reason begins with
`AGENT_LOCK`, is removed with the force that a locked worktree needs, after
the same check.

The script ends its output with the duration footer (`engine.duration`).

The script refuses a change, and says why, where:

- the submodule setup fails;
- a check, or the submodule setup after the rebase, fails, in which case it
  moves the branch back to the `master` commit it was rebased onto, with
  the change left uncommitted in the worktree and nothing staged;
- the main tree has uncommitted changes to a path the change touches,
  among them a path the main tree marks skip-worktree whose file there
  is moved away or holds other content than its commit;
- a submodule of the worktree holds changes or untracked files, which no
  commit of the worktree's branch can hold;
- a gitlink in the worktree's index, once the changes are staged, is not
  listed in `.gitmodules`, or names a commit that the main tree's copy of
  that submodule's repository lacks. The removal of the worktree deletes
  the worktree's own copies of the submodules' repositories, so the commit
  would then exist nowhere. The refusal puts the index back as it was.
- the rebase onto `master` conflicts, in which case it aborts the rebase
  and leaves the worktree as it was before the commit;
- another merge holds the merge lock, and the script runs under a hold of
  the heavy commands' lock it inherited, under which it does not wait
  (`engine.rwlock.MergeHeld`), in which case every change is refused, and
  each branch is moved back to the commit it stood on before the script's
  commit, with the change left uncommitted in the worktree and nothing
  staged.

A change refused before the stack is rebased is left out of the stack, and
the others merge.

It pushes nothing and moves no branch but `master` and the worktrees' own.
It prints a line per step on stdout, and a refusal, and a wait for the
merge lock with what its holder merges, on stderr. Each line a check writes
on stderr reaches its stderr as the check writes it, so a wait of the gate
for the heavy commands' lock shows while it lasts.

Exit status: 0 when every change is merged, 1 on a refusal of any change or
a failed step, 2 when the call itself is malformed.
"""

import argparse
import os
import shutil
import sys
import tempfile
import time
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from controlled_markdown import mctx
from engine import checkout, rwlock
from engine.duration import footer
from handbook.paths import importable

# `scripts/` is no package: a test loads this module by its path, with
# `scripts/` off `sys.path`, and `change_checks` imports from there.
importable(checkout.scripts())

from change_checks import (MARKDOWN_CHECK, Check, code_paths,  # noqa: E402
                           failures, run_in, said)

MASTER = "master"
"""The branch a change merges into."""

GITLINK_MODE = "160000"
"""The mode git gives an index entry that records a submodule's commit."""


class Refused(Exception):
    """A reason the script does not merge the change."""


class Failed(Exception):
    """A step that did not complete, and what it left."""


def branch_of(tree: Path) -> str:
    """The branch checked out in `tree`. A detached HEAD is a refusal."""
    done = checkout.git(tree, "symbolic-ref", "--short", "-q", "HEAD")
    if done.returncode != 0:
        raise Refused(f"{tree} stands on no branch")
    return done.stdout.strip()


@dataclass(frozen=True)
class Submodule:
    """A submodule `.gitmodules` lists: its name, and its path in the tree."""

    name: str
    path: str


def submodules(tree: Path) -> list[Submodule]:
    """The submodules the `.gitmodules` of `tree` lists, in its order."""
    listed = checkout.git_out(tree, "config", "-f", ".gitmodules", "-z",
                     "--get-regexp", r"^submodule\..*\.path$")
    found: list[Submodule] = []
    for entry in filter(None, listed.split("\0")):
        key, path = entry.split("\n", 1)
        found.append(Submodule(key.removeprefix("submodule.").removesuffix(".path"), path))
    return found


def main_gitdir(main: Path, sub: Submodule) -> str:
    """The git directory of submodule `sub` in the main tree, which holds
    the main tree's copy of its repository."""
    return checkout.git_out(main, "rev-parse", "--path-format=absolute",
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
        checkout.git_out(worktree, *overrides, "submodule", "update", "--init",
                env={**os.environ, "GIT_ALLOW_PROTOCOL": "file"})
    except checkout.GitFailed as exc:
        raise Refused(f"setting up the submodules from {main} failed: {exc}") from exc


def checked_out(tree: Path, sub: Submodule) -> bool:
    """Whether submodule `sub` is checked out in `tree`: its path is the top
    directory of a repository of its own."""
    path = tree / sub.path
    return path.is_dir() and Path(checkout.git_out(
        path, "rev-parse", "--show-toplevel").strip()) == path


def check(tree: Path, main: Path, base: str, touched: set[str]) -> Path:
    """Run in `tree` the checks of changes from the commit `base` that touch
    `touched`, or refuse; the gate's out-dir."""
    gate_out = tempfile.mkdtemp(prefix="merge-change-gate-")
    gate = Check(("uv", "run", "python", "scripts/gate.py", "--outputs-only", "--affected",
                  base, gate_out))
    code = ([Check(("uv", "run", "pyright")), Check(("uv", "run", "pytest", "-q"))]
            if code_paths(tree, main, touched) else [])
    run_checks(tree, [MARKDOWN_CHECK, gate, *code])
    return Path(gate_out)


def run_checks(tree: Path, checks: Sequence[Check]) -> None:
    """Run `checks` in `tree` concurrently, and refuse where any fails."""
    failed = failures(tree, checks)
    if failed:
        raise Refused("\n".join(failed))


def refuse_main_touched(main: Path, touched: set[str]) -> None:
    """Refuse where the main tree has uncommitted changes to a path the
    change touches."""
    hit = sorted({c.path for c in checkout.changed_paths(main, "HEAD")} & touched)
    if hit:
        raise Refused(f"the main tree {main} has uncommitted changes the fast-forward "
                      "would touch:\n" + "\n".join(hit))


def submodule_changes(worktree: Path) -> list[str]:
    """Each path, from the worktree's root, that a submodule of the worktree
    changes against the commit it stands on, untracked files among them. A
    commit of the superproject records only the commit a submodule stands
    on, so that content would not merge, and the removal of the worktree
    would delete it. A submodule that is not checked out is a fault."""
    held: list[str] = []
    for sub in submodules(worktree):
        if not checked_out(worktree, sub):
            raise Failed(f"the submodule {sub.path} is not checked out in {worktree}")
        held += sorted(f"{sub.path}/{c.path}" for c in checkout.changed_paths(worktree / sub.path, "HEAD"))
    return held


def refuse_dirty_submodules(worktree: Path) -> None:
    """Refuse where a submodule of the worktree holds changes or untracked
    files (`submodule_changes`)."""
    held = submodule_changes(worktree)
    if held:
        raise Refused("the worktree's submodules hold changes or untracked files, "
                      "which no commit of its branch can hold:\n" + "\n".join(held))


def gitlinks(tree: Path) -> list[tuple[str, str]]:
    """The gitlinks of the index of `tree`: each one's path and commit, in
    the index's order."""
    found: list[tuple[str, str]] = []
    for entry in filter(None, checkout.git_out(tree, "ls-files", "-s", "-z").split("\0")):
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
        elif checkout.git(main, "--git-dir", main_gitdir(main, sub), "cat-file", "-e",
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
    return Path(checkout.git_out(worktree, "rev-parse", "--path-format=absolute",
                        "--git-path", "index").strip())


def stage(worktree: Path, main: Path, backup: Path) -> None:
    """Stage every uncommitted change of the worktree, with a copy of its
    index kept at `backup` first, and refuse where `refuse_gitlinks` does,
    with the index put back."""
    shutil.copy2(index_file(worktree), backup)
    checkout.git_out(worktree, "add", "-A")
    try:
        refuse_gitlinks(worktree, main)
    except Refused:
        shutil.copy2(backup, index_file(worktree))
        raise


@dataclass(frozen=True)
class Change:
    """A worktree's change, committed on its branch: `before` is the commit
    the branch stood on before the script's commit, `backup` the copy of the
    index kept before the staging where the script made a commit, and
    `committed` the commit the branch stands on after it."""

    worktree: Path
    branch: str
    touched: frozenset[str]
    before: str
    backup: Path | None
    committed: str


def rebase(change: Change, onto: str, onto_name: str, restore: bool) -> None:
    """Rebase the change's branch onto the commit `onto`, which `onto_name`
    names. On a conflict, abort the rebase, which leaves the branch at
    `committed`; with `restore`, move it back to `before` and put back the
    index at `backup`; and refuse."""
    print(mctx("merge_change: rebasing {branch} onto {onto}").format(
        branch=change.branch, onto=onto_name), flush=True)
    done = checkout.git(change.worktree, "rebase", onto)
    if done.returncode == 0:
        return
    checkout.git_out(change.worktree, "rebase", "--abort")
    if restore and change.backup is not None:
        checkout.git_out(change.worktree, "reset", "-q", "--soft", change.before)
        shutil.copy2(change.backup, index_file(change.worktree))
    raise Refused(mctx("rebasing {branch} onto {onto} conflicts; the rebase is aborted "
                       "and the worktree is as it was:").format(
        branch=change.branch, onto=onto_name) + "\n" + said(done))


def commit(worktree: Path, message: str, main: Path, backup: Path) -> Change:
    """The worktree's change, with its uncommitted changes committed on its
    branch with `message`, and a copy of its index kept at `backup` first;
    or a refusal."""
    top = Path(checkout.git_out(worktree, "rev-parse", "--show-toplevel").strip())
    if top.resolve() != worktree:
        raise Refused(f"{worktree} is no worktree's top directory; {top} is")
    if worktree == main.resolve():
        raise Refused(f"{worktree} is the main tree")
    branch = branch_of(worktree)
    if branch == MASTER:
        raise Refused(f"{worktree} stands on {MASTER}")
    base = checkout.git_out(worktree, "merge-base", MASTER, "HEAD").strip()
    touched = {c.path for c in checkout.changed_paths(worktree, base)}
    if not touched:
        raise Refused(f"{branch} holds no change against {MASTER}")
    refuse_main_touched(main, touched)

    set_up_submodules(worktree, main)
    refuse_dirty_submodules(worktree)
    before = checkout.git_out(worktree, "rev-parse", "HEAD").strip()
    committing = bool(checkout.changed_paths(worktree, "HEAD"))
    stage(worktree, main, backup)
    if committing:
        print(f"merge_change: committing on {branch}", flush=True)
        checkout.git_out(worktree, "commit", "-q", "-m", message)
    return Change(worktree, branch, frozenset(touched), before,
                  backup if committing else None,
                  checkout.git_out(worktree, "rev-parse", "HEAD").strip())


def touched_by(changes: Sequence[Change]) -> set[str]:
    return {p for c in changes for p in c.touched}


def stack(main: Path, changes: Sequence[Change]) -> Path:
    """Rebase the branches of `changes`, in order, onto `MASTER` as one
    stack, and run the checks on its top, or refuse; the gate's out-dir. A
    refusal leaves each branch at `committed`."""
    base = onto = checkout.git_out(main, "rev-parse", MASTER).strip()
    names = [MASTER, *(c.branch for c in changes[:-1])]
    try:
        for c, onto_name in zip(changes, names, strict=True):
            rebase(c, onto, onto_name, restore=False)
            onto = checkout.git_out(c.worktree, "rev-parse", "HEAD").strip()
        top = changes[-1].worktree
        set_up_submodules(top, main)
        return check(top, main, base, touched_by(changes))
    except Refused:
        for c in changes:
            unstack(c)
        raise


def unstack(change: Change) -> None:
    """Move the change's branch back to `committed`. The worktree holds
    every change of its branch's commits after the stack's rebase, so the
    hard reset loses none where it holds no change against the branch."""
    if checkout.git_out(change.worktree, "rev-parse", "HEAD").strip() == change.committed:
        return
    left = sorted(c.path for c in checkout.changed_paths(change.worktree, "HEAD"))
    if left:
        raise Failed(mctx("{worktree} holds changes made after the stack's rebase, so "
                          "{branch} stays rebased:").format(
            worktree=change.worktree, branch=change.branch) + "\n" + "\n".join(left))
    checkout.git_out(change.worktree, "reset", "-q", "--hard", change.committed)


def merge_alone(main: Path, change: Change) -> None:
    """Rebase the change's branch onto `MASTER`, run the checks on it, and
    land it, or refuse."""
    onto = checkout.git_out(main, "rev-parse", MASTER).strip()
    rebase(change, onto, MASTER, restore=True)
    try:
        set_up_submodules(change.worktree, main)
        gate_out = check(change.worktree, main, onto, set(change.touched))
    except Refused as exc:
        checkout.git_out(change.worktree, "reset", "-q", "--mixed", onto)
        raise Refused(f"{exc}\n{change.branch} is moved back to {MASTER}'s commit "
                      f"{onto[:12]}, and the change stands uncommitted in "
                      f"{change.worktree}") from exc
    land(main, [change], gate_out)


AGENT_LOCK = "claude agent "
"""The start of the lock reason of a worktree a Claude agent works in."""


def lock_reasons(main: Path) -> dict[Path, str | None]:
    """Each worktree `git worktree list` gives, with the reason for its
    lock: the empty string for a lock with no reason, and None where it is
    not locked."""
    reasons: dict[Path, str | None] = {}
    at: Path | None = None
    for field in checkout.git_out(main, "worktree", "list", "--porcelain", "-z").split("\0"):
        if field.startswith("worktree "):
            at = Path(field.removeprefix("worktree ")).resolve()
            reasons[at] = None
        elif at is not None and (field == "locked" or field.startswith("locked ")):
            reasons[at] = field.removeprefix("locked").removeprefix(" ")
    return reasons


def remove(main: Path, change: Change) -> None:
    """Remove the change's worktree and branch, or fail where the worktree
    holds a change against its branch, or a submodule of it holds changes
    or untracked files."""
    worktree, branch = change.worktree, change.branch
    print(mctx("merge_change: removing {worktree} and {branch}").format(
        worktree=worktree, branch=branch), flush=True)

    def stays(why: str) -> Failed:
        return Failed(mctx("{master} is fast-forwarded, and {why}, so {worktree} and "
                           "{branch} stay").format(
            master=MASTER, why=why, worktree=worktree, branch=branch))

    left = sorted(c.path for c in checkout.changed_paths(worktree, "HEAD"))
    left += submodule_changes(worktree)
    if left:
        raise stays(mctx("the worktree holds changes made after the commit, in {left}")
                    .format(left=", ".join(left)))
    reasons = lock_reasons(main)
    if worktree not in reasons:
        raise stays(mctx("git worktree list does not list the worktree"))
    force = ["--force"]
    reason = reasons[worktree]
    if reason is not None:
        if not reason.startswith(AGENT_LOCK):
            raise stays(mctx("the worktree is locked for a reason no Claude agent gives: "
                             "`{reason}`").format(reason=reason))
        force = ["--force", "--force"]
    checkout.git_out(main, "worktree", "remove", *force, str(worktree))
    checkout.git_out(main, "branch", "-q", "-d", branch)


def land(main: Path, changes: Sequence[Change], gate_out: Path) -> None:
    """Fast-forward `MASTER` to the top of `changes`, write the context in
    the main tree, adopt the dependency record the gate wrote into
    `gate_out`, and remove each change's worktree and branch."""
    refuse_main_touched(main, touched_by(changes))
    top = changes[-1].branch
    print(f"merge_change: fast-forwarding {MASTER} to {top}", flush=True)
    done = checkout.git(main, "merge", "--ff-only", "-q", top)
    if done.returncode != 0:
        raise Failed(f"fast-forwarding {MASTER} failed; {top} is committed and "
                     f"rebased in {changes[-1].worktree}:\n{said(done)}")

    for argv in (("scripts/context.py", "--write"),
                 ("scripts/gate.py", "--adopt-record", str(gate_out))):
        shown = " ".join(argv)
        print(mctx("merge_change: running {shown} in the main tree").format(shown=shown),
              flush=True)
        done = run_in(main, ("uv", "run", "python", *argv))
        if done.returncode != 0:
            raise Failed(mctx("{master} is fast-forwarded, and {shown} failed in {main}; the "
                              "worktrees and branches of {branches} stay:").format(
                master=MASTER, shown=shown, main=main,
                branches=", ".join(c.branch for c in changes)) + "\n" + said(done))
        print(done.stdout, end="", flush=True)

    failed: list[str] = []
    for c in changes:
        try:
            remove(main, c)
        except (Failed, checkout.GitFailed) as exc:
            failed.append(str(exc))
        else:
            print(f"merge_change: merged {c.branch} into {MASTER}", flush=True)
    if failed:
        raise Failed("\n".join(failed))


def print_refusal(exc: Refused) -> None:
    print(f"merge_change: refused: {exc}", file=sys.stderr, flush=True)


def merge(pairs: Sequence[tuple[Path, str]]) -> bool:
    """Merge each worktree's change into `MASTER`, committed with its
    message, under the merge lock (`land_all`). Whether every change
    merged."""
    try:
        mains = [checkout.main_worktree(w) for w, _ in pairs]
    except checkout.GitFailed as exc:
        raise Refused(str(exc)) from exc
    main = mains[0]
    others = sorted({str(m) for m in mains} - {str(main)})
    if others:
        raise Refused(mctx("the worktrees belong to more than one repository: {main}, "
                           "{others}").format(main=main, others=", ".join(others)))
    main_branch = branch_of(main)
    if main_branch != MASTER:
        raise Refused(f"the main tree {main} stands on {main_branch}, not {MASTER}")
    every = True
    with tempfile.TemporaryDirectory(prefix="merge-change-") as tmp:
        changes: list[Change] = []
        for i, (worktree, message) in enumerate(pairs):
            try:
                changes.append(commit(worktree, message, main, Path(tmp) / f"index-{i}"))
            except Refused as exc:
                print_refusal(exc)
                every = False
        if not changes:
            return every
        holder = mctx("pid {pid}, since {since}, merging {branches}").format(
            pid=os.getpid(), since=time.strftime("%H:%M:%S"),
            branches=", ".join(c.branch for c in changes))
        try:
            with rwlock.merge_lock(checkout.git_common_dir(main), holder):
                print("merge_change: holding the merge lock", flush=True)
                return land_all(main, changes) and every
        except rwlock.MergeHeld as exc:
            for c in changes:
                checkout.git_out(c.worktree, "reset", "-q", "--mixed", c.before)
            raise Refused(mctx("{exc} Each branch is moved back to the commit it stood on "
                               "before, and its change stands uncommitted in its "
                               "worktree.").format(exc=exc)) from exc


def land_all(main: Path, changes: Sequence[Change]) -> bool:
    """Merge the committed `changes` into `MASTER`: as one stack, or, where
    the stack is refused, one at a time. Whether every change merged."""
    if len(changes) > 1:
        try:
            gate_out = stack(main, changes)
        except Refused as exc:
            print(mctx("merge_change: the stack is refused, so the changes merge one "
                       "at a time:") + "\n" + str(exc), flush=True)
        else:
            land(main, changes, gate_out)
            return True
    every = True
    for c in changes:
        try:
            merge_alone(main, c)
        except Refused as exc:
            print_refusal(exc)
            every = False
    return every


def main(argv: Sequence[str]) -> int:
    with footer("merge_change"):
        return merge_main(argv)


def merge_main(argv: Sequence[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("worktree", type=Path, nargs="+", help="the worktree of a change")
    ap.add_argument("-m", "--message", action="append", required=True,
                    help="the message of the commit of the uncommitted changes of the "
                         "worktree it follows")
    a = ap.parse_intermixed_args(argv)
    if len(a.worktree) != len(a.message):
        ap.error(mctx("{w} worktrees are given with {m} messages").format(
            w=len(a.worktree), m=len(a.message)))
    worktrees: list[Path] = [w.resolve() for w in a.worktree]
    for given, w in zip(a.worktree, worktrees, strict=True):
        if not w.is_dir():
            ap.error(f"{given} is no directory")
    if len(set(worktrees)) != len(worktrees):
        ap.error(mctx("a worktree is given twice"))
    try:
        merged = merge(list(zip(worktrees, a.message, strict=True)))
    except Refused as exc:
        print_refusal(exc)
        return 1
    except (Failed, checkout.GitFailed) as exc:
        print(f"merge_change: failed: {exc}", file=sys.stderr)
        return 1
    return 0 if merged else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
