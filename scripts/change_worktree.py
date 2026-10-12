"""Make the worktree of a change. `HELP`, which `--help` prints, gives its
usage form, the worktree's name and branch, and what a run does where the
change already has a worktree."""

import argparse
import shutil
import sys
import textwrap
from pathlib import Path

from controlled_markdown import mctx
from engine import checkout
from handbook.paths import importable

# `scripts/` is no package: the modules below import from there.
importable(checkout.scripts())

from ticket_files import ticket_path  # noqa: E402
from ticket_log import log_moves  # noqa: E402
from ticket_numbers import ticket_number  # noqa: E402
from ticket_reads import read_ticket  # noqa: E402
from transcripts import Refused  # noqa: E402
from tree_reads import main_tree, worktrees  # noqa: E402

from operations.state import Ticket  # noqa: E402
from operations.tracker import WORKTREES, logged_worktree  # noqa: E402
from ticketing.vocabulary import Note  # noqa: E402

HELP = mctx("""
    - Usage:
        ```
        uv run python scripts/change_worktree.py <number> <agent> [--id <agent id>]
        uv run python scripts/change_worktree.py --name <name>
        ```
    - The first form makes the worktree of the change whose ticket has the number `<number>`.
        - `<agent>` and `--id` are the agent and the agent id of the log line it writes, as `file_ticket.py log` takes them.
    - The second form makes the worktree of a change that has no ticket, such as solver work, and writes no log line.
        - `<name>` is the name of its worktree and its branch, a branch name with no `/`.
    - The command prints the path of the worktree, alone on one line.
    - In the first form, where the change has a worktree, the command adds none, writes no line, and prints its path.
        - The change's worktree is the path that the latest line of its log that gives a path under `{worktrees}/` gives, where no line whose note opens with `{rerun}` is that line or follows it, and where that path stands in `git worktree list`.
        - Otherwise `<name>` is `change-<number>`, and after `k` lines whose note opens with `{rerun}`, `change-<number>-run-<k + 1>`.
    - The worktree is `<main tree>/{worktrees}/<name>`, on the branch `<name>`.
        - Where no worktree stands at that path, the command adds it with `git worktree add` on a new branch of that name from `master`.
        - Where one stands there on that branch, as an earlier run left it, it adds none.
    - It then copies in from the main tree each untracked file that the patterns of the main tree's `.worktreeinclude` match.
    - In the first form, it then writes on the ticket the line `worktree <path>` in the status the ticket stands in.
    - The command refuses, adds nothing and writes no line, where a worktree stands at that path on another branch, or where that path or that branch exists with no worktree of that branch at that path.
    """)

BASE = "master"
INCLUDE = ".worktreeinclude"
WORKTREE_NOTE = "worktree"


def name(t: Ticket) -> str:
    """The name of the worktree and the branch `HELP` gives `t`'s run."""
    runs = 1 + sum(line.note.startswith(Note.RERUN) for line in t.log)
    return f"change-{t.number}" if runs == 1 else f"change-{t.number}-run-{runs}"


def branch_exists(main: Path, branch: str) -> bool:
    return checkout.git(main, "show-ref", "--verify", "--quiet", f"refs/heads/{branch}").returncode == 0


def add(main: Path, path: Path, branch: str) -> None:
    """Add the worktree `path` on the branch `branch`, as `HELP` gives,
    unless it stands there."""
    standing = worktrees(main)
    if path in standing:
        if standing[path] != branch:
            raise Refused(mctx("the worktree {path} stands on the branch {found}, not {branch}")
                          .format(path=path, found=standing[path], branch=branch))
        return
    if path.exists() or branch_exists(main, branch):
        raise Refused(mctx("{path} or the branch {branch} exists with no worktree of that branch "
                           "at that path").format(path=path, branch=branch))
    checkout.git_out(main, "worktree", "add", "-q", "-b", branch, str(path), BASE)


def copy_included(main: Path, path: Path) -> None:
    """Copy in from `main` each untracked file the patterns of its
    `.worktreeinclude` match."""
    include = main / INCLUDE
    if not include.is_file():
        return
    listed = checkout.git_out(main, "ls-files", "-z", "--others", "--ignored",
                              f"--exclude-from={include}")
    for rel in sorted(filter(None, listed.split("\0"))):
        target = path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(main / rel, target)


def made(main: Path, branch: str) -> Path:
    """The worktree `branch` names, added where it does not stand and with
    the files `.worktreeinclude` gives copied in."""
    path = main / WORKTREES / branch
    add(main, path, branch)
    copy_included(main, path)
    return path


def of_change(number: str, agent: str, agent_id: str | None) -> Path:
    main = main_tree()
    tickets = main / "tickets"
    ref = ticket_number(number)
    t = read_ticket(ticket_path(tickets, ref))
    logged = logged_worktree(t)
    if logged is not None and logged in worktrees(main):
        return logged
    path = made(main, name(t))
    log_moves(tickets, ref, t.status, agent, t.status, agent_id, f"{WORKTREE_NOTE} {path}")
    return path


def named(branch: str) -> Path:
    main = main_tree()
    if "/" in branch or checkout.git(main, "check-ref-format", "--branch", branch).returncode:
        raise Refused(mctx("`{name}` is no branch name with no `/`").format(name=branch))
    return made(main, branch)


def main() -> int:
    parser = argparse.ArgumentParser(description=textwrap.dedent(HELP).format(rerun=Note.RERUN,
                                                                              worktrees=WORKTREES),
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("number", nargs="?")
    parser.add_argument("agent", nargs="?")
    parser.add_argument("--id", dest="agent_id")
    parser.add_argument("--name")
    args = parser.parse_args()
    if args.name is not None and (args.number or args.agent or args.agent_id):
        parser.error(mctx("`--name` takes no ticket number, agent or agent id"))
    if args.name is None and not (args.number and args.agent):
        parser.error(mctx("a ticket number and an agent, or `--name`, are given"))
    try:
        print(named(args.name) if args.name is not None
              else of_change(args.number, args.agent, args.agent_id))
    except Refused as e:
        print(mctx("refused: {reason}").format(reason=e), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
