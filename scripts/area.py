"""Print the tickets that bear on a set of files: the open changes whose
Scope gives one of them, and the recent tickets whose text names one.
`HELP`, which `--help` prints, gives the usage form and the rules of each
list."""

import argparse
import sys
import textwrap
import time
from pathlib import Path

from controlled_markdown import mctx
from handbook.paths import scripts_importable

scripts_importable()

from ticket_paths import scope_paths, ticket_text  # noqa: E402
from ticketing.references import refers, word_forms  # noqa: E402
from ticket_reads import read_tickets  # noqa: E402
from transcript_snapshots import Refused, print_refused  # noqa: E402
from tree_reads import main_tree  # noqa: E402

from operations.state import Ticket  # noqa: E402
from ticketing.vocabulary import Kind, Status  # noqa: E402

RECENT_DAYS = 14

HELP = mctx("""
    - Usage: `uv run python scripts/area.py <path> [<path> ...]`
    - `<path>` is the path of a file or a directory from the root of the tree.
    - The command reads the ticket tracker of the main tree and prints two lists, each under its heading, in the order of numbers, with `{none}` under a heading whose list is empty.
    - Open changes: each `{change}` outside `tickets/{closed}/` whose `## Scope` gives a path that is a `<path>`, or stands under one, or that a `<path>` stands under, with its number, its status and its title.
        - The paths a Scope gives are those `uv run python scripts/file_ticket.py --help-all` gives.
    - Recent tickets: each ticket filed or closed in the last {days} days whose text names a `<path>`, as `uv run python scripts/file_ticket.py closed-on --help` gives, with its number, its kind, its status and its title.
    - The command refuses an absolute `<path>`.
    """)

CHANGES = mctx("Open changes whose Scope gives a path:")
RECENT = mctx("Tickets filed or closed in the last {days} days whose text names a path:")
CHANGE_ROW = mctx("{number} {status} {title}")
RECENT_ROW = mctx("{number} {kind} {status} {title}")
NONE = mctx("none")


def overlaps(a: str, b: str) -> bool:
    """Whether the path `a` is `b`, or one of them stands under the other."""
    return Path(a).is_relative_to(b) or Path(b).is_relative_to(a)


def open_changes(tickets: dict[str, Ticket], paths: list[str], root: Path) -> list[Ticket]:
    return [t for t in tickets.values()
            if t.kind is Kind.CHANGE and t.status is not Status.CLOSED
            and any(overlaps(s, p) for s in scope_paths(t, root) for p in paths)]


def recent(tickets: dict[str, Ticket], paths: list[str], since: float) -> list[Ticket]:
    forms = [(p, word_forms(p)) for p in paths]
    return [t for t in tickets.values()
            if (t.filed >= since or any(line.status is Status.CLOSED and line.time >= since
                                        for line in t.log))
            and (text := ticket_text(t)) is not None and any(refers(text, p, f) for p, f in forms)]


def area(paths: list[str]) -> str:
    if bad := [p for p in paths if Path(p).is_absolute()]:
        raise Refused(mctx("{paths} are absolute: give each path from the root of the tree, as "
                           "`uv run python scripts/area.py --help` gives").format(paths=", ".join(bad)))
    root = main_tree()
    tickets, _ = read_tickets(root / "tickets")
    ordered = dict(sorted(tickets.items(), key=lambda kv: kv[1].order))
    changes = [CHANGE_ROW.format(number=t.number, status=t.status, title=t.title)
               for t in open_changes(ordered, paths, root)]
    since = time.time() - RECENT_DAYS * 86400
    others = [RECENT_ROW.format(number=t.number, kind=t.kind, status=t.status, title=t.title)
              for t in recent(ordered, paths, since)]
    return "\n".join([CHANGES, *(changes or [NONE]), "",
                      RECENT.format(days=RECENT_DAYS), *(others or [NONE])])


def main() -> int:
    parser = argparse.ArgumentParser(
        description=textwrap.dedent(HELP).format(none=NONE, change=Kind.CHANGE, closed=Status.CLOSED,
                                                 days=RECENT_DAYS),
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("paths", nargs="+", metavar="path")
    args = parser.parse_args()
    try:
        print(area(args.paths))
    except Refused as e:
        print_refused(e)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
