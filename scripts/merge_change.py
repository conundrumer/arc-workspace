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
they will merge, by `uv run python scripts/merge_steps.py checks`, so that
the top of the stack's copy of `merge_steps.py` runs each check by the
command line that tree's code gives. Where the changes touch
`scripts/merge_steps.py`, the main tree's copy of it runs in its place, in
the main tree's environment and with the top of the stack as its working
directory, so that a change to that script's own command line merges by
the command line of `master`'s copy. The checks are:

    uv run python -m controlled_markdown check
    uv run python scripts/context.py --write
    uv run python scripts/gate.py --affected <base> <out>
    cargo test --manifest-path engine/Cargo.toml --workspace --offline --no-fail-fast
    env RUSTDOCFLAGS=-D warnings cargo doc --manifest-path engine/Cargo.toml --workspace --no-deps --offline

The last two run only where the changes touch a path under `engine/`. The
checks run concurrently. A check passes when it exits 0, and a refusal
lists every check that fails. The gate's dependency record decides which
of its commands a change affects, so the gate runs on every change, with
`<base>` the `master` commit the stack is rebased onto. It writes into a
new directory under `$TMPDIR`, whose name is `merge-change-gate-`, then the
first 8 hex digits of each commit after `<base>` up to the top of the stack,
newest first, each followed by `-`, for at most the 24 newest commits,
then a random part. So `ls -dt "$TMPDIR"/merge-change-gate-*<hash>*`, with
`<hash>` what `git rev-parse --short=8 <commit>` prints, lists the
directories of the gates that checked `<commit>`, newest first, for a gate
that passes as for one that fails. The merge's `running` line of the gate
gives its directory too. The gate's `--help` says which
commands `--affected` runs and how the gate's times are judged.

The top of the stack holds every change committed, so where the gate runs
every command, it traces them and writes a dependency record of that
commit into its directory.

When every check passes, the script runs in the main tree
`uv run python scripts/context.py context --keep-tree HEAD`, so that the
readers' updates after the merge find the tree of the old `master` made,
and goes on where it fails. It then fast-forwards `master` in the main tree
to the top of the stack, and runs in the main tree, by
`uv run python scripts/merge_steps.py after <out>` and so by the command
lines of the new `master`,
`uv run python scripts/context.py --write`,
`uv run python scripts/document_pass.py` and
`uv run python scripts/gate.py --adopt <out>`, with `<out>` the
directory of the gate that checked the stack, so that a record the gate
wrote stands as the dependency record of the new `master`, the gate's counts
of instructions are adopted, and a ticket is filed on each `SLOW` line, as the
gate's `--help` gives. It then removes each worktree and its branch.

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

The main tree's `work/` holds the files the sessions share. The script
does not stage a worktree's `work`, a link or a directory, or anything
under it, and does not count it as a change of the worktree, whatever the
worktree's `.gitignore` gives. Git ignores `work`, so the removal would
delete the files under a worktree's own `work/`. Before it removes a
worktree whose `work` is a directory, the script moves each file under it
to the same path under the main tree's `work/`, where nothing stands there.
Where a file stands at one of those paths, or at a directory above one,
the worktree and its branch stay, and the script lists each file that
stays. Where a move fails, or the worktree's `work` is neither a directory
nor a link, they stay as well, and the script says why. A `work` that is
a link is removed as the link alone.

The script ends its output with the duration footer (`engine.duration`).

The script refuses a change, and says why, where:

- the submodule setup fails;
- a check, or the submodule setup after the rebase, fails, in which case it
  moves the branch back to the `master` commit it was rebased onto, with
  the change left uncommitted in the worktree and nothing staged;
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
merge lock with what its holder merges, and the line that gives the name of each
check as it starts, on stderr. As each submodule
setup, commit, rebase, check, command in the main tree and removal of a
worktree ends, it writes the step's step line (`engine.duration.STEP`),
which says how long the step took, on stderr. Each line a check writes on
stderr reaches its stderr as the check writes it.

Exit status: 0 when every change is merged, 1 on a refusal of any change or
a failed step, 2 when the call itself is malformed.
"""

import argparse
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


GATE_PREFIX = "merge-change-gate-"

NAMED_COMMITS = 24
"""The most commits the name of the gate's out-dir gives, which the module
docstring states: the newest, so that the name stays under the file
system's 255 bytes."""


def check(tree: Path, main: Path, base: str, touched: set[str]) -> Path:
    """Run in `tree` the checks of changes from the commit `base`, or
    refuse; the gate's out-dir, named as the module docstring gives.
    `touched`, the paths the changes touch, picks the copy of
    `merge_steps.py` that runs, as the module docstring gives, and `main`
    is the main tree, where that copy is the main tree's."""
    commits = checkout.git_out(tree, "rev-list", f"--max-count={NAMED_COMMITS}", f"{base}..HEAD").split()
    gate_out = tempfile.mkdtemp(prefix=GATE_PREFIX + "".join(f"{c[:8]}-" for c in commits))
    steps = (("--project", str(main), "python", str(main / STEPS[0])) if STEPS[0] in touched
             else ("python", *STEPS))
    argv = ("uv", "run", *steps, "checks", base, gate_out)
    done = subprocess.run(argv, cwd=tree, env=checkout.tree_env(), stdout=subprocess.PIPE,
                          text=True, stdin=subprocess.DEVNULL)
    if done.returncode != 0:
        raise Refused(done.stdout.strip() or mctx("{shown} exited with status {code}").format(
            shown=" ".join(argv), code=done.returncode))
    return Path(gate_out)


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


def stack(main: Path, changes: Sequence[Change]) -> Path:
    """Rebase the branches of `changes`, in order, onto `master` as one
    stack, and run the checks on its top, or refuse; the gate's out-dir. A
    refusal leaves each branch at `committed`."""
    base = onto = checkout.git_out(main, "rev-parse", BASE).strip()
    names = [BASE, *(c.branch for c in changes[:-1])]
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
    left = changed_outside_work(change.worktree, "HEAD")
    if left:
        raise Failed(mctx("{worktree} holds changes made after the stack's rebase, so "
                          "{branch} stays rebased:").format(
            worktree=change.worktree, branch=change.branch) + "\n" + "\n".join(left))
    checkout.git_out(change.worktree, "reset", "-q", "--hard", change.committed)


def merge_alone(main: Path, change: Change, locks: MergeLocks) -> None:
    """Rebase the change's branch onto `master`, run the checks on it, and
    land it, or refuse."""
    onto = checkout.git_out(main, "rev-parse", BASE).strip()
    rebase(change, onto, BASE, restore=True)
    try:
        set_up_submodules(change.worktree, main)
        gate_out = check(change.worktree, main, onto, set(change.touched))
    except Refused as exc:
        tree = checkout.git_out(change.worktree, "rev-parse", "HEAD^{tree}").strip()
        checkout.git_out(change.worktree, "reset", "-q", "--mixed", onto)
        raise Refused(f"{exc}\n{change.branch} is moved back to {BASE}'s commit "
                      f"{onto[:12]}, and the change stands uncommitted in "
                      f"{change.worktree}" + REFUSED_TREE.format(tree=tree)) from exc
    land(main, [change], gate_out, locks)


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


def move_work(main: Path, worktree: Path) -> list[str]:
    """Move each file under the worktree's `work/` to the same path under
    the main tree's `work/` (`checkout.work`), where nothing stands there;
    each path, from the worktree's root, of a file that stays, since a file
    or a link stands at its path under the main tree's `work/`, or a file
    at a directory above it. The file comes to stand there whole or not at
    all, and a file another process puts there first stays where it is. A
    `work` that is a link is left to the removal, which deletes the link and
    nothing it leads to. A `work` that is neither a directory nor a link is
    a fault (`ValueError`)."""
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


def land(main: Path, changes: Sequence[Change], gate_out: Path, locks: MergeLocks) -> None:
    """Merge `changes`, the stack the gate passed with its outputs in
    `gate_out`, into `master` in the main tree `main`, with the refresh
    locks `locks` taken before the fast-forward."""
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
        raise Failed(f"fast-forwarding {BASE} failed; {top} is committed and "
                     f"rebased in {changes[-1].worktree}:\n{said(done)}")
    locks.mark_landed()

    argv = (*STEPS, "after", str(gate_out))
    done = run_step(main, argv)
    if done.returncode != 0:
        raise Failed(mctx("{master} is fast-forwarded, and {shown} failed in {main}; the "
                          "worktrees and branches of {branches} stay:").format(
            master=BASE, shown=" ".join(argv), main=main,
            branches=", ".join(c.branch for c in changes)) + "\n" + said(done))
    print(done.stdout, end="", flush=True)

    failed: list[str] = []
    for c in changes:
        try:
            with timed(mctx("the removal of {worktree}").format(worktree=c.worktree)):
                remove(main, c)
        except (Failed, checkout.GitFailed) as exc:
            failed.append(str(exc))
        else:
            say(f"merged {c.branch} into {BASE}", flush=True)
    if failed:
        raise Failed("\n".join(failed))


def print_refusal(exc: Refused) -> None:
    print(f"{REFUSED}{exc}", file=sys.stderr, flush=True)


def merge(pairs: Sequence[tuple[Path, str]]) -> bool:
    """Merge each worktree's change into `master`, committed with its
    message, under the merge lock (`land_all`). Whether every change
    merged."""
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
            return every
        holder = mctx("pid {pid}, since {since}, merging {branches}").format(
            pid=os.getpid(), since=time.strftime("%H:%M:%S"),
            branches=", ".join(c.branch for c in changes))
        locks = MergeLocks(main, os.environ.get(SESSION_ENV))
        try:
            with rwlock.merge_lock(checkout.git_common_dir(main), holder):
                say("holding the merge lock", flush=True)
                return land_all(main, changes, locks) and every
        except rwlock.MergeHeld as exc:
            for c in changes:
                checkout.git_out(c.worktree, "reset", "-q", "--mixed", c.before)
            raise Refused(mctx("{exc} Each branch is moved back to the commit it stood on "
                               "before, and its change stands uncommitted in its "
                               "worktree.").format(exc=exc)) from exc
        finally:
            refresh_kept(locks)


def refresh_kept(locks: MergeLocks) -> None:
    """Start the refresh described by the module's help text."""
    if locks.start() is not None:
        say("refreshing the kept reads in the main tree", flush=True)


def land_all(main: Path, changes: Sequence[Change], locks: MergeLocks) -> bool:
    """Merge the committed `changes` into `master`: as one stack, or, where
    the stack is refused, one at a time. Whether every change merged."""
    if len(changes) > 1:
        try:
            gate_out = stack(main, changes)
        except Refused as exc:
            say(mctx("the stack is refused, so the changes merge one "
                       "at a time:") + "\n" + str(exc), flush=True)
        else:
            land(main, changes, gate_out, locks)
            return True
    every = True
    for c in changes:
        try:
            merge_alone(main, c, locks)
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
        print(f"{FAILED_LINE}{exc}", file=sys.stderr)
        return 1
    return 0 if merged else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
