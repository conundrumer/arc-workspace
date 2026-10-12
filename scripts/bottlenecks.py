"""Print, for each file that `change` tickets' Scopes name, what contention
on it has cost: the waits on `depends-on` links and the reruns after a
conflict in a rebase. `HELP`, which `--help` prints, gives the usage form
and the counting rules."""

import argparse
import re
import sys
import textwrap
import time
from collections import defaultdict
from pathlib import Path

from controlled_markdown import mctx
from engine import checkout
from handbook.paths import importable

# `scripts/` is no package: the modules below import from there.
importable(checkout.scripts())

from file_ticket import print_undecided  # noqa: E402
from ticket_form import section, section_head  # noqa: E402
from ticket_reads import read_tickets  # noqa: E402
from tree_reads import main_tree  # noqa: E402

from operations.merging import RERUN_OPENING, rerun_paths  # noqa: E402
from operations.state import Ticket  # noqa: E402
from ticketing.vocabulary import Kind, Status  # noqa: E402

NO_SHARED_FILE = "(no shared file)"
PATHS_NOT_RECORDED = "(paths not recorded)"

RERUN_COST = 2.20
"""The dollars of one build of a change, the estimate the log of ticket
6-702 gives for a rerun."""

HELP = mctx("""
    - Usage: `uv run python scripts/bottlenecks.py`
    - The command reads the ticket tracker of the main tree and prints one row per file, with the hours changes waited on it, the number of changes that waited on it, the number of reruns charged to it and their cost in dollars. The rows are sorted by wait hours plus rerun count, the largest first.
    - A file is a path a `change` ticket's `## Scope` gives that contains a `/` or names a file or a directory at the root of the main tree. A path with a `/` that is not the whole path of its file, and the old and the new path of a renamed file, count toward separate rows.
    - Waits: for each `change` ticket and each number its `depends-on` gives, the spans in which the waiting ticket stood under `tickets/open/` and the ticket it depends on stood outside `tickets/closed/`, by the status of each log line, up to now. The spans are charged to each file both tickets' Scopes give, and for each file and each waiting change, overlapping spans count once. A link whose two Scopes name no common file is charged to the row `{no_shared}`.
        - The wait hours of a file are change-hours: the waits of different changes that overlap in time add up.
    - Reruns: each log line of a `change` ticket whose note opens with `{opening}`, charged to each path it gives. A line that gives no path is charged to the row `{not_recorded}`. Each rerun costs ${cost}, an estimate of the cost of one build of a change.
    - Each number a `depends-on` gives that is the number of no ticket the read finds, and each ticket file the read fails on, is printed to stderr on a line that opens with `undecided:`.
    """)

ROW = mctx("{hours} h  {waiting} waiting  {reruns} reruns  ${cost}  {path}")


def scope_paths(t: Ticket, root: Path) -> frozenset[str]:
    """The paths the `Scope` of `t` names, in backticks or as link targets:
    each that holds a `/` or stands at the root of the tree `root`. A
    ticket with no `Scope` names none."""
    text = t.path.read_text()
    if section_head(text, "Scope") is None:
        return frozenset()
    body = section(text, "Scope")
    words = re.findall(r"`([^`\s]+)`", body) + re.findall(r"\]\(([^)\s]+)\)", body)
    paths = {w.split("#", 1)[0].rstrip(":") for w in words}
    return frozenset(p for p in paths if p and ("/" in p or (root / p).exists()))


type Span = tuple[float, float]


def spans_in(t: Ticket, keep: frozenset[Status], now: float) -> list[Span]:
    """The spans in which `t` stood in a status of `keep`, each line's
    status holding from its time to the next line's, and the last one's
    to `now`."""
    ends = [line.time for line in t.log[1:]] + [now]
    return [(line.time, end) for line, end in zip(t.log, ends) if line.status in keep]


def overlap(a: list[Span], b: list[Span]) -> list[Span]:
    return [(max(s, u), min(e, v)) for s, e in a for u, v in b if max(s, u) < min(e, v)]


def union_hours(spans: list[Span]) -> float:
    """The hours the spans cover, counting an overlap once."""
    total, reach = 0.0, -float("inf")
    for s, e in sorted(spans):
        if e > reach:
            total += e - max(s, reach)
            reach = e
    return total / 3600


def bottlenecks(tickets: dict[str, Ticket], root: Path, now: float,
                undecided: list[str]) -> list[tuple[str, float, int, int]]:
    """For each file, its wait hours, its waiting changes and its reruns,
    sorted by wait hours plus reruns, the largest first, then by path."""
    scopes = {n: scope_paths(t, root) for n, t in sorted(tickets.items())}
    waits: dict[str, dict[str, list[Span]]] = defaultdict(lambda: defaultdict(list))
    reruns: dict[str, int] = defaultdict(int)
    not_closed = frozenset(Status) - {Status.CLOSED}
    for n, t in sorted(tickets.items()):
        if t.kind is not Kind.CHANGE:
            continue
        for line in t.log:
            paths = rerun_paths(line.note)
            if paths is not None:
                for p in paths or (PATHS_NOT_RECORDED,):
                    reruns[p] += 1
        waiting = spans_in(t, frozenset({Status.OPEN}), now)
        for d in t.depends_on:
            if d not in tickets:
                undecided.append(mctx("{number} depends on {d}, and no ticket the read finds "
                                      "has that number").format(number=n, d=d))
                continue
            spans = overlap(waiting, spans_in(tickets[d], not_closed, now))
            for p in sorted(scopes[n] & scopes[d]) or [NO_SHARED_FILE]:
                waits[p][n] += spans
    rows = [(p, sum(union_hours(spans) for spans in waits[p].values()),
             sum(1 for spans in waits[p].values() if spans), reruns[p])
            for p in sorted(set(waits) | set(reruns))]
    return sorted(rows, key=lambda r: (-(r[1] + r[3]), r[0]))


def main() -> int:
    help_text = textwrap.dedent(HELP).format(
        no_shared=NO_SHARED_FILE, opening=RERUN_OPENING, not_recorded=PATHS_NOT_RECORDED,
        cost=f"{RERUN_COST:.2f}")
    argparse.ArgumentParser(description=help_text,
                            formatter_class=argparse.RawDescriptionHelpFormatter).parse_args()
    root = main_tree()
    tickets, unread = read_tickets(root / "tickets")
    undecided = [mctx("{path}: {why}").format(path=u.path, why=u.why) for u in unread]
    for path, hours, waiting, count in bottlenecks(tickets, root, time.time(), undecided):
        print(ROW.format(hours=f"{hours:8.1f}", waiting=f"{waiting:3}", reruns=f"{count:3}",
                         cost=f"{count * RERUN_COST:7.2f}", path=path))
    print_undecided(undecided)
    return 0


if __name__ == "__main__":
    sys.exit(main())
