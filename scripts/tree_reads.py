"""The reads of git and of the main worktree that the operator's procedures
take their state from: the worktrees, the commits of `master`, the code
and lib review tags, the standing doc review tags, the task claims and restores, the solvers that stand, the accepted
gate outputs a change writes, the `mctx` fragments a change adds or
changes, and the session's scratchpad directory, and the run of the main
tree's copy of a script in place of a worktree's copy."""

import os
import subprocess
from collections.abc import Callable, Hashable
from pathlib import Path

from file_reads import file_text, listed, stat_of, stat_read
from state_reads import state_cache

from controlled_markdown import ControlledMarkdownError, mctx
from controlled_markdown.prose import Fragment, text_fragments
from engine import checkout
from operations.state import DOC_REVIEW, Baseline, Commit, NoBaseline, PathSet, Place, Restore, Review
from operations.task_dirs import CLAIM, restore_records, restores_file, tasks_work
from operations import worktrees as change_worktree
from operations.worktrees import BASE
from solver.vocabulary import SOLVER_SUFFIX
from transcript_snapshots import Refused

COMMITS = 300
"""The number of commits of `master` the state reads, newest first."""

PROCESS_DIRS = PathSet(("prompts/agents/", "src/operations/"))
ACCEPTED = "tests/gate/accepted"


@state_cache(lambda: git_entry(checkout.ROOT))
def main_tree() -> Path:
    return checkout.main_worktree(checkout.ROOT)


def run_in_main(script: str, args: list[str]) -> int | None:
    """Runs the main tree's copy of the script `scripts/<script>` with
    `args` and this process's stdin, and returns its exit status, where
    the running copy is another one; None where the running copy is the
    main tree's."""
    main = main_tree()
    copy = main / "scripts" / script
    if (checkout.scripts() / script).resolve() == copy.resolve():
        return None
    if not copy.exists():
        raise Refused(mctx("the main tree has no `scripts/{script}`").format(script=script))
    return subprocess.run(["uv", "run", "--project", str(main), "python", str(copy), *args],
                          env=checkout.tree_env()).returncode


def git(main: Path, *argv: str) -> str:
    return checkout.git_out(main, *argv)


def git_entry(tree: Path) -> Hashable:
    """What `common_dir` of the worktree `tree` rests on: its `.git`, a
    directory in the main worktree, whose stat each write of its index
    changes, and a file that gives the git directory in a linked one."""
    entry = tree / ".git"
    return "directory" if entry.is_dir() else stat_of(entry)


@state_cache(git_entry)
def common_dir(tree: Path) -> Path:
    """The common git directory of the repository of the worktree `tree`."""
    return checkout.git_common_dir(tree)


def refs_stamp(main: Path, kind: str) -> Hashable:
    """What the refs under `refs/<kind>` of the repository whose main tree
    is `main` rest on: git writes a ref by renaming a lock file into place,
    which changes the stat of the directory that holds it, and rewrites
    `packed-refs` whole."""
    common = common_dir(main)
    dirs: list[Path] = []
    todo = [common / "refs" / kind]
    while todo:
        d = todo.pop()
        dirs.append(d)
        todo += [d / e.name for e in listed(d) if e.is_dir and not e.is_link]
    return tuple((d, stat_of(d)) for d in dirs), stat_of(common / "packed-refs")


def trees_stamp(main: Path) -> Hashable:
    """What `git worktree list` of the repository whose main tree is `main`
    gives of each worktree rests on: the main tree's `HEAD`, and each linked
    worktree's directory under `worktrees`, with its `HEAD`, its `gitdir`,
    which gives its path, and its `locked`."""
    common = common_dir(main)
    trees = sorted(e.name for e in listed(common / "worktrees") if e.is_dir)
    return stat_of(common / "HEAD"), stat_of(common / "worktrees"), tuple(
        (t, *(stat_of(common / "worktrees" / t / f) for f in ("HEAD", "gitdir", "locked")))
        for t in trees)


@state_cache(trees_stamp)
def worktrees(main: Path) -> dict[Path, str | None]:
    return {w.path: w.branch for w in checkout.worktree_list(main)}


@state_cache(lambda main: refs_stamp(main, "heads"))
def commits(main: Path) -> tuple[Commit, ...]:
    out: list[Commit] = []
    for head, files in logged(main, "%H %ct %s", BASE, f"-n{COMMITS}"):
        sha, ct, subject = (head.split(" ", 2) + [""])[:3]
        out.append(Commit(sha, float(ct),
                          frozenset(r for r in Review if changes(files, r.facts.paths)), subject,
                          changes(files, PROCESS_DIRS), frozenset(files)))
    return tuple(out)


def logged(main: Path, form: str, *argv: str) -> list[tuple[str, list[str]]]:
    """The `git log` of `argv`: each commit's line in the format `form`,
    with the files it changes."""
    out: list[tuple[str, list[str]]] = []
    for chunk in git(main, "log", *argv, f"--format=%x00{form}", "--name-only").split("\0")[1:]:
        head, _, names = chunk.partition("\n")
        out.append((head, names.split()))
    return out


def changes(files: list[str], paths: PathSet) -> bool:
    return any(paths.covers(n) for n in files)


@state_cache(lambda main, review: (refs_stamp(main, "tags"), refs_stamp(main, "heads")))
def baseline(main: Path, review: Review) -> Baseline | NoBaseline:
    tags = [n for t in git(main, "tag", "-l", f"{review.value}*").split()
            if (n := review.number(t)) is not None]
    if not tags:
        return NoBaseline.NO_TAG
    n = max(tags)
    try:
        unreviewed = logged(main, "%H", f"{review.tag(n)}..{BASE}")
    except checkout.GitFailed:
        return NoBaseline.GIT_FAILED
    return Baseline(n, tuple(sha for sha, files in unreviewed if changes(files, review.facts.paths)))


@state_cache(lambda main: refs_stamp(main, "tags"))
def doc_reviews(main: Path) -> dict[str, float] | None:
    """The time of the commit each standing doc review tag points at, by
    tag, or None where a tag does not read as a commit."""
    try:
        return {t: float(git(main, "log", "-1", "--format=%ct", f"{t}^{{commit}}"))
                for t in git(main, "tag", "-l", f"{DOC_REVIEW}*").split()}
    except (checkout.GitFailed, ValueError):
        return None


def claims(main: Path) -> dict[str, str]:
    work = tasks_work(main)
    return {e.name: file_text(work / e.name / CLAIM).strip()
            for e in listed(work) if e.is_dir and stat_read(work / e.name / CLAIM) is not None}


def solvers(main: Path) -> frozenset[str]:
    """The tasks whose solver stands in the main tree `main`."""
    return frozenset(e.name.removesuffix(SOLVER_SUFFIX) for e in listed(main / checkout.SOLVERS)
                     if e.is_file and e.name.endswith(SOLVER_SUFFIX))


def restores(main: Path) -> dict[str, tuple[Restore, ...]]:
    path = restores_file(main)
    return restore_records(file_text(path)) if stat_read(path) is not None else {}


def gate_outputs(tree: Path) -> tuple[str, ...]:
    """The accepted gate outputs the change in the worktree `tree` writes,
    against its merge base with `master`; none where the worktree is gone
    (`standing`)."""
    base = merge_base(tree)
    if base is None:
        return ()
    return standing(tree, lambda: tuple(sorted(
        {c.path for c in checkout.changed_paths(tree, base, ACCEPTED)})), ())


def fragments(tree: Path) -> tuple[Place, ...]:
    """The fragments whose text the change in the worktree `tree` adds or
    changes, against its merge base with `master`: those of each `.py` and
    `.js` file the diff names whose text is not the text of a fragment of
    that file at the merge base, so a fragment that only moved is no
    change. A file whose text in the worktree does not read as fragments,
    as a Python file that does not parse or an `mctx` call with no literal,
    is one place in their stead, at the line of the error, or line 1 where
    the error gives none. None where the worktree is gone (`standing`)."""
    base = merge_base(tree)
    if base is None:
        return ()
    return standing(tree, lambda: changed_fragments(tree, base), ())


def changed_fragments(tree: Path, base: str) -> tuple[Place, ...]:
    """`fragments` of the worktree `tree` against its merge base `base`."""
    names = {c.path for c in checkout.changed_paths(tree, base, "*.py", "*.js")}
    out: list[Place] = []
    for name in sorted(names):
        path = tree / name
        if not path.is_file():
            continue
        old = {f.text for f in fragments_at(tree, base, name)}
        try:
            now = fragments_of(path.read_text(), path, name)
        except SyntaxError as e:
            out.append(Place(name, e.lineno or 1, None))
            continue
        except ControlledMarkdownError as e:
            out.append(Place(name, e.line or 1, None))
            continue
        out += [Place(name, f.line, f.text) for f in now if f.text not in old]
    return tuple(sorted(out, key=lambda p: (p.file, p.line)))


def standing[T](tree: Path, read: Callable[[], T], gone: T) -> T:
    """What `read`, a read of the worktree `tree`, gives, or `gone` where it
    fails with an `OSError` or a `GitFailed` and the directory `tree` no
    longer stands, as a removal of the worktree before or while the read
    runs leaves it: git finds no directory to run in, or refuses."""
    try:
        return read()
    except (OSError, checkout.GitFailed):
        if tree.is_dir():
            raise
        return gone


@state_cache(lambda tree: (trees_stamp(main_tree()), refs_stamp(main_tree(), "heads")))
def merge_base(tree: Path) -> str | None:
    """`worktrees.merge_base` of `tree`, or None where the worktree is gone
    (`standing`)."""
    return standing(tree, lambda: change_worktree.merge_base(tree), None)


@state_cache(lambda tree, base, name: ())
def fragments_at(tree: Path, base: str, name: str) -> tuple[Fragment, ...]:
    """The fragments of the file `name` at the commit `base`, none where it
    has no such file: a commit's files do not change."""
    if not git(tree, "ls-tree", "--name-only", base, "--", name).strip():
        return ()
    return fragments_of(git(tree, "show", f"{base}:{name}"), tree / name, name)


@state_cache(lambda text, path, name: ())
def fragments_of(text: str, path: Path, name: str) -> tuple[Fragment, ...]:
    """`text_fragments` of `text`, the text of the file `path`, parsed once
    for each text."""
    return tuple(text_fragments(text, path, name))


def scratch(session: str) -> Path:
    """The session's scratchpad directory, as the section `Launching` of
    `prompts/agents/notes/launching.md` gives it, for a session that
    started in the main worktree, as the coordinator's does."""
    started = str(main_tree())
    return (Path(f"/private/tmp/claude-{os.getuid()}") / started.replace("/", "-") / session
            / "scratchpad")

