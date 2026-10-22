"""Ticket lifetime reports derived from logs and recorded run evidence."""

import argparse
import time
from collections import defaultdict
from pathlib import Path

from handbook.paths import scripts_importable

scripts_importable()

from agent_launches import children_of, run_transcript
from agent_turns import turns
from bottlenecks import Span, overlap, spans_in, wait_spans
from codex_transcript import Transcript, read
from controlled_markdown import mctx
from operations.change_budget import TIME_OPENING
from operations.codex_spend import CodexSpend
from operations.state import Ticket
from operations.tracker import runs as status_runs
from run_reads import agent_type, run_entries
from spends import closed_tree, measured_through_root, native_agents, ticket_runs, union_seconds
from ticket_cases import print_undecided
from ticket_files import ticket_path
from ticket_numbers import ticket_number
from ticket_reads import held_ticket
from ticketing.times import utc_stamp
from ticketing.vocabulary import Kind, Resolution, Status
from transcript_entries import epoch
from transcript_snapshots import SUBJECT_FAULTS
from transcripts import agent_id, held_find
from tree_reads import main_tree

HELP = mctx("""
    - Usage: `uv run python scripts/lifetimes.py <number> ...`.
    - The command reads the main tracker and reports each ticket's life from its first log line to its latest close, or to now when open, with UTC bounds, seconds and percentages of its full life.
    - Status rows partition the life; wait rows divide blocked and waiting time by their recorded cause.
        + xref: scripts/bottlenecks.py:spans_in, scripts/bottlenecks.py:wait_spans
    - Assigned time is partitioned into merge, known worker time, launcher overhead or wait, and remaining time. Worker time by role may overlap; the worker total counts each interval once.
        + xref: scripts/lifetimes.py:report
    - Launcher overhead or wait includes the launcher's own work and its waits outside known worker time and merge.
        + xref: scripts/lifetimes.py:report
    - Where timing or role evidence is missing, the report keeps known intervals and marks unproved time unresolved. With complete evidence, remaining time has no recorded run at work. Missing token usage alone does not invalidate timing.
        + xref: scripts/lifetimes.py:evidence, scripts/lifetimes.py:report
    """)


UNKNOWN_ROLE = mctx("unknown role")


def subtract(spans: list[Span], removed: list[Span]) -> list[Span]:
    """The parts of the spans outside all removed intervals."""
    out = spans
    for a, b in removed:
        out = [part for s, e in out for part in
               ([(s, e)] if b <= s or a >= e else
                [(s, min(a, e)), (max(b, s), e)]) if part[0] < part[1]]
    return out


def evidence(roots: list[str], undecided: list[str]
             ) -> tuple[dict[str, list[Span]], list[Span]]:
    paths: set[Path] = set()
    native_measured = None

    def missing(run: str) -> bool:
        nonlocal native_measured
        if native_measured is None:
            native_measured = native_agents(roots)
        return not measured_through_root(native_measured, roots, run)

    for root in roots:
        try:
            top = held_find(root)
        except SUBJECT_FAULTS as exc:
            undecided.append(mctx("{run}: transcript unreadable: {error}").format(run=root, error=exc))
            continue
        if top is None:
            if missing(root):
                undecided.append(mctx("{run}: transcript missing").format(run=root))
            continue
        paths.add(top)
        try:
            paths.update(closed_tree(top))
        except SUBJECT_FAULTS as exc:
            undecided.append(mctx("{run}: descendant evidence unreadable: {error}").format(run=root, error=exc))
    workers: dict[str, list[Span]] = defaultdict(list)
    launchers: list[Span] = []
    seen: set[tuple[str | None, str]] = set()
    for path in sorted(paths):
        try:
            for child in sorted(children_of(path, agent_id(path))):
                if run_transcript(child, False) is None and missing(child):
                    undecided.append(mctx("{run}: child transcript missing").format(run=child))
        except SUBJECT_FAULTS as exc:
            undecided.append(mctx("{run}: child evidence unreadable: {error}").format(run=path, error=exc))
        try:
            own_type = agent_type(path)
        except SUBJECT_FAULTS as exc:
            undecided.append(mctx("{run}: worker role unreadable: {error}").format(run=path, error=exc))
            own_type = None
        try:
            codex = read(path)
        except SUBJECT_FAULTS as exc:
            undecided.append(mctx("{run}: accepted turn evidence unreadable: {error}").format(
                run=path, error=exc))
            codex = Transcript(CodexSpend(()), gaps=[str(exc)])
        accepted = {(source.thread, source.turn) for source, _, _ in codex.turns}
        for source in codex.spend.sources:
            if source.thread is None or source.turn is None or (source.thread, source.turn) not in accepted:
                undecided.append(mctx("{run}: accepted turn evidence missing or ambiguous").format(run=path))
        for source, _, turn in codex.turns:
            key = source.thread, turn.turn
            if key in seen:
                continue
            seen.add(key)
            role = source.role
            if not role or role == "unknown":
                undecided.append(mctx("{run}: worker role unknown").format(run=path))
                role = UNKNOWN_ROLE
            if turn.ended is None:
                undecided.append(mctx("{run}: accepted turn has no end").format(run=path))
            else:
                workers[role].append((turn.started, turn.ended))
        try:
            entries = list(run_entries(path))
        except SUBJECT_FAULTS as exc:
            undecided.append(mctx("{run}: turn evidence unreadable: {error}").format(run=path, error=exc))
            continue
        starts, ends = turns(entries)
        opened: float | None = None
        envelopes: list[Span] = []
        for i, entry in enumerate(entries):
            if not entry.get("timestamp"):
                if i in starts or i in ends:
                    undecided.append(mctx("{run}: turn boundary has no timestamp").format(run=path))
                continue
            at = epoch(entry["timestamp"])
            if i in starts and opened is None:
                opened = at
            if i in ends and opened is not None:
                envelopes.append((opened, at))
                opened = None
        if not starts:
            undecided.append(mctx("{run}: no recorded turn boundaries").format(run=path))
        if opened is not None:
            undecided.append(mctx("{run}: turn has no end").format(run=path))
            dated = [epoch(e["timestamp"]) for e in entries if e.get("timestamp")]
            if dated:
                envelopes.append((opened, dated[-1]))
        if codex.spend.sources or codex.gaps or own_type == "codex-launcher":
            launchers.extend(envelopes)
        elif own_type is None:
            undecided.append(mctx("{run}: worker role unknown").format(run=path))
            workers[UNKNOWN_ROLE].extend(envelopes)
        else:
            workers[own_type].extend(envelopes)
    return dict(workers), launchers


def report(t: Ticket, now: float, undecided: list[str]) -> None:
    if not t.log:
        undecided.append(mctx("{number}: no log").format(number=t.number))
        return
    closing = [t.log[r.start] for r in status_runs(t) if r.status is Status.CLOSED]
    close = closing[-1] if closing else None
    end = close.time if t.status is Status.CLOSED and close is not None else now
    life = end - t.log[0].time
    print(mctx("{number}: life {seconds:.3f} s").format(number=t.number, seconds=life))

    def row(label: str, spans: list[Span]) -> None:
        seconds = union_seconds(spans)
        print(mctx("  {label}: {seconds:.3f} s ({share:.2f}%)").format(
            label=label, seconds=seconds, share=100 * seconds / life if life else 0))
        for a, b in sorted(spans):
            print(mctx("    {start} {end}").format(start=utc_stamp(a), end=utc_stamp(b)))

    for status in Status:
        spans = [(a, min(b, end)) for a, b in spans_in(t, frozenset({status}), end)
                 if a <= end and a <= b]
        if spans:
            row(status.value, spans)
    for span, line, status in wait_spans(t, end):
        cause = mctx("user") if line.on_user else (
            mctx("change {change}").format(change=line.on_change)
            if line.on_change is not None else mctx("unresolved wait"))
        row(mctx("{status}: {cause}").format(status=status.value, cause=cause), [span])
        if not line.waits:
            undecided.append(mctx("{number}: wait cause unknown at {time}").format(
                number=t.number, time=utc_stamp(span[0])))
    for line in t.log:
        if line.note.startswith(("taking:", TIME_OPENING)):
            print(mctx("  {time}: {note}").format(time=utc_stamp(line.time), note=line.note))
    assigned = spans_in(t, frozenset({Status.ASSIGNED}), end)
    if not assigned:
        return
    fixed = (t.kind is Kind.CHANGE and t.status is Status.CLOSED and close is not None
             and close.resolution is Resolution.FIXED)
    take_lines = [t.log[r.start] for r in status_runs(t) if r.status is Status.ASSIGNED]
    roots = ticket_runs(t) if fixed else list(dict.fromkeys(
        line.agent_id for line in take_lines
        if line.agent != "operator" and line.agent_id is not None))
    before = len(undecided)
    workers, launchers = evidence(roots, undecided)
    if not roots:
        undecided.append(mctx("{number}: assigned time has no run evidence").format(number=t.number))
    takes = [line.time for line in take_lines]
    opening = [line.time for line in t.log if line.note.startswith(TIME_OPENING)
               and (not takes or line.time >= takes[-1])]
    merge = overlap([(opening[-1], end)], assigned) if fixed and opening else []
    work = {role: subtract(overlap(spans, assigned), merge) for role, spans in workers.items()}
    union = [span for spans in work.values() for span in spans]
    launcher = subtract(overlap(launchers, assigned), [*merge, *union])
    remaining = subtract(assigned, [*merge, *union, *launcher])
    unresolved = len(undecided) > before
    row(mctx("merge"), merge)
    row(mctx("known worker union"), union)
    for role, spans in sorted(work.items()):
        row(mctx("worker {role}").format(role=role), spans)
    row(mctx("launcher overhead or wait unresolved") if unresolved
        else mctx("launcher overhead or wait"), launcher)
    row(mctx("unresolved") if unresolved else mctx("no recorded run at work"), remaining)


def main() -> None:
    parser = argparse.ArgumentParser(description=HELP,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("numbers", nargs="+")
    args = parser.parse_args()
    undecided: list[str] = []
    for number in args.numbers:
        report(held_ticket(ticket_path(main_tree() / "tickets", ticket_number(number))),
               time.time(), undecided)
    print_undecided(undecided)


if __name__ == "__main__":
    main()
