"""File an issue under the main tree's `issues/new/`, from the main tree or
any worktree of it. `HELP`, which `--help` prints, says how an agent calls
it."""

import os
import re
import sys
import tempfile
from pathlib import Path

from controlled_markdown import mctx
from engine import checkout

HELP = mctx("""
    - Usage:
        ```
        uv run python scripts/file_issue.py <unix time> <source> <agent> <<'EOF'
        ---
        kind: <kind>
        ---
        # <target>: <what is wrong in it>

        ## Effect
        <its effect>

        ## Evidence
        <the evidence>
        EOF
        ```
    - The command reads one issue from stdin, names it `<unix time>-<source>-<agent>-<i>.md`, writes it under `issues/new/` in the main tree, and prints the path it wrote.
    - `<i>` is 1 more than the largest `<i>` of a file under `issues/` with the same time, source and agent, so the issues of one `date +%s` count from 1.
    - Give one `date +%s` as `<unix time>` to every call that files your issues.
    - The command refuses, and writes nothing, where the text on stdin does not have the form above.
    """)

STATUSES = ("new", "assigned", "resolved")
"""The directories under `issues/` that an issue's file moves between."""

FORM = re.compile(r"---\nkind: \S+\n---\n# .+: .+\n\n## Effect\n(?:.*\n)*## Evidence(?:\n|$)")
"""The front matter, title and sections an issue opens with."""

NAME_PART = re.compile(r"[^\s/]+")


class Refused(Exception):
    """A call the command does not carry out, with the reason."""


def file_issue(issues: Path, time: str, source: str, agent: str, text: str) -> Path:
    """Writes `text` as a new file under `issues/new/` and returns its path.
    An existing file is never replaced: a name another call took first moves
    this one to the next `<i>`."""
    if not time.isdigit():
        raise Refused(mctx("the unix time `{time}` is not a number").format(time=time))
    for part in (source, agent):
        if not NAME_PART.fullmatch(part):
            raise Refused(mctx("`{part}` is not one word without `/`").format(part=part))
    if not FORM.match(text):
        raise Refused(mctx("the issue on stdin does not have the form `--help` shows"))
    prefix = f"{time}-{source}-{agent}-"
    taken = [int(m.group(1)) for status in STATUSES
             for p in (issues / status).glob(f"{prefix}*.md")
             if (m := re.fullmatch(re.escape(prefix) + r"(\d+)\.md", p.name))]
    new = issues / "new"
    new.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=new, prefix=".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(text)
        i = max(taken, default=0) + 1
        while True:
            path = new / f"{prefix}{i}.md"
            try:
                os.link(tmp, path)
                return path
            except FileExistsError:
                i += 1
    finally:
        Path(tmp).unlink(missing_ok=True)


def main(args: list[str]) -> int:
    if args and args[0] in ("--help", "-h"):
        print(HELP)
        return 0
    if len(args) != 3:
        print(HELP, file=sys.stderr)
        return 2
    issues = checkout.main_worktree(checkout.ROOT) / "issues"
    try:
        time, source, agent = args
        print(file_issue(issues, time, source, agent, sys.stdin.read()))
    except Refused as e:
        print(mctx("refused: {reason}").format(reason=e), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
