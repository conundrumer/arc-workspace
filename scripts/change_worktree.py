"""Make the worktree of a change. `HELP`, which `--help` prints, gives its
usage form, the worktree's name and branch, and what a run does where the
change already has a worktree."""

import argparse
import json
import shutil
import sys
import textwrap
from pathlib import Path

from controlled_markdown import mctx
from engine import checkout
from handbook.paths import importable

# `scripts/` is no package: the modules below import from there.
importable(checkout.scripts())

from bottlenecks import scope_paths  # noqa: E402
from ticket_files import ticket_path  # noqa: E402
from ticket_log import log_moves  # noqa: E402
from ticket_numbers import ticket_number  # noqa: E402
from ticket_reads import read_ticket  # noqa: E402
from transcripts import Refused  # noqa: E402
from tree_reads import main_tree, worktrees  # noqa: E402

from operations.state import Ticket  # noqa: E402
from operations.tracker import BASE, WORKTREES, fingerprint, logged_worktree  # noqa: E402
from ticketing.vocabulary import Note  # noqa: E402

HELP = mctx("""
    - Usage:
        ```
        uv run python scripts/change_worktree.py <number> <agent> [--id <agent id>]
        uv run python scripts/change_worktree.py --name <name>
        uv run python scripts/change_worktree.py --fingerprint <worktree>
        ```
    - The first form makes the worktree of the change whose ticket has the number `<number>`, writes on the ticket the line `worktree <path>` in the status the ticket stands in, and prints its path.
        - `<agent>` and `--id` are the agent and the agent id of that log line, as `file_ticket.py log` takes them.
        - Where the latest line of the ticket's log that gives a path under `{worktrees}/` gives a worktree that `git worktree list` lists, and no line whose note opens with `{rerun}` is that line or follows it, that worktree is the change's, and the command adds none.
        - Otherwise `<name>` is `change-<number>`, and after `k` lines whose note opens with `{rerun}`, `change-<number>-run-<k + 1>`.
    - The second form makes the worktree of a change that has no ticket, writes no log line, and prints its path. `<name>` is a branch name with no `/`.
    - The third form prints a digest of the diff of `<worktree>` from its merge base with `master` and of each untracked file there that git does not ignore, and makes or changes nothing.
    - The worktree `<name>` is `<main tree>/{worktrees}/<name>`, on the branch `<name>` from `master`, and the command adds it where it does not stand there.
    - The command copies into the worktree from the main tree each untracked file that the patterns of the main tree's `.worktreeinclude` match, and, in the first form, each untracked file that git does not ignore at a path that the ticket's `## Scope` gives, where the worktree holds no file at that path.
    - The command refuses, adds nothing and writes no line, where a worktree stands at that path on another branch, or where that path or that branch exists with no worktree of that branch at that path.
    """)

INCLUDE = ".worktreeinclude"
CARRIED = "carried-untracked.json"
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


def copy_in(main: Path, path: Path, rel: str) -> None:
    target = path / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(main / rel, target)


def copy_included(main: Path, path: Path) -> None:
    """Copy in from `main` each untracked file the patterns of its
    `.worktreeinclude` match."""
    include = main / INCLUDE
    if not include.is_file():
        return
    listed = checkout.git_out(main, "ls-files", "-z", "--others", "--ignored",
                              f"--exclude-from={include}")
    for rel in sorted(filter(None, listed.split("\0"))):
        copy_in(main, path, rel)


def carried_record(worktree: Path) -> Path:
    """The record of the files `copy_scope_untracked` carried into
    `worktree`, in its own git directory, which the worktree's removal
    deletes."""
    return Path(checkout.git_out(worktree, "rev-parse", "--path-format=absolute",
                                 "--git-path", CARRIED).strip())


def carried(worktree: Path) -> dict[str, str]:
    record = carried_record(worktree)
    return json.loads(record.read_text()) if record.is_file() else {}


def copy_scope_untracked(main: Path, path: Path, t: Ticket) -> None:
    """Copy into the worktree `path` each file the `Scope` of `t` names that
    `main` holds untracked, as `HELP` gives, and add it to `carried_record`
    with the hash of its blob, which it writes into the object store, so
    that the blob outlives the main tree's file."""
    scope = sorted(scope_paths(t, main))
    if not scope:
        return
    listed = checkout.untracked(main, *(f":(literal){p}" for p in scope))
    hashes = carried(path)
    new = False
    for rel in sorted(set(listed) & set(scope)):
        if (path / rel).exists():
            continue
        new = True
        copy_in(main, path, rel)
        hashes[rel] = checkout.git_out(main, "hash-object", "-w", "--", rel).strip()
    if new:
        carried_record(path).write_text(json.dumps(hashes, indent=1, sort_keys=True) + "\n")


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
    path = logged if logged is not None and logged in worktrees(main) else made(main, name(t))
    copy_scope_untracked(main, path, t)
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
    parser.add_argument("--fingerprint", metavar="<worktree>")
    args = parser.parse_args()
    if args.fingerprint is not None:
        if args.number or args.agent or args.agent_id or args.name is not None:
            parser.error(mctx("`--fingerprint` takes no ticket number, agent, agent id or "
                              "`--name`"))
        print(fingerprint(Path(args.fingerprint)))
        return 0
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
