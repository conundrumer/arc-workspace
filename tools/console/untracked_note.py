"""PreToolUse hook for the console committer: refuse to stage or commit a
file git does not already track.

The console commits the approved solvers itself, and the committer runs after
that, so an untracked file left in the tree is one no one approved. The brief
already says to leave those alone; the hook is what holds when it is not read.

A staging call has to arrive on its own, because a command that stages and
commits at once stages after this hook has read the index.
"""
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(os.environ.get("CLAUDE_PROJECT_DIR") or ".")
OPERATORS = {"&&", "||", ";", "|", "&"}
GLOBALS = ("-C", "-c", "--git-dir", "--work-tree", "--exec-path")
ONE_CALL = ("Run one git command per Bash call, with nothing staging around it."
            " The console reads the index before the call runs, so a command that"
            " stages and commits at once goes unread.")
ROOT_ONLY = "Run git from the repo root, with no -C, -c, --git-dir, or --work-tree."


def git(*args: str, index: str | None = None) -> str:
    """One git call, optionally against an index file of our own."""
    env = {**os.environ, "GIT_INDEX_FILE": index} if index else None
    out = subprocess.run(["git", *args], cwd=ROOT, env=env, capture_output=True,
                         text=True, stdin=subprocess.DEVNULL, timeout=300)
    return out.stdout


def refuse(note: str) -> None:
    print(note, file=sys.stderr)
    sys.exit(2)


def listing(paths: list[str]) -> str:
    """A refusal names a few paths, because a sweep can name hundreds."""
    head = ", ".join(paths[:8])
    return head if len(paths) <= 8 else f"{head}, and {len(paths) - 8} more"


def added(index: str | None = None) -> list[str]:
    """The paths an index holds that HEAD does not."""
    out = git("diff", "--cached", "--name-only", "--diff-filter=A", index=index)
    return sorted(p for p in out.split("\n") if p)


def check_add(argv: list[str]) -> None:
    """What this add would stage, read off a copy of the index.

    The add runs for real against that copy, so it needs no reading of pathspecs
    and the working index stays as it was. What it writes to the object store is
    unreferenced, and git drops it with the rest of the loose objects.
    """
    with tempfile.TemporaryDirectory() as tmp:
        copy = str(Path(tmp) / "index")
        live = ROOT / git("rev-parse", "--git-path", "index").strip()
        if live.exists():
            shutil.copyfile(live, copy)
        git(*argv[1:], index=copy)
        new = added(copy)
    if new:
        refuse("This add stages files git does not track: " + listing(new)
               + "\nStage only tracked files. An untracked file is one nobody approved;"
                 " leave it in the working tree and say so in your report.")


def check_commit() -> None:
    """What is staged already, against what HEAD holds."""
    new = added()
    if new:
        refuse("The index holds files HEAD does not track: " + listing(new)
               + "\nUnstage them with `git restore --staged` and commit the tracked"
                 " changes alone. An untracked file is one nobody approved.")


def segments(argv: list[str]) -> list[list[str]]:
    """The command's parts, one per call the shell would make."""
    parts, seg = [], []
    for token in argv:
        if token in OPERATORS:
            parts.append(seg)
            seg = []
        else:
            seg.append(token)
    parts.append(seg)
    return [seg for seg in parts if seg]


def verb(seg: list[str]) -> str:
    """The verb of one git call, or nothing for a call that is not git's."""
    if "git" in seg[1:]:
        refuse(ONE_CALL)
    if seg[0] != "git":
        return ""
    for token in seg[1:]:
        if token.startswith(GLOBALS):
            refuse(ROOT_ONLY)
        if not token.startswith("-"):
            return token
    return ""


def check(command: str) -> None:
    """What one Bash command would stage, before the shell runs it."""
    if not re.search(r"\bgit\b.*\b(add|commit)\b", command, re.S):
        return
    try:
        lex = shlex.shlex(command, posix=True, punctuation_chars=True)
        lex.whitespace_split = True
        argv = list(lex)
    except ValueError:
        # A command that does not lex still says whether it stages.
        if re.search(r"\bgit\b[^|;&]*\badd\b", command):
            refuse(ONE_CALL)
        check_commit()
        return
    parts = segments(argv)
    verbs = [verb(seg) for seg in parts]
    if "add" in verbs:
        if len(parts) > 1:
            refuse(ONE_CALL)
        check_add(parts[verbs.index("add")])
    if "commit" in verbs:
        check_commit()


def main() -> None:
    try:
        ev = json.load(sys.stdin)
    except (ValueError, OSError):
        return
    if ev.get("tool_name") != "Bash":
        return
    try:
        check(str(ev.get("tool_input", {}).get("command", "")))
    except Exception as exc:  # a check that cannot run refuses the call
        refuse(f"The console could not check what this call stages: {exc!r}")


if __name__ == "__main__":
    main()
