"""Judge the recent calls of each frequently used script against its own
usual calls, from the record `script_calls` keeps, and file a
`performance` ticket on each script whose calls grew. `HELP`, which
`--help` prints, gives the test."""

import argparse
import statistics
import sys
import time
from collections import defaultdict
from pathlib import Path

from controlled_markdown import mctx
from engine import checkout
from handbook.paths import scripts_importable
import script_calls
from script_calls import Call
from operations.log_commands import AGENT
from ticketing.text import ticket_text
from ticketing.times import TIME_FORM, stamp_time, utc_stamp
from ticketing.vocabulary import DEFECT_SECTIONS, Domain, Kind, Status

scripts_importable()

from file_ticket import file_ticket, main_tickets  # noqa: E402
from ticket_files import ticket_files  # noqa: E402
from ticket_form import title  # noqa: E402

DAY = 24 * 3600
FREQUENT = 20
CPU_RATIO = 2
CPU_MARGIN = 1.0
MB = 1024 * 1024
PEAK_RATIO = 2
PEAK_MARGIN = 256 * MB
SHOWN = 3
"""The number of the slowest recent calls a ticket's evidence gives."""

HELP = mctx("""
    - The usage form:
        ```
        uv run python scripts/check_script_calls.py --since <time>
        ```
    - `<time>` is a UTC time, as `2026-10-15T21:49:39Z`.
    - The record holds a line for each call of a script under `scripts/` of the main tree, with the call's key: the script's file name, and its first argument where that is a bare word, as in `operate.py next`.
    - A key with at least {frequent} calls in the {days} days before `<time>` is judged, by its calls since `<time>` against those earlier calls.
    - The command files a `performance` ticket on a judged key where the median CPU seconds of its recent calls exceeds {cpu_ratio} times the 25th percentile of its earlier calls by at least {cpu_margin:.0f} s, or the largest peak memory of its recent calls exceeds {peak_ratio} times the median peak memory of its earlier calls by at least {peak_margin} MB.
        - It files none on a key where a ticket outside `tickets/closed/` has the same text before the first `: ` of its title as the ticket it would file.
    - It deletes the record of each day more than {days} days old, and prints the path of each ticket it filed, or `no ticket filed`.
    """).format(frequent=FREQUENT, days=script_calls.WINDOW_SECONDS // DAY, cpu_ratio=CPU_RATIO, cpu_margin=CPU_MARGIN,
            peak_ratio=PEAK_RATIO, peak_margin=PEAK_MARGIN // MB)

NONE_FILED = mctx("no ticket filed")


def subject_of(key: str) -> str:
    """The text a ticket's title gives before its first `: `."""
    return f"scripts/{key}"


def figures(calls: list[Call]) -> str:
    return mctx("{n} calls, median CPU {cpu:.2f} s, median wall {wall:.2f} s, "
                "median peak {peak} MB, largest peak {top} MB").format(
                    n=len(calls), cpu=statistics.median(c.cpu for c in calls),
                    wall=statistics.median(c.wall for c in calls),
                    peak=round(statistics.median(c.peak for c in calls) / MB),
                    top=max(c.peak for c in calls) // MB)


def judged(key: str, recent: list[Call], earlier: list[Call]) -> str | None:
    """The text of the ticket on `key`, where its recent calls grew."""
    usual_cpu = statistics.quantiles([c.cpu for c in earlier], n=4, method="inclusive")[0]
    cpu = statistics.median(c.cpu for c in recent)
    usual_peak = statistics.median(c.peak for c in earlier)
    peak = max(c.peak for c in recent)
    if cpu >= CPU_RATIO * usual_cpu + CPU_MARGIN:
        ratio = cpu / usual_cpu if usual_cpu else float("inf")
        name = mctx("{subject}: its calls take {n:.1f} times their usual CPU time").format(
            subject=subject_of(key), n=ratio)
        impact_text = mctx("Each call of `scripts/{key}` takes more of the machine than its usual calls "
                           "took, which the work of every session on the machine goes without.").format(key=key)
        slowest = sorted(recent, key=lambda c: (-c.cpu, c.start))[:SHOWN]
    elif peak >= PEAK_RATIO * usual_peak + PEAK_MARGIN:
        ratio = peak / usual_peak if usual_peak else float("inf")
        name = mctx("{subject}: a recent call took {n:.1f} times the median peak memory "
                    "of its earlier calls").format(subject=subject_of(key), n=ratio)
        impact_text = mctx("A recent call of `scripts/{key}` took more memory than its usual calls "
                           "took, which the work of every session on the machine went without at that "
                           "time.").format(key=key)
        slowest = sorted(recent, key=lambda c: (-c.peak, c.start))[:SHOWN]
    else:
        return None
    impact, evidence = DEFECT_SECTIONS
    return ticket_text(Kind.PERFORMANCE, name, {
        impact: impact_text,
        evidence: "\n".join([
            mctx("- Recent calls: {figures}.").format(figures=figures(recent)),
            mctx("- Earlier calls: {figures}, 25th percentile CPU {p25:.2f} s.").format(
                figures=figures(earlier), p25=usual_cpu),
            *(mctx("- Call at {start} of session {session}: CPU {cpu:.2f} s, wall {wall:.2f} s, "
                   "peak {peak} MB.").format(start=utc_stamp(c.start), session=c.session or "none",
                                             cpu=c.cpu, wall=c.wall, peak=c.peak // MB)
              for c in slowest)])})


def open_subjects(tickets: Path) -> set[str]:
    """The text before the first `: ` of the title of each ticket outside
    `tickets/closed/`."""
    return {title(p, p.read_text()).split(": ", 1)[0]
            for s in Status if s is not Status.CLOSED for p in ticket_files(tickets, s)}


def check(since: float, records: Path, tickets: Path) -> list[Path]:
    calls = script_calls.read(str(records), since - script_calls.WINDOW_SECONDS)
    recent: dict[str, list[Call]] = defaultdict(list)
    earlier: dict[str, list[Call]] = defaultdict(list)
    for c in calls:
        (recent if c.start >= since else earlier)[c.key].append(c)
    filed: list[Path] = []
    master = checkout.git_out(checkout.ROOT, "rev-parse", "master").strip()
    for key in sorted(recent):
        if len(earlier[key]) < FREQUENT or subject_of(key) in open_subjects(tickets):
            continue
        if (text := judged(key, recent[key], earlier[key])) is not None:
            filed.append(file_ticket(tickets, Domain.COMMIT.value, master, AGENT, text))
    script_calls.prune(str(records), time.time() - script_calls.WINDOW_SECONDS)
    return filed


def records_dir() -> Path:
    return checkout.main_worktree(checkout.ROOT) / script_calls.RECORDS


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=HELP, usage=argparse.SUPPRESS,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--since", required=True)
    args = parser.parse_args(argv)
    try:
        since = stamp_time(args.since)
    except ValueError:
        parser.error(mctx("`{text}` is no time of the form {form}").format(text=args.since, form=TIME_FORM))
    filed = check(since, records_dir(), main_tickets())
    print("\n".join(map(str, filed)) if filed else NONE_FILED)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
