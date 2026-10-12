"""The reads of git and of the main worktree that the operator's procedures
take their state from: the worktrees, the commits of `master`, the code
review tags, the standing doc review tags, the task claims, the accepted
gate outputs a change writes, the `mctx` fragments a change adds or
changes, the places a change's fragments had at a launch of a doc editor on
them, and the session's scratchpad directory. `HELP`, which `--help` prints,
gives the usage form of the command that writes those places."""

import argparse
import json
import os
import sys
import textwrap
import time
from pathlib import Path

from controlled_markdown import ControlledMarkdownError, mctx
from controlled_markdown.prose import text_fragments
from engine import checkout
from operations.state import DOC_REVIEW, Commit, Place, Seen
from operations.task_work import CLAIM, tasks_work
from operations.tracker import BASE

HELP = mctx("""
    - Usage:
        ```
        uv run python scripts/tree_reads.py seen <worktree> <directory>
        ```
    - The command writes to a new file `<time>.json` in `<directory>` the file and the text of each fragment whose text the change in `<worktree>` adds or changes, against its merge base with `master`, with `<time>` the time of the write in seconds since the epoch.
        - A file of the change whose text does not read as fragments has no entry.
    - It makes `<directory>` where it does not exist, and prints the path of the file it wrote.
    """)

COMMITS = 300
"""The commits of `master` read for After a batch, newest first."""

CODE_DIRS = ("src/", "scripts/", "tests/")
PROCESS_DIRS = ("prompts/agents/", "src/operations/")
ACCEPTED = "tests/gate/accepted"


def main_tree() -> Path:
    return checkout.main_worktree(checkout.ROOT)


def git(main: Path, *argv: str) -> str:
    return checkout.git_out(main, *argv)


def worktrees(main: Path) -> dict[Path, str | None]:
    return {w.path: w.branch for w in checkout.worktree_list(main)}


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


def code_review(main: Path) -> int | None:
    tags = [int(t.rsplit("/", 1)[1]) for t in git(main, "tag", "-l", "code-review/*").split()
            if t.rsplit("/", 1)[1].isdigit()]
    return max(tags) if tags else None


def doc_reviews(main: Path) -> dict[str, float] | None:
    """The time of the commit each standing doc review tag points at, by
    tag, or None where a tag does not read as a commit."""
    try:
        return {t: float(git(main, "log", "-1", "--format=%ct", f"{t}^{{commit}}"))
                for t in git(main, "tag", "-l", f"{DOC_REVIEW}*").split()}
    except (checkout.GitFailed, ValueError):
        return None


def claims(main: Path) -> dict[str, str]:
    return {p.parent.name: p.read_text().strip()
            for p in tasks_work(main).glob(f"*/{CLAIM}")}


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
    base = git(tree, "merge-base", "HEAD", BASE).strip()
    names = {c.path for c in checkout.changed_paths(tree, base, "*.py", "*.js")}
    out: list[Place] = []
    for name in sorted(names):
        path = tree / name
        if not path.is_file():
            continue
        old: set[str] = set()
        if git(tree, "ls-tree", "--name-only", base, "--", name).strip():
            old = {f.text for f in text_fragments(git(tree, "show", f"{base}:{name}"), path, name)}
        try:
            now = list(text_fragments(path.read_text(), path, name))
        except SyntaxError as e:
            out.append(Place(name, e.lineno or 1, None))
            continue
        except ControlledMarkdownError as e:
            out.append(Place(name, e.line or 1, None))
            continue
        out += [Place(name, f.line, f.text) for f in now if f.text not in old]
    return tuple(sorted(out, key=lambda p: (p.file, p.line)))


def write_seen(tree: Path, directory: Path) -> Path:
    """Write the file and the text of each place of `fragments(tree)` that
    has a text to a new file of `directory`, named by the time of the
    write, whole or not at all."""
    directory.mkdir(parents=True, exist_ok=True)
    out = directory / f"{time.time():.6f}.json"
    part = out.with_suffix(".part")
    part.write_text(json.dumps([[p.file, p.text] for p in fragments(tree) if p.text is not None]))
    os.replace(part, out)
    return out


def read_seen(directory: Path) -> tuple[Seen, ...]:
    """The files `write_seen` wrote to `directory`, in the order of their
    time."""
    out: list[Seen] = []
    for path in directory.glob("*.json"):
        try:
            entries = json.loads(path.read_text())
        except (OSError, ValueError):
            entries = None
        places = (frozenset((f, t) for f, t in entries)
                  if isinstance(entries, list) and all(
                      isinstance(e, list) and len(e) == 2 and all(isinstance(x, str) for x in e)
                      for e in entries)
                  else None)
        out.append(Seen(float(path.stem), places))
    return tuple(sorted(out, key=lambda s: s.time))


def scratch(session: str) -> Path:
    """The session's scratchpad directory, as the section `Launching` of
    `prompts/agents/notes/launching.md` gives it, for a session that
    started in the main worktree, as the coordinator's does."""
    started = str(main_tree())
    return (Path(f"/private/tmp/claude-{os.getuid()}") / started.replace("/", "-") / session
            / "scratchpad")


def main() -> int:
    parser = argparse.ArgumentParser(description=textwrap.dedent(HELP),
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    seen = sub.add_parser("seen")
    seen.add_argument("worktree", type=Path)
    seen.add_argument("directory", type=Path)
    args = parser.parse_args()
    print(write_seen(args.worktree, args.directory))
    return 0


if __name__ == "__main__":
    sys.exit(main())
