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
    uv run python scripts/context.py --write       always
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

A carried file is a file the main tree holds untracked at a path a change
touches, where the worktree of each change that touches that path holds a
copy that `change_worktree.py` made, and the main tree's file still has
the content it had when copied. Just before the fast-forward, the script
removes each carried file from the main tree, so that the fast-forward
writes the change's version there. Where the fast-forward then fails, it
writes each carried file back with the content and the mode it had.

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
the worktree and its branch stay, and the script names each file that
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
  is moved away or holds other content than its commit, and a carried
  file is no such change;
- a submodule of the worktree holds changes or untracked files, which no
  commit of the worktree's branch can hold;
- a gitlink in the worktree's index, once the changes are staged, is not
  listed in `.gitmodules`, or names a commit that the main tree's copy of
  that submodule's repository lacks. The removal of the worktree deletes
  the worktree's own copies of the submodules' repositories, so the commit
  would then exist nowhere. The refusal puts the index back as it was.
- the rebase onto `master` conflicts, or fails where git leaves no path
  unmerged, in which case it aborts the rebase and leaves the worktree as
  it was before the commit, and names the paths it conflicts in, where git
  leaves any;
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
merge lock with what its holder merges, on stderr. As each submodule
setup, commit, rebase, check, command in the main tree and removal of a
worktree ends, it writes the step's step line (`engine.duration.STEP`),
which says how long the step took, on stderr. Each line a check writes on
stderr reaches its stderr as the check writes it, so a wait of the gate
for the heavy commands' lock shows while it lasts.

Exit status: 0 when every change is merged, 1 on a refusal of any change or
a failed step, 2 when the call itself is malformed.
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from typing import TextIO
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from controlled_markdown import form, mctx
from engine import checkout, rwlock
from engine.duration import footer
from handbook.paths import importable

# `scripts/` is no package: a test loads this module by its path, with
# `scripts/` off `sys.path`, and `change_checks` and `worktree_submodules`
# import from there.
importable(checkout.scripts())

from change_checks import (MARKDOWN_CHECK, Check, code_paths,  # noqa: E402
                           failures, run_in, said, timed)
from change_worktree import carried  # noqa: E402
from worktree_submodules import (checked_out, main_gitdir,  # noqa: E402
                                 submodules, locked_update, SetupFailed)

from operations.merging import PATHS_SEP, split_paths  # noqa: E402
from operations.tracker import BASE  # noqa: E402

PREFIX = "merge_change: "
"""The opening of each line the script prints, on stdout and on stderr."""

REFUSED = PREFIX + "refused: "
"""The opening of the line of a refusal."""


def say(text: str, file: TextIO | None = None, flush: bool = False) -> None:
    print(PREFIX + text, file=file, flush=flush)

CONFLICT = mctx("rebasing {branch} onto {onto} conflicts in {paths}; the rebase is aborted "
                "and the worktree is as it was:")
"""The refusal of a change whose rebase onto `master` conflicts."""

UNMERGED_NONE = mctx("the rebase of {branch} onto {onto} fails with no unmerged path; the "
                     "rebase is aborted and the worktree is as it was:")
"""The refusal of a change whose rebase onto `master` fails where git
leaves no path unmerged, which is no conflict."""


def ran(output: str) -> bool:
    """Whether `output`, what a call of the script printed, holds a line of
    the script's own, which a call that never ran does not."""
    return any(line.startswith(PREFIX) for line in output.splitlines())


STAYS = mctx("{master} is fast-forwarded, and {why}, so {worktree} and {branch} stay")
"""The failure of a step after `master` is fast-forwarded that leaves a
change's worktree and branch."""

LEFT_AFTER = mctx("the worktree holds changes made after the commit, in {left}")
"""The reason a worktree stays where it holds changes made after its
change's commit."""


def conflict_paths(output: str) -> tuple[str, ...] | None:
    """The paths in which `output` gives that a change's rebase conflicts,
    or None where it refuses no change for a conflict."""
    m = re.search(form(REFUSED + CONFLICT, {"branch": r"\S+", "onto": r"\S+",
                                            "paths": r"(?P<paths>.*?)"}), output)
    return None if m is None else split_paths(m["paths"])


def left_edits(output: str) -> bool:
    """Whether `output` gives that `master` is fast-forwarded and a
    worktree stays for changes made after its change's commit."""
    text = STAYS.format(master=BASE, why=LEFT_AFTER, worktree="{worktree}", branch="{branch}")
    return re.search(form(text, {"left": r".+?", "worktree": r"\S+", "branch": r"\S+"}),
                     output) is not None


def outside_work() -> tuple[str, str, str]:
    """The pathspec of every path of a worktree but `work` and what lies
    under it (`checkout.work`).

    The exclude items name `work` by a glob: `git add` exits 1 on an
    ignored path that a pathspec item names literally, an exclude item
    among them."""
    name = checkout.work().name
    glob = f"{name[:-1]}[{name[-1]}]"
    return (".", f":(exclude,top,glob){glob}", f":(exclude,top,glob){glob}/**")


def changed_outside_work(worktree: Path, base: str) -> list[str]:
    """The paths of `worktree` outside `work` (`outside_work`) whose
    content differs from the commit `base` (`checkout.changed_paths`),
    sorted."""
    return sorted(c.path for c in checkout.changed_paths(worktree, base, *outside_work()))


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


CONTEXT_WRITE = ("scripts/context.py", "--write")
"""The command, after `uv run python`, that writes the generated files."""


def check(tree: Path, main: Path, base: str, touched: set[str]) -> Path:
    """Run in `tree` the checks of changes from the commit `base` that touch
    `touched`, or refuse; the gate's out-dir."""
    gate_out = tempfile.mkdtemp(prefix="merge-change-gate-")
    gate = Check(("uv", "run", "python", "scripts/gate.py", "--outputs-only", "--affected",
                  base, gate_out))
    context = Check(("uv", "run", "python", *CONTEXT_WRITE))
    code = ([Check(("uv", "run", "pyright")), Check(("uv", "run", "pytest", "-q"))]
            if code_paths(tree, main, touched) else [])
    run_checks(tree, [MARKDOWN_CHECK, context, gate, *code])
    return Path(gate_out)


def run_checks(tree: Path, checks: Sequence[Check]) -> None:
    """Run `checks` in `tree` concurrently, and refuse where any fails."""
    failed = failures(tree, checks)
    if failed:
        raise Refused("\n".join(failed))


def refuse_main_touched(main: Path, touched: Mapping[Path, frozenset[str]]) -> dict[str, str]:
    """Refuse where the main tree has uncommitted changes to a path a change
    touches, `touched` giving the paths each worktree's change touches,
    other than a carried file, as the module docstring gives it. Return
    each carried file, with the hash of its blob."""
    every = set().union(*touched.values())
    records = {w: carried(w) for w in touched}
    hit: list[str] = []
    replaced: dict[str, str] = {}
    for c in checkout.changed_paths(main, "HEAD"):
        if c.path not in every:
            continue
        hashes = {records[w].get(c.path) for w, paths in touched.items() if c.path in paths}
        recorded = hashes.pop() if len(hashes) == 1 else None
        if c.change is checkout.Change.UNTRACKED and recorded is not None:
            if checkout.git_out(main, "hash-object", "--", c.path).strip() == recorded:
                replaced[c.path] = recorded
                continue
        hit.append(c.path)
    hit.sort()
    if hit:
        raise Refused(f"the main tree {main} has uncommitted changes the fast-forward "
                      "would touch:\n" + "\n".join(hit))
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


def stage(worktree: Path, main: Path, backup: Path) -> None:
    """Stage every uncommitted change of the worktree outside `work`
    (`outside_work`), with a copy of its
    index kept at `backup` first, and refuse where `refuse_gitlinks` does,
    with the index put back."""
    shutil.copy2(index_file(worktree), backup)
    checkout.git_out(worktree, "add", "-A", "--", *outside_work())
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
    index at `backup`; and refuse, with the paths git leaves unmerged, or,
    where it leaves none, as a failure that is no conflict."""
    say(mctx("rebasing {branch} onto {onto}").format(
        branch=change.branch, onto=onto_name), flush=True)
    with timed(mctx("the rebase of {branch}").format(branch=change.branch)):
        done = checkout.git(change.worktree, "rebase", onto)
    if done.returncode == 0:
        return
    unmerged = checkout.git_out(change.worktree, "diff", "--name-only",
                                "--diff-filter=U").splitlines()
    checkout.git_out(change.worktree, "rebase", "--abort")
    if restore and change.backup is not None:
        checkout.git_out(change.worktree, "reset", "-q", "--soft", change.before)
        shutil.copy2(change.backup, index_file(change.worktree))
    refusal = (CONFLICT.format(branch=change.branch, onto=onto_name, paths=PATHS_SEP.join(unmerged))
               if unmerged else UNMERGED_NONE.format(branch=change.branch, onto=onto_name))
    raise Refused(refusal + "\n" + said(done))


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
    base = checkout.git_out(worktree, "merge-base", BASE, "HEAD").strip()
    touched = set(changed_outside_work(worktree, base))
    if not touched:
        raise Refused(f"{branch} holds no change against {BASE}")
    refuse_main_touched(main, {worktree: frozenset(touched)})

    set_up_submodules(worktree, main)
    refuse_dirty_submodules(worktree)
    before = checkout.git_out(worktree, "rev-parse", "HEAD").strip()
    committing = bool(changed_outside_work(worktree, "HEAD"))
    stage(worktree, main, backup)
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


def merge_alone(main: Path, change: Change) -> None:
    """Rebase the change's branch onto `master`, run the checks on it, and
    land it, or refuse."""
    onto = checkout.git_out(main, "rev-parse", BASE).strip()
    rebase(change, onto, BASE, restore=True)
    try:
        set_up_submodules(change.worktree, main)
        gate_out = check(change.worktree, main, onto, set(change.touched))
    except Refused as exc:
        checkout.git_out(change.worktree, "reset", "-q", "--mixed", onto)
        raise Refused(f"{exc}\n{change.branch} is moved back to {BASE}'s commit "
                      f"{onto[:12]}, and the change stands uncommitted in "
                      f"{change.worktree}") from exc
    land(main, [change], gate_out)


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


def land(main: Path, changes: Sequence[Change], gate_out: Path) -> None:
    """Fast-forward `master` to the top of `changes`, write the context in
    the main tree, adopt the dependency record the gate wrote into
    `gate_out`, and remove each change's worktree and branch."""
    replaced = refuse_main_touched(main, {c.worktree: c.touched for c in changes})
    modes = {p: (main / p).stat().st_mode for p in replaced}
    for p in sorted(replaced):
        (main / p).unlink()
    top = changes[-1].branch
    say(f"fast-forwarding {BASE} to {top}", flush=True)
    done = checkout.git(main, "merge", "--ff-only", "-q", top)
    if done.returncode != 0:
        for p, blob in sorted(replaced.items()):
            (main / p).write_bytes(subprocess.run(["git", "cat-file", "blob", blob], cwd=main,
                                                  capture_output=True, check=True).stdout)
            os.chmod(main / p, modes[p])
        raise Failed(f"fast-forwarding {BASE} failed; {top} is committed and "
                     f"rebased in {changes[-1].worktree}:\n{said(done)}")

    for argv in (CONTEXT_WRITE,
                 ("scripts/gate.py", "--adopt-record", str(gate_out))):
        shown = " ".join(argv)
        say(mctx("running {shown} in the main tree").format(shown=shown),
              flush=True)
        with timed(shown):
            done = run_in(main, ("uv", "run", "python", *argv))
        if done.returncode != 0:
            raise Failed(mctx("{master} is fast-forwarded, and {shown} failed in {main}; the "
                              "worktrees and branches of {branches} stay:").format(
                master=BASE, shown=shown, main=main,
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
        raise Refused(mctx("the worktrees belong to more than one repository: {main}, "
                           "{others}").format(main=main, others=", ".join(others)))
    main_branch = branch_of(main)
    if main_branch != BASE:
        raise Refused(f"the main tree {main} stands on {main_branch}, not {BASE}")
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
                say("holding the merge lock", flush=True)
                return land_all(main, changes) and every
        except rwlock.MergeHeld as exc:
            for c in changes:
                checkout.git_out(c.worktree, "reset", "-q", "--mixed", c.before)
            raise Refused(mctx("{exc} Each branch is moved back to the commit it stood on "
                               "before, and its change stands uncommitted in its "
                               "worktree.").format(exc=exc)) from exc


def land_all(main: Path, changes: Sequence[Change]) -> bool:
    """Merge the committed `changes` into `master`: as one stack, or, where
    the stack is refused, one at a time. Whether every change merged."""
    if len(changes) > 1:
        try:
            gate_out = stack(main, changes)
        except Refused as exc:
            say(mctx("the stack is refused, so the changes merge one "
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
        say(f"failed: {exc}", file=sys.stderr)
        return 1
    return 0 if merged else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
