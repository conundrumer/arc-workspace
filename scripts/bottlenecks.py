"""Print what held ready work up, by cause: per file that `change`
tickets' Scopes name, the waits on `depends-on` links and the conflicts in
a change's rebase; per ticket, the waits on the user and the hours a
change stood untaken and ready; per change, the waits of other changes on it;
and beside each file, its churn. `HELP`, which `--help` prints, gives the
usage form and the counting rules."""

import argparse
import sys
import textwrap
import time
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from controlled_markdown import mctx
from engine import checkout
from handbook.paths import scripts_importable

scripts_importable()

from file_ticket import print_undecided  # noqa: E402
from ticket_paths import scope_paths  # noqa: E402
from ticket_reads import read_tickets  # noqa: E402
from spends import union_seconds  # noqa: E402
from tree_reads import main_tree  # noqa: E402

from operations.merging import CONFLICT_OPENING, RERUN_OPENING, conflict_note_paths  # noqa: E402
from operations.state import LogLine, Ticket  # noqa: E402
from operations.tracker import runs  # noqa: E402
from operations.worktrees import BASE  # noqa: E402
from ticketing.times import TIME_FORM, stamp_time, utc_stamp  # noqa: E402
from ticketing.vocabulary import UNTAKEN, WAIT_STATUSES, Kind, Status  # noqa: E402
from ticket_vocabulary import ticked  # noqa: E402

NO_SHARED_FILE = "(no shared file)"
PATHS_NOT_RECORDED = "(paths not recorded)"

HELP = mctx("""
    - Usage: `uv run python scripts/bottlenecks.py [--since <time>]`
    - The command reads the ticket tracker of the main tree and prints, for each cause below, a heading with the cause's sum and then its rows, the largest first.
    - `--since <time>`, with `<time>` in the form `{form}` in UTC, sets the window from that time to now: each span is cut to the window, and only the conflict lines in it count. With no `--since`, the window is the whole log.
    - `depends-on` waits: one row per path that a `change` ticket's `## Scope` gives, with the wall-clock hours in which a change waited on it and the number of changes that waited on it.
        - The paths a Scope gives are those `uv run python scripts/file_ticket.py --help-all` gives.
        - A `depends-on` wait is a span in which a `change` ticket stood in one of {queue} and a ticket its `depends-on` gives stood outside `tickets/closed/`, charged to each path both Scopes give, or to the row `{no_shared}` where they give none in common.
        - The wait hours of a path are its wall-clock hours: the hours in which at least one change waited on the path, each hour counted once however many changes waited in it.
    - Rebase conflicts: each log line of a `change` ticket whose note opens with `{opening}` or `{rerun}`, charged to each path it gives, or to the row `{not_recorded}` where it gives none.
    - A status wait is a span of a ticket's log. It opens at a line that moves the ticket into `blocked` or `waiting`, or at a line whose note opens with what the ticket waits on while it stands there. It takes as its cause what that line's note opens with, as `uv run python scripts/file_ticket.py log --help` gives it: `user` or `change <number>`. It runs to the next line of the ticket's log that moves the ticket out of that status or whose note opens with what the ticket waits on.
    - Waits on the user: one row per ticket of any kind, with the hours of its status waits whose cause is `user`.
    - Waits on another change: one row per change number, with the hours of the status waits of `change` tickets whose cause is `change <number>`.
    - Ready and not taken: one row per `change` ticket, with the hours it stood in one of {queue} while each ticket its `depends-on` gives stood under `tickets/closed/`.
    - Churn: with `--since`, each path row gives the number of commits of `master` that touch the path, or a file under it, in the window of the same length that ends at the window's start.
    """)

HEADING = mctx("{cause}: {total}")
DEPENDS_ON = mctx("depends-on waits")
CONFLICTS = mctx("rebase conflicts")
ON_USER = mctx("waits on the user")
ON_CHANGE = mctx("waits on another change")
READY = mctx("ready and not taken")
WAIT_ROW = mctx("{hours} h  {waiting} waiting  {churn}  {path}")
CONFLICT_ROW = mctx("{conflicts} conflicts  {churn}  {path}")
TICKET_ROW = mctx("{hours} h  {number}")
NO_TICKET = mctx("{number} {link} {d}, and no ticket the read finds has that number")
CHURN = mctx("churn {commits}")
WAITS_ON_CHANGE = mctx("waits on change")
DEPENDS_ON_LINK = mctx("depends on")
NO_WAIT = mctx("{number} moves into `{status}` at {time} with a note that opens with no wait")
NEITHER = mctx("{number} waits at {time} on neither the user nor a change")


type Span = tuple[float, float]


def spans_in(t: Ticket, keep: frozenset[Status], now: float) -> list[Span]:
    """The spans in which `t` stood in a status of `keep`, each line's
    status holding from its time to the next line's, and the last one's
    to `now`."""
    ends = [line.time for line in t.log[1:]] + [now]
    return [(line.time, end) for line, end in zip(t.log, ends) if line.status in keep]


def overlap(a: list[Span], b: list[Span]) -> list[Span]:
    return [(max(s, u), min(e, v)) for s, e in a for u, v in b if max(s, u) < min(e, v)]


def clip(spans: list[Span], start: float) -> list[Span]:
    """The parts of `spans` from `start` on."""
    return [(max(s, start), e) for s, e in spans if e > start]


def wait_spans(t: Ticket, now: float) -> list[tuple[Span, LogLine, Status]]:
    """The spans in which `t` stood under `blocked` or `waiting`, each with
    the line that opens it and that status: the first line of each run of
    lines in that status (`runs`), and each line of the run after it whose
    note opens with a wait. A span runs to the next of those lines, or,
    after the last, to the time of the line after the run, or to `now`
    where the run ends the log."""
    out: list[tuple[Span, LogLine, Status]] = []
    for run in runs(t):
        if run.status not in WAIT_STATUSES:
            continue
        opens = [run.start] + [i for i in run.waits if i > run.start]
        end = t.log[run.end].time if run.end < len(t.log) else now
        ends = [t.log[i].time for i in opens[1:]] + [end]
        out += [((t.log[i].time, e), t.log[i], run.status) for i, e in zip(opens, ends)]
    return out


@dataclass(frozen=True)
class Costs:
    """What held ready work up in a window, by cause: per file, the
    `depends-on` wait hours and the waiting changes, and the rebase
    conflicts; per
    ticket, the hours it waited on the user and the hours it stood untaken and
    ready; per change number, the hours other changes waited on it."""
    depends_on: dict[str, tuple[float, int]]
    conflicts: dict[str, int]
    on_user: dict[str, float]
    on_change: dict[str, float]
    ready: dict[str, float]


def hours(spans: list[Span]) -> float:
    return union_seconds(spans) / 3600


type Window = tuple[float, float]
"""The window from its start to `now`."""


def by_number(spans: dict[str, list[Span]]) -> dict[str, float]:
    return {n: hours(s) for n, s in sorted(spans.items()) if s}


def wait_hours(tickets: dict[str, Ticket], window: Window,
               undecided: list[str]) -> tuple[dict[str, float], dict[str, float]]:
    """The hours each ticket waited on the user, and the hours `change`
    tickets waited on each change number, in `window`."""
    start, now = window
    on_user: dict[str, list[Span]] = defaultdict(list)
    on_change: dict[str, list[Span]] = defaultdict(list)
    for n, t in sorted(tickets.items()):
        for span, line, status in wait_spans(t, now):
            spans = clip([span], start)
            if not spans:
                continue
            if not line.waits:
                undecided.append(NO_WAIT.format(number=n, status=status, time=utc_stamp(line.time)))
            elif line.on_user:
                on_user[n] += spans
            elif line.on_change is None:
                undecided.append(NEITHER.format(number=n, time=utc_stamp(line.time)))
            elif t.kind is Kind.CHANGE:
                if line.on_change not in tickets:
                    undecided.append(NO_TICKET.format(number=n, link=WAITS_ON_CHANGE,
                                                      d=line.on_change))
                else:
                    on_change[line.on_change] += spans
    return by_number(on_user), by_number(on_change)


def changes(tickets: dict[str, Ticket]) -> list[tuple[str, Ticket]]:
    return [(n, t) for n, t in sorted(tickets.items()) if t.kind is Kind.CHANGE]


def conflict_counts(tickets: dict[str, Ticket], start: float) -> dict[str, int]:
    """The number of rebase conflicts of each path from `start` on."""
    conflicts: dict[str, int] = defaultdict(int)
    for _, t in changes(tickets):
        for line in t.log:
            paths = conflict_note_paths(line.note)
            if paths is not None and line.time >= start:
                for p in paths or (PATHS_NOT_RECORDED,):
                    conflicts[p] += 1
    return dict(sorted(conflicts.items()))


def dependency_waits(tickets: dict[str, Ticket], root: Path, window: Window,
                     undecided: list[str]
                     ) -> tuple[dict[str, tuple[float, int]], dict[str, float]]:
    """Per file, the wall-clock `depends-on` wait hours and the waiting changes, and
    per change, the hours it stood untaken and ready, in `window`."""
    start, now = window
    scopes = {n: scope_paths(t, root) for n, t in sorted(tickets.items())}
    waits: dict[str, dict[str, list[Span]]] = defaultdict(lambda: defaultdict(list))
    ready: dict[str, float] = {}
    not_closed = frozenset(Status) - {Status.CLOSED}
    for n, t in changes(tickets):
        waiting = clip(spans_in(t, frozenset(UNTAKEN), now), start)
        free = waiting
        for d in t.depends_on:
            if d not in tickets:
                undecided.append(NO_TICKET.format(number=n, link=DEPENDS_ON_LINK, d=d))
                free = []
                continue
            spans = overlap(waiting, spans_in(tickets[d], not_closed, now))
            free = overlap(free, spans_in(tickets[d], frozenset({Status.CLOSED}), now))
            if not spans:
                continue
            for p in sorted(scopes[n] & scopes[d]) or [NO_SHARED_FILE]:
                waits[p][n] += spans
        if free:
            ready[n] = hours(free)
    return ({p: (hours([sp for s in waits[p].values() for sp in s]),
                 sum(1 for s in waits[p].values() if s)) for p in sorted(waits)},
            ready)


def bottlenecks(tickets: dict[str, Ticket], root: Path, start: float, now: float,
                undecided: list[str]) -> Costs:
    """The costs of each cause over the window from `start` to `now`."""
    on_user, on_change = wait_hours(tickets, (start, now), undecided)
    conflicts = conflict_counts(tickets, start)
    depends_on, ready = dependency_waits(tickets, root, (start, now), undecided)
    return Costs(depends_on=depends_on, conflicts=conflicts, on_user=on_user,
                 on_change=on_change, ready=ready)


def churn(root: Path, start: float, now: float) -> list[frozenset[str]]:
    """The files each commit of `master` touches in the window of the same
    length as the one from `start` to `now` that ends at `start`."""
    out = checkout.git_out(root, "log", BASE, f"--since=@{int(2 * start - now)}",
                           f"--until=@{int(start)}", "--format=%x00", "--name-only")
    return [frozenset(chunk.split()) for chunk in out.split("\0")[1:]]


def touching(commits: list[frozenset[str]], path: str) -> int:
    """The number of `commits` that touch `path` or a file under it."""
    under = path.rstrip("/") + "/"
    return sum(1 for files in commits if any(f == path or f.startswith(under) for f in files))


def main() -> int:
    help_text = textwrap.dedent(HELP).format(
        no_shared=NO_SHARED_FILE, opening=CONFLICT_OPENING, rerun=RERUN_OPENING,
        not_recorded=PATHS_NOT_RECORDED, form=TIME_FORM, queue=ticked(UNTAKEN))
    ap = argparse.ArgumentParser(description=help_text,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--since", type=stamp_time)
    args = ap.parse_args()
    root = main_tree()
    now = time.time()
    since: float | None = args.since
    tickets, unread = read_tickets(root / "tickets")
    undecided = [mctx("{path}: {why}").format(path=u.path, why=u.why) for u in unread]
    costs = bottlenecks(tickets, root, 0.0 if since is None else since, now, undecided)
    touched = None if since is None else churn(root, since, now)

    def churn_of(path: str) -> str:
        if touched is None:
            return ""
        if path in (NO_SHARED_FILE, PATHS_NOT_RECORDED):
            return CHURN.format(commits="  -")
        return CHURN.format(commits=f"{touching(touched, path):3}")

    rows = sorted(costs.depends_on.items(), key=lambda r: (-r[1][0], r[0]))
    print(HEADING.format(cause=DEPENDS_ON, total=f"{sum(h for _, (h, _) in rows):.1f} h"))
    for path, (h, waiting) in rows:
        print(WAIT_ROW.format(hours=f"{h:8.1f}", waiting=f"{waiting:3}", churn=churn_of(path),
                              path=path))
    print(HEADING.format(cause=CONFLICTS, total=sum(costs.conflicts.values())))
    for path, n in sorted(costs.conflicts.items(), key=lambda r: (-r[1], r[0])):
        print(CONFLICT_ROW.format(conflicts=f"{n:3}", churn=churn_of(path), path=path))
    for cause, per in ((ON_USER, costs.on_user), (ON_CHANGE, costs.on_change),
                       (READY, costs.ready)):
        print(HEADING.format(cause=cause, total=f"{sum(per.values()):.1f} h"))
        for n, h in sorted(per.items(), key=lambda r: (-r[1], r[0])):
            print(TICKET_ROW.format(hours=f"{h:8.1f}", number=n))
    print_undecided(undecided)
    return 0


if __name__ == "__main__":
    sys.exit(main())
