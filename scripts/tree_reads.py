"""The reads of git and of the main worktree that the operator's procedures
take their state from: the worktrees, the commits of `master`, the code
review tags, the standing doc review tags, the task claims, the accepted
gate outputs a change writes, the `mctx` fragments a change adds or
changes, and the session's scratchpad directory."""

import os
from collections.abc import Hashable
from pathlib import Path

from state_reads import file_text, listed, stat_of, stat_read, state_cache

from controlled_markdown import ControlledMarkdownError
from controlled_markdown.prose import Fragment, text_fragments
from engine import checkout
from operations.state import DOC_REVIEW, Commit, Place
from operations.task_work import CLAIM, tasks_work
from operations.worktrees import BASE

COMMITS = 300
"""The commits of `master` read for After a batch, newest first."""

CODE_DIRS = ("src/", "scripts/", "tests/")
PROCESS_DIRS = ("prompts/agents/", "src/operations/")
ACCEPTED = "tests/gate/accepted"


@state_cache(lambda: git_entry(checkout.ROOT))
def main_tree() -> Path:
    return checkout.main_worktree(checkout.ROOT)


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
    for chunk in git(main, "log", BASE, f"-n{COMMITS}", "--format=%x00%H %ct %s",
                     "--name-only").split("\0")[1:]:
        head, _, names = chunk.partition("\n")
        sha, ct, subject = (head.split(" ", 2) + [""])[:3]
        files = names.split()
        out.append(Commit(sha, float(ct), any(n.startswith(CODE_DIRS) for n in files), subject,
                          any(n.startswith(PROCESS_DIRS) for n in files)))
    return tuple(out)


@state_cache(lambda main: refs_stamp(main, "tags"))
def code_review(main: Path) -> int | None:
    tags = [int(t.rsplit("/", 1)[1]) for t in git(main, "tag", "-l", "code-review/*").split()
            if t.rsplit("/", 1)[1].isdigit()]
    return max(tags) if tags else None


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


def gate_outputs(tree: Path) -> tuple[str, ...]:
    """The accepted gate outputs the change in the worktree `tree` writes,
    against `master`."""
    return tuple(sorted({c.path for c in checkout.changed_paths(tree, BASE, ACCEPTED)}))


def fragments(tree: Path) -> tuple[Place, ...]:
    """The fragments whose text the change in the worktree `tree` adds or
    changes, against its merge base with `master`: those of each `.py` and
    `.js` file the diff names whose text is not the text of a fragment of
    that file at the merge base, so a fragment that only moved is no
    change. A file whose text in the worktree does not read as fragments,
    as a Python file that does not parse or an `mctx` call with no literal,
    is one place in their stead, at the line of the error, or line 1 where
    the error gives none."""
    base = merge_base(tree)
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


@state_cache(lambda tree: (trees_stamp(main_tree()), refs_stamp(main_tree(), "heads")))
def merge_base(tree: Path) -> str:
    """The merge base of the worktree `tree`'s `HEAD` with `master`."""
    return git(tree, "merge-base", "HEAD", BASE).strip()


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

