"""Merge the changes of one or more worktrees into `master`.

    uv run python scripts/merge_change.py [--block] <worktree> -m <message> [<worktree> -m <message> ...]

The paragraphs below say how the script commits, rebases, checks and lands
the changes, the merge lock it holds, the cases where it refuses a change,
what it prints, and its exit status. The arguments and options follow them.

A check does not stop a merge, other than where the call gives `--block`.
By default the script lands the changes with no check before the
fast-forward of `master`, and runs the checks on the landed commit once
`master` has moved and the merge lock is released. A check that fails then
does not undo the merge: the script prints which check failed, on which
commit, with the check's output, and exits with status 3. With `--block`
the checks run before the fast-forward, and a failed check refuses the
change. A caller gives `--block` for a change that has an active risk
of a silent change: a change that alters existing data or outputs without
failing, which a live consumer reads now.

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
`master` the merge before it left. The kernel releases the lock when its holder ends, however it
ends.

Other writers of `master` take no merge lock: a user's direct commit, and
a merge of a Claude agent's worktree. So `master` can move after the
rebase. Where the fast-forward of `master` fails and `master` is no longer
the commit the stack was rebased onto, the script releases the refresh locks
(below), prints a line that gives the old and the new `master` commit and
whether the engine checks run again (under `--block`), rebases the stack
onto the new `master` as it did the first time, runs the checks on its top
(under `--block`), and fast-forwards `master` to it, in the same call.
Another failure of the fast-forward fails the call. Under `--block`, the
engine checks run again only where the `engine/` tree of the new top
differs from that of the top on which they last passed
(`merge_steps.py checks --engine-passed`); every other check runs again.
The script gives up after 3 such re-checks in one call, and fails as for a
fast-forward that fails for another reason, with the changes committed and
rebased in their worktree. A conflict, or under `--block` a failed check,
in a re-check refuses as in the first round.

The script then rebases the branches, in the order given, onto `master` as
one stack: the first onto `master`, and each next one onto the one before
it. It sets up the submodules of the top of the stack again, for the
commits its branch records. Under `--block` it then runs the checks there,
on the changes as they will merge; without it, it runs them on the landed
commit once the merge lock is released (below). Either way it runs them by
`uv run python scripts/merge_steps.py checks`, so that the top of the
stack's copy of `merge_steps.py` runs each check by the command line that
tree's code gives. Where the changes touch `scripts/merge_steps.py`, the
main tree's copy of it runs in its place, in the main tree's environment
and with the top of the stack as its working directory, so that a change
to that script's own command line merges by the command line of
`master`'s copy. The checks are:

    uv run python -m controlled_markdown check
    uv run python scripts/context.py --write
    cargo test --manifest-path engine/Cargo.toml <crates> --offline --no-fail-fast
    env RUSTDOCFLAGS=-D warnings cargo doc --manifest-path engine/Cargo.toml <crates> --no-deps --offline

The last two run only where the changes touch a path under `engine/`, in
the kept tree, `merge-engine` under the `.cache/` of the main tree, which
each call moves to the `HEAD` of the top of the stack, so that cargo
compiles again only the crates the commits since the last merge changed.
`<crates>` is `-p <crate>` for each crate that holds a path the changes
touch and each crate that depends on one of them, directly or through
others, and `--workspace` where a touched path under `engine/` lies in no
crate's directory (`Cargo.toml`, `Cargo.lock`, `lib/`) or those crates are
all of them. The checks fail where the top of the stack's tree holds an
`engine/` edit that its `HEAD` lacks. `merge_steps.py --help` gives the
kept tree and the selection in full.

The checks run concurrently. A check passes when it exits 0, and a refusal
under `--block` lists every check that fails. `<base>` is the `master`
commit the stack is rebased onto.

Where the checks passed under `--block`, or without it, the script runs in
the main tree
`uv run python scripts/context.py context --keep-tree HEAD`, so that the
readers' updates after the merge find the tree of the old `master` made,
and goes on where it fails. It then fast-forwards `master` in the main tree
to the top of the stack, and runs in the main tree, by
`uv run python scripts/merge_steps.py after` and so by the command
lines of the new `master`,
`uv run python scripts/context.py --write` and
`uv run python scripts/document_pass.py`.

Once every change has landed or been refused, the merge lock is released.
Without `--block`, the script then runs the checks, as above, on each
landed stack's top commit, in the worktree of the top of the stack, with
`<base>` the `master` commit the stack was rebased onto. For each check
that fails, it prints on stderr a line that gives the branch and the
commit, and the check's output, and the call exits with status 3, unless
a change was refused or a step failed, in which case the status is 1. The
merge is not undone. The script then removes each worktree and its branch,
other than where a step after the fast-forward failed.

Before the first fast-forward of `master` of the call whose commits change
a `.py` file, the script locks the refresh locks
(`refresh_locks`) of the merging session, the one
`CLAUDE_CODE_SESSION_ID` gives where the environment gives one, and of
the live sessions, so that a call of `operate.py next` of those sessions
that meets a lock is replaced and does not compute reads of the old code.
Once that fast-forward has landed, the script releases the locks, so a lock
is held only while a fast-forward is. Once the merge lock is released,
where such a fast-forward succeeded, the script starts
`uv run python scripts/kept_refresh.py` in the main tree, as a process in a
session of its own that outlives the script, with those sessions. That
process has the resident service of each session read the state of the new
code into the store of the kept reads, as its `--help` gives. The script
continues without waiting for that refresh. Where no such fast-forward
succeeded, the script releases the locks when it ends.

`document_pass.py` reads the size of each document against its
budget on the new `master`. Where some document stands past its budget
and no whole-document pass stands outside `tickets/closed/`, it files one
pass, a `change` for a doc editor on every document then past its budget,
under `tickets/approved/` with no ticket review, and the script prints its
path. A document that goes past its budget while a pass stands open gets
the next pass, which the first merge after that pass closes files.

A file that `change_worktree.py` copied into a worktree from the main
tree, where the main tree holds it untracked, and whose copy still has
the content copied, is no change of that worktree: the script puts it in
no commit, and leaves the main tree's file in place.

A copied file is a file the main tree holds untracked at a path a change
touches, where the worktree of each change that touches that path holds a
copy that `change_worktree.py` made, and the main tree's file still has
the content it had when copied. Just before the fast-forward, the script
removes each copied file from the main tree, so that the fast-forward
writes the change's version there. Where the fast-forward then fails, it
writes each copied file back with the content and the mode it had.

Where the stack's rebase conflicts or, under `--block`, a check fails on the
top of the stack, and the stack holds more than one change, the script moves
each branch back to its commit before the rebase, and then merges the
changes one at a time, in the order given, each as a stack of one: it
rebases the branch onto `master`, runs the checks on it (under `--block`),
and fast-forwards `master` to it. So the change that fails is the one
refused, and under `--block` every check runs on every change before
`master` moves.

Since git removes a worktree that holds submodules only by force, the
removal is forced, after a check that the worktree holds no change against
its branch, counting changes and untracked files inside its submodules. A
worktree locked by a Claude agent, whose lock reason begins with
`AGENT_LOCK`, is removed with the force that a locked worktree needs, after
the same check.

The main tree's `work/` holds the files the sessions share. The script
does not stage a worktree's `work`, a link or a directory, or anything
under it, and does not count it as a change of the worktree, whatever the
worktree's `.gitignore` gives. Git ignores `work`, so the removal would
delete the files under a worktree's own `work/`. Before it removes a
worktree whose `work` is a directory, the script moves each file under it
to the same path under the main tree's `work/`, where nothing stands there.
A file that is a link to the main tree's file or directory at that path,
or that holds the bytes of the file there, is removed with the worktree.
Where another file stands at one of those paths, or at a directory above
one, the worktree and its branch stay, and the script lists each file that
stays. Where a move fails, or the worktree's `work` is neither a directory
nor a link, they stay as well, and the script says why. A `work` that is
a link is removed as the link alone.

The script ends its output with the duration footer (`engine.duration`).

The script refuses a change, and says why, where:

- the submodule setup fails;
- under `--block`, a check fails, or the submodule setup after the rebase
  fails, in which case it moves the branch back to the `master` commit it
  was rebased onto, with the change left uncommitted in the worktree and
  nothing staged. Without `--block` only the submodule setup does so;
- the main tree has uncommitted changes to a path the change touches,
  among them a path the main tree marks skip-worktree whose file there
  is moved away or holds other content than its commit, and a copied
  file is no such change;
- a submodule of the worktree holds changes or untracked files, which no
  commit of the worktree's branch can hold;
- a gitlink in the worktree's index, once the changes are staged, is not
  listed in `.gitmodules`, or gives a commit that the main tree's copy of
  that submodule's repository lacks. The removal of the worktree deletes
  the worktree's own copies of the submodules' repositories, so the commit
  would then exist nowhere. The refusal puts the index back as it was.
- the rebase onto `master` fails where git leaves no path unmerged, in
  which case it aborts the rebase and leaves the worktree as it was before
  the commit;
- the rebase onto `master` conflicts, in which case it aborts the rebase
  and lists the paths it conflicts in. Where the stack holds that change
  alone, the script then puts the change onto that `master` in its
  worktree: it puts the index and the files at the change's commit, moves
  the branch to that `master` commit, and merges the change's commit onto
  it with `git merge --squash --no-commit`, which leaves each path that
  conflicts as git's 3-way merge leaves it, and it leaves the change
  uncommitted with nothing staged and gives that commit. Where
  any part of that step fails, it puts the branch, the index and the files
  back as the abort left them, and says so;
- `git diff --check` reports a leftover conflict marker in the change
  once it is staged, in which case the script puts the index back as it
  was and commits nothing;
- another merge holds the merge lock, and the script runs under a hold of
  the heavy commands' lock it inherited, under which it does not wait
  (`engine.rwlock.MergeHeld`), in which case every change is refused, and
  each branch is moved back to the commit it stood on before the script's
  commit, with the change left uncommitted in the worktree and nothing
  staged.

A change refused before the stack is rebased is left out of the stack, and
the others merge.

It pushes nothing and moves no branch but `master` and the worktrees' own.
It prints a line per step on stdout, and a refusal, a wait for the
merge lock with what its holder merges, the line that gives the name of each
check as it starts, and the output of each check that fails after landing,
on stderr. As each submodule
setup, commit, rebase, check, command in the main tree and removal of a
worktree ends, it writes the step's step line (`engine.duration.STEP`),
which says how long the step took, on stderr. Each line a check writes on
stderr reaches its stderr as the check writes it.

Exit status: 0 when every change is merged and every check passes, 1 on a
refusal of any change or a failed step, 2 when the call itself is
malformed, and 3 when every change is merged and a check failed after
landing (without `--block`).
"""

import argparse
import filecmp
import os
import shutil
import subprocess
import sys
import tempfile
import time
from typing import TextIO
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from controlled_markdown import mctx
from engine import checkout, rwlock
from engine.duration import footer
from operations.constants import FOREGROUND_MS
from script_calls import SESSION_ENV
from handbook.paths import scripts_importable

scripts_importable()

from change_checks import (merge_base, changed_outside_work,  # noqa: E402
                           outside_work, run_in, said, timed)
from change_worktree import carried, same_blobs  # noqa: E402
from merge_steps import engine_runs  # noqa: E402
from refresh_locks import MergeLocks  # noqa: E402
from worktree_submodules import (checked_out, main_gitdir,  # noqa: E402
                                 submodules, locked_update, SetupFailed)

from operations.merging import (FAILED_LINE,  # noqa: E402
                                MAIN_CHANGED, MAIN_OFF_BASE, REPOSITORIES,
                                MARKERS, MARKER_LINE, NO_CHANGE, NOT_PUT_ON, PATHS_SEP,
                                PREFIX, REFUSED, REFUSED_TREE, TOOL)
from operations.merge_outcomes import CONFLICT, LEFT_AFTER, STAYS  # noqa: E402
from operations.worktrees import BASE  # noqa: E402

STARTED = time.monotonic()
"""The start of the process, from which the bound on a foreground call
runs."""

STEPS = ("scripts/merge_steps.py",)
"""The command, after `uv run python`, that runs the checks or the steps
after the fast-forward in the tree it runs in."""

TREE_KEEP = ("scripts/context.py", "context", "--keep-tree", "HEAD")
"""The command, after `uv run python`, that makes the tree of the main
tree's `HEAD` that the readers' updates read."""


def say(text: str, file: TextIO | None = None, flush: bool = False) -> None:
    print(PREFIX + text, file=file, flush=flush)

ABORTED = mctx("the rebase is aborted and the worktree is as it was:")

PUT_ON = mctx("the rebase is aborted, and {branch} is moved to {onto}'s commit {commit}, "
              "with the change uncommitted in {worktree} and each of those paths that still "
              "conflicts as git's 3-way merge left it:")

UNMERGED_NONE = mctx("the rebase of {branch} onto {onto} fails with no unmerged path; the "
                     "rebase is aborted and the worktree is as it was:")
"""The refusal of a change whose rebase onto `master` fails where git
leaves no path unmerged, which is no conflict."""


class Refused(Exception):
    """A reason the script does not merge the change."""


class Failed(Exception):
    """A step that did not complete, and what it left."""


class Moved(Exception):
    """The fast-forward of `master` did not happen because `master` is
    another commit than the one the stack was rebased onto: `now`, the
    commit `master` stands on, and `failed`, the failure it is where the
    re-checks are used up."""

    def __init__(self, now: str, failed: Failed) -> None:
        super().__init__(str(failed))
        self.now = now
        self.failed = failed


RECHECKS = 3
"""The most times one call rebases and checks the changes again onto a
`master` that moved, which the module docstring states."""


def branch_of(tree: Path) -> str:
    """The branch checked out in `tree`. A detached HEAD is a refusal."""
    done = checkout.git(tree, "symbolic-ref", "--short", "-q", "HEAD")
    if done.returncode != 0:
        raise Refused(f"{tree} stands on no branch")
    return done.stdout.strip()


def set_up_submodules(worktree: Path, main: Path) -> None:
    """Set up the worktree's submodules by
    `worktree_submodules.locked_update`. A failure is a refusal."""
    say("setting up the submodules from the main tree", flush=True)
    try:
        with timed(mctx("the submodule setup of {worktree}").format(worktree=worktree)):
            locked_update(worktree, main)
    except SetupFailed as exc:
        raise Refused(str(exc)) from exc


def run_checks(tree: Path, main: Path, base: str, touched: set[str],
               engine_passed: str | None = None) -> str | None:
    """Run in `tree` the checks of changes from the commit `base`: None
    where every check passes, else the output of the checks that fail.
    `touched`, the paths the changes touch, picks the copy of
    `merge_steps.py` that runs, as the module docstring gives, and `main`
    is the main tree, where that copy is the main tree's. `engine_passed`,
    the commit on which the engine checks last passed, is given to
    `merge_steps.py checks`, as its `--help` gives."""
    steps = (("--project", str(main), "python", str(main / STEPS[0])) if STEPS[0] in touched
             else ("python", *STEPS))
    passed = ("--engine-passed", engine_passed) if engine_passed is not None else ()
    argv = ("uv", "run", *steps, "checks", *passed, base)
    done = subprocess.run(argv, cwd=tree, env=checkout.tree_env(), stdout=subprocess.PIPE,
                          text=True, stdin=subprocess.DEVNULL)
    if done.returncode == 0:
        return None
    return done.stdout.strip() or mctx("{shown} exited with status {code}").format(
        shown=" ".join(argv), code=done.returncode)


def check(tree: Path, main: Path, base: str, touched: set[str],
          engine_passed: str | None = None) -> None:
    """Run the checks as `run_checks` does, and refuse where one fails."""
    failed = run_checks(tree, main, base, touched, engine_passed)
    if failed is not None:
        raise Refused(failed)


def refuse_main_touched(main: Path, touched: Mapping[Path, frozenset[str]]) -> dict[str, str]:
    """Refuse where the main tree has uncommitted changes to a path a change
    touches, `touched` giving the paths each worktree's change touches,
    other than a copied file, as the module docstring gives it. Return
    each copied file, with the hash of its blob."""
    every = set().union(*touched.values())
    records = {w: carried(w) for w in touched}
    hit: list[str] = []
    candidates: dict[str, str] = {}
    for c in checkout.changed_paths(main, "HEAD"):
        if c.path not in every:
            continue
        hashes = {records[w].get(c.path) for w, paths in touched.items() if c.path in paths}
        recorded = hashes.pop() if len(hashes) == 1 else None
        if c.change is checkout.Change.UNTRACKED and recorded is not None:
            candidates[c.path] = recorded
        else:
            hit.append(c.path)
    kept = same_blobs(main, candidates)
    replaced = {p: candidates[p] for p in sorted(kept)}
    hit = sorted([*hit, *(p for p in candidates if p not in kept)])
    if hit:
        raise Refused(MAIN_CHANGED.format(main=main) + "\n" + "\n".join(hit))
    return replaced


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
        e = checkout.index_entry(entry)
        if e.mode == checkout.Mode.GITLINK:
            found.append((e.path, e.object_name))
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


def stage(worktree: Path, main: Path, backup: Path, base: str) -> None:
    """Stage each path of the worktree that `changed_outside_work` gives
    against its `HEAD`, with a copy of its
    index kept at `backup` first, and refuse where `refuse_gitlinks` or
    `refuse_markers` against the commit `base` does, with the index put
    back."""
    shutil.copy2(index_file(worktree), backup)
    changed = changed_outside_work(worktree, "HEAD")
    if changed:
        checkout.git_out(worktree, "update-index", "--add", "--remove", "--",
                         *(path.rstrip("/") for path in changed))
    try:
        refuse_gitlinks(worktree, main)
        refuse_markers(worktree, base)
    except Refused:
        shutil.copy2(backup, index_file(worktree))
        raise


def refuse_markers(worktree: Path, base: str) -> None:
    """Refuse where `git diff --check` reports a leftover conflict marker
    in the staged change against the commit `base`."""
    done = checkout.git(worktree, "diff", "--cached", "--check", base, "--", *outside_work())
    found = [ln for ln in done.stdout.splitlines() if ln.endswith(MARKER_LINE)]
    if found:
        raise Refused(MARKERS.format(branch=branch_of(worktree)) + "\n" + "\n".join(found))


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


@dataclass
class Landed:
    """The changes `master` took in one fast-forward, as a stack: `base` is
    the `master` commit the stack was rebased onto. `checked` is whether
    the checks passed before the fast-forward (`--block`), and `stays`
    whether a step after the fast-forward failed, so that the worktrees and
    branches of the changes stay."""

    changes: tuple[Change, ...]
    base: str
    checked: bool
    stays: bool = False


def unmerged_paths(worktree: Path) -> list[str]:
    """The paths git leaves unmerged in `worktree`."""
    return checkout.git_out(worktree, "diff", "--name-only", "--diff-filter=U").splitlines()


def rebase(change: Change, onto: str, onto_name: str, restore: bool) -> None:
    """Rebase the change's branch onto the commit `onto`, which `onto_name`
    names. On a conflict, abort the rebase, which leaves the branch at
    `committed`; with `restore`, move it back to `before`, put back the
    index at `backup`, and put the change onto `onto` (`put_on`); and
    refuse, with the paths git leaves unmerged, or, where it leaves none,
    as a failure that is no conflict."""
    say(mctx("rebasing {branch} onto {onto}").format(
        branch=change.branch, onto=onto_name), flush=True)
    with timed(mctx("the rebase of {branch}").format(branch=change.branch)):
        done = checkout.git(change.worktree, "rebase", onto)
    if done.returncode == 0:
        return
    unmerged = unmerged_paths(change.worktree)
    checkout.git_out(change.worktree, "rebase", "--abort")
    if restore and change.backup is not None:
        checkout.git_out(change.worktree, "reset", "-q", "--soft", change.before)
        shutil.copy2(change.backup, index_file(change.worktree))
    if not unmerged:
        raise Refused(UNMERGED_NONE.format(branch=change.branch, onto=onto_name) + "\n"
                      + said(done))
    outcome = put_on(change, onto, onto_name) if restore else ABORTED
    raise Refused(CONFLICT.format(branch=change.branch, onto=onto_name,
                                  paths=PATHS_SEP.join(unmerged), outcome=outcome)
                  + "\n" + said(done))


def put_on(change: Change, onto: str, onto_name: str) -> str:
    """Put the change, aborted out of its rebase onto the commit `onto`,
    onto `onto`, as the module docstring gives it, or put the branch, the
    index and the files back as the abort left them; the outcome a
    `CONFLICT` refusal gives."""
    w = change.worktree
    head = checkout.git_out(w, "rev-parse", "HEAD").strip()
    with tempfile.TemporaryDirectory(prefix="merge-change-put-on-") as tmp:
        index = Path(tmp) / "index"
        shutil.copy2(index_file(w), index)
        try:
            # From the commit's index, so that the reset to `onto` removes
            # each file the change adds, which the restore left untracked.
            checkout.git_out(w, "reset", "-q", "--hard", change.committed)
            checkout.git_out(w, "reset", "-q", "--hard", onto)
            squash = ("merge", "--squash", "--no-commit", change.committed)
            merged = checkout.git(w, *squash)
            if merged.returncode != 0 and not unmerged_paths(w):
                raise checkout.GitFailed(w, squash, merged.stderr)
            checkout.git_out(w, "reset", "-q")
        except checkout.GitFailed:
            checkout.git_out(w, "reset", "-q", "--hard", change.committed)
            checkout.git_out(w, "reset", "-q", "--soft", head)
            shutil.copy2(index, index_file(w))
            return NOT_PUT_ON.format(onto=onto_name, commit=onto[:12])
    return PUT_ON.format(branch=change.branch, onto=onto_name, commit=onto[:12], worktree=w)


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
    if branch == BASE:
        raise Refused(f"{worktree} stands on {BASE}")
    base = merge_base(worktree)
    touched = set(changed_outside_work(worktree, base))
    if not touched:
        raise Refused(NO_CHANGE.format(branch=branch, base=BASE))
    refuse_main_touched(main, {worktree: frozenset(touched)})

    set_up_submodules(worktree, main)
    refuse_dirty_submodules(worktree)
    before = checkout.git_out(worktree, "rev-parse", "HEAD").strip()
    committing = bool(changed_outside_work(worktree, "HEAD"))
    stage(worktree, main, backup, base)
    if committing:
        say(f"committing on {branch}", flush=True)
        with timed(mctx("the commit on {branch}").format(branch=branch)):
            checkout.git_out(worktree, "commit", "-q", "-m", message)
    return Change(worktree, branch, frozenset(touched), before,
                  backup if committing else None,
                  checkout.git_out(worktree, "rev-parse", "HEAD").strip())


def touched_by(changes: Sequence[Change]) -> set[str]:
    return {p for c in changes for p in c.touched}


def say_moved(old: str, new: str, engine: bool | None) -> None:
    """Say that `master` moved from `old` to `new`, and, where `engine` is
    not None, whether the engine checks run again."""
    again = "" if engine is None else (
        f"; the engine checks {'run' if engine else 'do not run'} again")
    say(f"{BASE} moved from {old[:12]} to {new[:12]}{again}", flush=True)


def stack(main: Path, changes: Sequence[Change], locks: MergeLocks, block: bool,
          landed: list[Landed]) -> None:
    """Rebase the branches of `changes`, in order, onto `master` as one
    stack, run the checks on its top where `block` holds, and land it, or
    refuse. Where `master` moves before the fast-forward, rebase, check
    and land again, up to `RECHECKS` times, as the module docstring gives.
    A refusal leaves each branch at `committed`. `landed` gets the stack
    once it lands."""
    base = checkout.git_out(main, "rev-parse", BASE).strip()
    passed: str | None = None
    moved_from: str | None = None
    for attempt in range(RECHECKS + 1):
        try:
            onto = base
            names = [BASE, *(c.branch for c in changes[:-1])]
            for c, onto_name in zip(changes, names, strict=True):
                rebase(c, onto, onto_name, restore=False)
                onto = checkout.git_out(c.worktree, "rev-parse", "HEAD").strip()
            top = changes[-1].worktree
            set_up_submodules(top, main)
            again = engine_runs(top, base, passed) if block else None
            if moved_from is not None:
                say_moved(moved_from, base, again)
            if block:
                check(top, main, base, touched_by(changes), passed)
                passed = onto if again else passed
            land(main, changes, locks, base, block, landed)
            return
        except Refused:
            for c in changes:
                unstack(c)
            raise
        except Moved as moved:
            if attempt == RECHECKS:
                raise moved.failed from moved
            moved_from, base = base, moved.now


def unstack(change: Change) -> None:
    """Move the change's branch back to `committed`. The worktree holds
    every change of its branch's commits after the stack's rebase, so the
    hard reset loses none where it holds no change against the branch."""
    if checkout.git_out(change.worktree, "rev-parse", "HEAD").strip() == change.committed:
        return
    left = changed_outside_work(change.worktree, "HEAD")
    if left:
        raise Failed(mctx("{worktree} holds changes made after the stack's rebase, so "
                          "{branch} stays rebased:").format(
            worktree=change.worktree, branch=change.branch) + "\n" + "\n".join(left))
    checkout.git_out(change.worktree, "reset", "-q", "--hard", change.committed)


def merge_alone(main: Path, change: Change, locks: MergeLocks, block: bool,
                landed: list[Landed]) -> None:
    """Rebase the change's branch onto `master`, run the checks on it where
    `block` holds, and land it, or refuse. Where `master` moves before the
    fast-forward, rebase, check and land again, up to `RECHECKS` times, as
    the module docstring gives. `landed` gets the change once it lands."""
    onto = checkout.git_out(main, "rev-parse", BASE).strip()
    passed: str | None = None
    moved_from: str | None = None
    for attempt in range(RECHECKS + 1):
        rebase(change, onto, BASE, restore=True)
        try:
            set_up_submodules(change.worktree, main)
            again = engine_runs(change.worktree, onto, passed) if block else None
            if moved_from is not None:
                say_moved(moved_from, onto, again)
            if block:
                check(change.worktree, main, onto, set(change.touched), passed)
        except Refused as exc:
            tree = checkout.git_out(change.worktree, "rev-parse", "HEAD^{tree}").strip()
            checkout.git_out(change.worktree, "reset", "-q", "--mixed", onto)
            raise Refused(f"{exc}\n{change.branch} is moved back to {BASE}'s commit "
                          f"{onto[:12]}, and the change stands uncommitted in "
                          f"{change.worktree}" + REFUSED_TREE.format(tree=tree)) from exc
        if again:
            passed = checkout.git_out(change.worktree, "rev-parse", "HEAD").strip()
        try:
            land(main, [change], locks, onto, block, landed)
            return
        except Moved as moved:
            if attempt == RECHECKS:
                raise moved.failed from moved
            moved_from, onto = onto, moved.now


AGENT_LOCK = "claude agent "
"""The start of the lock reason of a worktree a Claude agent works in."""


def files_under(top: Path) -> list[Path]:
    """Each file under the directory `top`, from `top`, sorted: each entry
    that is no directory, a link to a directory among them."""
    found: list[Path] = []
    for entry in os.scandir(top):
        if entry.is_dir(follow_symlinks=False):
            found += [Path(entry.name) / p for p in files_under(Path(entry.path))]
        else:
            found.append(Path(entry.name))
    return sorted(found)


def holds_nothing_new(src: Path, dst: Path) -> bool:
    """Whether the entry `src` leads to the same file or directory as `dst`,
    or both are regular files, no link, of equal bytes (`filecmp.cmp` reads
    them only where their sizes are equal)."""
    if os.path.realpath(src) == os.path.realpath(dst):
        return True
    return (src.is_file() and dst.is_file()
            and not src.is_symlink() and not dst.is_symlink()
            and filecmp.cmp(src, dst, shallow=False))


def move_work(main: Path, worktree: Path) -> list[str]:
    """Move each file under the worktree's `work/` to the same path under
    the main tree's `work/` (`checkout.work`), where nothing stands there;
    each path, from the worktree's root, of a file that stays, since a file
    or a link stands at its path under the main tree's `work/`, or a file
    at a directory above it. A file that holds nothing the main tree's
    `work/` lacks is removed with no move: a link that leads to the same
    file or directory as the main tree's path (`os.path.realpath`), or a
    regular file whose bytes equal those of the main tree's regular file
    there. The file comes to stand there whole or not at all, and a file
    another process puts there first stays where it is. A `work` that is a
    link is left to the removal, which deletes the link and nothing it
    leads to. A `work` that is neither a directory nor a link is a fault
    (`ValueError`)."""
    name = checkout.work().name
    work = worktree / name
    if work.is_symlink() or not os.path.lexists(work):
        return []
    if not work.is_dir():
        raise ValueError(f"{work} is neither a directory nor a link")
    stays: list[str] = []
    for rel in files_under(work):
        src, dst = work / rel, main / name / rel
        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
            if src.is_symlink():
                os.symlink(os.readlink(src), dst)
            else:
                os.link(src, dst)
        except (FileExistsError, NotADirectoryError):
            if not holds_nothing_new(src, dst):
                stays.append(f"{name}/{rel}")
                continue
        src.unlink()
    return stays


def remove(main: Path, change: Change) -> None:
    """Remove the change's worktree and branch, or fail where the worktree
    holds a change against its branch, or a submodule of it holds changes
    or untracked files, or where a file under its `work/` stays
    (`move_work`)."""
    worktree, branch = change.worktree, change.branch
    say(mctx("removing {worktree} and {branch}").format(
        worktree=worktree, branch=branch), flush=True)

    def stays(why: str) -> Failed:
        return Failed(STAYS.format(master=BASE, why=why, worktree=worktree, branch=branch))

    left = changed_outside_work(worktree, "HEAD")
    left += submodule_changes(worktree)
    if left:
        raise stays(LEFT_AFTER.format(left=", ".join(left)))
    reasons = {w.path.resolve(): w.lock for w in checkout.worktree_list(main)}
    if worktree not in reasons:
        raise stays(mctx("git worktree list does not list the worktree"))
    force = ["--force"]
    reason = reasons[worktree]
    if reason is not None:
        if not reason.startswith(AGENT_LOCK):
            raise stays(mctx("the worktree is locked for a reason no Claude agent gives: "
                             "`{reason}`").format(reason=reason))
        force = ["--force", "--force"]
    try:
        kept = move_work(main, worktree)
    except (OSError, ValueError) as exc:
        raise stays(mctx("moving the files under its work/ to the main tree's failed: "
                         "{exc}").format(exc=exc)) from exc
    if kept:
        raise stays(mctx("a file stands in the main tree at the path of each of {kept}, "
                         "or at a directory above it").format(kept=", ".join(kept)))
    checkout.git_out(main, "worktree", "remove", *force, str(worktree))
    checkout.git_out(main, "branch", "-q", "-d", branch)


def run_step(main: Path, argv: Sequence[str]) -> subprocess.CompletedProcess[str]:
    shown = " ".join(argv)
    say(mctx("running {shown} in the main tree").format(shown=shown), flush=True)
    with timed(shown):
        return run_in(main, ("uv", "run", "python", *argv))


def land(main: Path, changes: Sequence[Change], locks: MergeLocks,
         onto: str, block: bool, landed: list[Landed]) -> None:
    """Merge `changes`, the stack rebased onto the commit `onto` of
    `master`, into `master` in the main tree `main`, with the refresh locks
    `locks` taken before the fast-forward, and run the steps after it. The
    checks passed on the stack where `block` holds. Once the fast-forward
    has landed, `landed` gets the stack. Where the fast-forward fails and
    `master` is no longer `onto`, raise `Moved`, with the refresh locks
    released. It removes no worktree (`finish` does)."""
    replaced = refuse_main_touched(main, {c.worktree: c.touched for c in changes})
    done = run_step(main, TREE_KEEP)
    if done.returncode != 0:
        say(mctx("{shown} failed in {main}; the merge goes on:").format(
            shown=" ".join(TREE_KEEP), main=main) + "\n" + said(done), flush=True)
    modes = {p: (main / p).stat().st_mode for p in replaced}
    for p in sorted(replaced):
        (main / p).unlink()
    top = changes[-1].branch
    locks.take(top)
    say(f"fast-forwarding {BASE} to {top}", flush=True)
    done = checkout.git(main, "merge", "--ff-only", "-q", top)
    if done.returncode != 0:
        for p, blob in sorted(replaced.items()):
            (main / p).write_bytes(subprocess.run(["git", "cat-file", "blob", blob], cwd=main,
                                                  capture_output=True, check=True).stdout)
            os.chmod(main / p, modes[p])
        failure = Failed(f"fast-forwarding {BASE} failed; {top} is committed and "
                        f"rebased in {changes[-1].worktree}:\n{said(done)}")
        now = checkout.git_out(main, "rev-parse", BASE).strip()
        if now == onto:
            raise failure
        locks.close()
        raise Moved(now, failure)
    locks.mark_landed()
    entry = Landed(tuple(changes), onto, checked=block)
    landed.append(entry)

    argv = (*STEPS, "after")
    done = run_step(main, argv)
    if done.returncode != 0:
        entry.stays = True
        raise Failed(mctx("{master} is fast-forwarded, and {shown} failed in {main}; the "
                          "worktrees and branches of {branches} stay:").format(
            master=BASE, shown=" ".join(argv), main=main,
            branches=", ".join(c.branch for c in changes)) + "\n" + said(done))
    print(done.stdout, end="", flush=True)


CHECK_AFTER = mctx("a check failed after {branch} landed in {master}, on the commit {commit}:")
"""The line that opens the output of the checks that fail on a commit that
has landed."""

LANDED_CHECK_EXIT = 3
"""The exit status of a call that landed every change it did not refuse
and on which a check failed after landing."""


def check_landed(main: Path, entry: Landed) -> bool:
    """Run the checks on the commit `entry` landed, in the worktree of the
    top of its stack, outside the merge lock, and print on stderr the
    output of each that fails, with the branch and the commit. Whether
    every check passed."""
    top = entry.changes[-1]
    commit = checkout.git_out(top.worktree, "rev-parse", "HEAD").strip()
    failed = run_checks(top.worktree, main, entry.base, touched_by(entry.changes))
    if failed is None:
        return True
    print(PREFIX + CHECK_AFTER.format(branch=top.branch, master=BASE, commit=commit[:12])
          + "\n" + failed, file=sys.stderr, flush=True)
    return False


def finish(main: Path, landed: Sequence[Landed]) -> tuple[bool, bool]:
    """The work after the merge lock is released, for each stack in `landed`
    in order: the checks on its landed commit (`check_landed`), where they
    did not pass before the fast-forward, and then the removal of the
    worktree and branch of each of its changes, other than where a step
    after the fast-forward failed. Print each failure of a removal on
    stderr. Whether every check passed, and whether every removal
    succeeded."""
    passed = removed = True
    for entry in landed:
        if not entry.checked:
            passed = check_landed(main, entry) and passed
    for entry in landed:
        if entry.stays:
            continue
        for c in entry.changes:
            try:
                with timed(mctx("the removal of {worktree}").format(worktree=c.worktree)):
                    remove(main, c)
            except (Failed, checkout.GitFailed) as exc:
                print(f"{FAILED_LINE}{exc}", file=sys.stderr, flush=True)
                removed = False
            else:
                say(f"merged {c.branch} into {BASE}", flush=True)
    return passed, removed


def print_refusal(exc: Refused) -> None:
    print(f"{REFUSED}{exc}", file=sys.stderr, flush=True)


def merge(pairs: Sequence[tuple[Path, str]], block: bool) -> int:
    """Merge each worktree's change into `master`, committed with its
    message, under the merge lock (`land_all`), with the checks before the
    fast-forward where `block` holds and after it otherwise (`finish`).
    The exit status: 0 where every change merged and every check passed,
    `LANDED_CHECK_EXIT` where every change merged and a check failed after
    landing, and 1 otherwise."""
    try:
        mains = [checkout.main_worktree(w) for w, _ in pairs]
    except checkout.GitFailed as exc:
        raise Refused(str(exc)) from exc
    main = mains[0]
    others = sorted({str(m) for m in mains} - {str(main)})
    if others:
        raise Refused(REPOSITORIES.format(main=main, others=", ".join(others)))
    try:
        main_branch = branch_of(main)
    except Refused:
        main_branch = "no branch"
    if main_branch != BASE:
        raise Refused(MAIN_OFF_BASE.format(main=main, branch=main_branch, base=BASE))
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
            return 0 if every else 1
        holder = mctx("pid {pid}, since {since}, merging {branches}").format(
            pid=os.getpid(), since=time.strftime("%H:%M:%S"),
            branches=", ".join(c.branch for c in changes))
        locks = MergeLocks(main, os.environ.get(SESSION_ENV))
        landed: list[Landed] = []
        passed = removed = True
        try:
            with rwlock.merge_lock(checkout.git_common_dir(main), holder):
                say("holding the merge lock", flush=True)
                every = land_all(main, changes, locks, block, landed) and every
        except rwlock.MergeHeld as exc:
            for c in changes:
                checkout.git_out(c.worktree, "reset", "-q", "--mixed", c.before)
            raise Refused(mctx("{exc} Each branch is moved back to the commit it stood on "
                               "before, and its change stands uncommitted in its "
                               "worktree.").format(exc=exc)) from exc
        finally:
            refresh_kept(locks)
            passed, removed = finish(main, landed)
        if not (every and removed):
            return 1
        return 0 if passed else LANDED_CHECK_EXIT


def refresh_kept(locks: MergeLocks) -> None:
    """Start the refresh described by the module's help text."""
    if locks.start() is not None:
        say("refreshing the kept reads in the main tree", flush=True)


def land_all(main: Path, changes: Sequence[Change], locks: MergeLocks, block: bool,
             landed: list[Landed]) -> bool:
    """Merge the committed `changes` into `master`: as one stack, or, where
    the stack is refused, one at a time, with the checks before the
    fast-forward where `block` holds. `landed` gets each stack that lands.
    Whether every change merged."""
    if len(changes) > 1:
        try:
            stack(main, changes, locks, block, landed)
        except Refused as exc:
            say(mctx("the stack is refused, so the changes merge one "
                       "at a time:") + "\n" + str(exc), flush=True)
        else:
            return True
    every = True
    for c in changes:
        try:
            merge_alone(main, c, locks, block, landed)
        except Refused as exc:
            print_refusal(exc)
            every = False
    return every


def main(argv: Sequence[str]) -> int:
    with footer(TOOL):
        return merge_main(argv)


def merge_main(argv: Sequence[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("worktree", type=Path, nargs="+", help="the worktree of a change")
    ap.add_argument("-m", "--message", action="append", required=True,
                    help="the message of the commit of the uncommitted changes of the "
                         "worktree it follows")
    ap.add_argument("--block", action="store_true",
                    help="run the checks before the fast-forward of master, and refuse a "
                         "change on which one fails; otherwise they run on the landed commit "
                         "once master has moved, and a failure exits with status "
                         f"{LANDED_CHECK_EXIT}")
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
        return merge(list(zip(worktrees, a.message, strict=True)), a.block)
    except Refused as exc:
        print_refusal(exc)
        return 1
    except (Failed, checkout.GitFailed) as exc:
        print(f"{FAILED_LINE}{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
