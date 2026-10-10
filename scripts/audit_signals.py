"""Prints, for each audit of facet `agent` in a session, the audit signals
(`operations.signals`) on the audited run as of that audit's launch,
beside the auditor's finding and the tickets it filed on that agent. HELP
gives the output."""

import argparse
import re
import sys
import time
from collections import Counter
from dataclasses import replace
from pathlib import Path
from typing import Any

from agent_launches import launches
from budgets import budgets_in_force
from controlled_markdown import mctx
from open_agents import node, turn_ended
from operator_reads import operator_runs, read_operator
from operator_state import audit_of, usual
from run_profile import Run
from run_reads import blocks, is_prompt, result_text, run_entries
from ticket_reads import read_tickets
from transcripts import Refused, epoch, find
from tree_reads import commits, main_tree

from operations.monitor import NO_SIGN, Audit, agent_audits, hung_from
from operations.roles import EDITORS
from operations.signals import Known, Reading, RunAt, Unknown, signals
from operations.state import Agent, Call, Message
from operations.tracker import WORKTREES
from ticketing.vocabulary import Domain, Status

HELP = """\
usage: uv run python scripts/audit_signals.py <session id>

- For each audit of facet `agent` that an operator of the session launched, in the order of
  the launches, prints a block: the agent audited and its type, the auditor and the models its
  transcript gives, each signal of `operations.signals` on the audited run as of the audit's
  launch, as `fired`, `quiet` or `undecided: <reason>`, the auditor's finding (`no sign`, its
  alert kind, or `pending` or `unread`), and each ticket of domain `agent` on the audited agent
  whose first log line the auditor wrote, with its status, and where closed, its last log note.
- Then prints, per auditor model, the number of runs and of findings on them, on runs where a
  signal fired, on runs where none fired and none was undecided, and on runs where none fired
  and one was undecided, and the number of runs where a signal fired and the auditor found no
  sign.
- The run as of a launch:
  - Its latest turn began at the latest message from its parent by then, and ended at its last
    entry by then where that entry is the model's and makes no call.
  - Its work was open at that end where a call it backgrounded began by then and had no end by
    then.
  - Its active time is that of the period of the latest message from its parent; it is unknown
    where a call of the run began after the launch inside that period.
  - A call was refused where its result is an error that opens with a form the harness or a
    hook gives to a call it refused (`REFUSALS`), and hung where it ran past `HUNG_FACTOR` times
    its label's usual time by then.
  - Its changed files are the paths its Edit, Write and NotebookEdit calls gave by then, inside
    the repo; a file a Bash command changed is not among them.
  - The paths its change's Scope gives are the backticked words of that section, each with any
    trailing `/` cut.
- `undecided` lines on stderr give what the reads left unknown."""

REFUSALS = ("Permission for this action was denied", "The user doesn't want to proceed",
            "PreToolUse:", "Blocked:", "<tool_use_error>Blocked:")
"""The openings of the result of a call the harness, the permission
classifier, the user or a hook refused."""

EDITS = frozenset({"Edit", "Write", "NotebookEdit"})
WORKTREE = re.compile(rf"/{re.escape(WORKTREES)}/[^/]+/(?P<rest>.+)\Z")
BACKTICKED = re.compile(r"`([^`\s]+)`")
INDENT = "  "
SCOPE = re.compile(r"^## Scope\n(?P<body>.*?)(?=^## |\Z)", re.MULTILINE | re.DOTALL)


SYNTHETIC = "<synthetic>"
"""The model field the harness writes on the assistant entries no model
made."""


def models(path: Path) -> list[str]:
    """The models the assistant entries of the run at `path` give, in
    their first order, other than `SYNTHETIC`."""
    found = [m for e in run_entries(path) if e.get("type") == "assistant"
             and isinstance(m := (e.get("message") or {}).get("model"), str)
             and m != SYNTHETIC]
    return list(dict.fromkeys(found))


def turn_at(entries: list[dict[str, Any]], run: Run, at: float
            ) -> Known[tuple[float, float | None]]:
    starts = [m.time for m in run.messages if m.time <= at]
    if not starts:
        return Unknown(mctx("no message from its parent reached it by the launch"))
    timed = [e for e in entries if e.get("timestamp") and epoch(e["timestamp"]) <= at
             and (e.get("type") == "assistant" or is_prompt(e) or blocks(e, "tool_result"))]
    if not timed:
        return Unknown(mctx("its transcript gives no entry by the launch"))
    last = timed[-1]
    ended = last.get("type") == "assistant" and not blocks(last, "tool_use")
    return starts[-1], epoch(last["timestamp"]) if ended else None


def open_at(run: Run, turn: Known[tuple[float, float | None]]) -> Known[bool]:
    if isinstance(turn, Unknown):
        return turn
    if turn[1] is None:
        return False
    end = turn[1]
    return any(s.start <= end and (s.end is None or s.end > end) for s in run.backgrounded)


def active_at(run: Run, at: float) -> Known[float]:
    i = max((k for k, m in enumerate(run.messages) if m.time <= at), default=None)
    if i is None:
        return Unknown(mctx("no message from its parent reached it by the launch"))
    nxt = run.period_end(i)
    until = nxt.time if nxt is not None else float("inf")
    if any(at < s.start < until for s in run.spans):
        return Unknown(mctx("a call of it began after the launch inside the period of its "
                            "latest message"))
    active = run.active_from(i)
    return Unknown(mctx("its start or a message to it is unknown")) if active is None else active


def budget_at(run: Run, at: float, undecided: list[str]) -> Known[float | None]:
    given = [b for m, b in zip(run.messages, budgets_in_force(run, undecided)) if m.time <= at]
    last = given[-1] if given else None
    return None if last is None else last * 60


def refused_at(entries: list[dict[str, Any]], at: float) -> int:
    return sum(1 for e in entries if e.get("timestamp") and epoch(e["timestamp"]) <= at
               for b in blocks(e, "tool_result") if b.get("is_error")
               and result_text(b, e.get("toolUseResult")).lstrip().startswith(REFUSALS))


def hung_count(listed_usual: dict[str, float], run: Run, at: float) -> int:
    return sum(1 for s in run.spans
               if hung_from(s.start, listed_usual[s.label]) <= min(
                   at, s.end if s.end is not None else float("inf")))


def edited(entries: list[dict[str, Any]], at: float, main: Path) -> frozenset[str]:
    out: set[str] = set()
    for e in entries:
        if e.get("type") != "assistant" or not e.get("timestamp") or epoch(e["timestamp"]) > at:
            continue
        for b in blocks(e, "tool_use"):
            if b.get("name") not in EDITS:
                continue
            p = str((b.get("input") or {}).get("file_path") or (b.get("input") or {}).get(
                "notebook_path") or "")
            if m := WORKTREE.search(p):
                out.add(m["rest"])
            elif p.startswith(f"{main}/"):
                out.add(p.removeprefix(f"{main}/"))
    return frozenset(out)


def scope_of(path: Path) -> Known[frozenset[str]]:
    m = SCOPE.search(path.read_text())
    if m is None:
        return Unknown(mctx("its change's ticket has no Scope section"))
    return frozenset(x.rstrip("/") for x in BACKTICKED.findall(m["body"]))


def run_at(a: Agent, audit: Audit, main: Path, tickets: dict[str, Any],
           undecided: list[str]) -> RunAt | str:
    """The run of `a` as of the launch of `audit`, or the reason it is
    unknown."""
    if a.agent_id is None:
        return mctx("its launch gives no agent id")
    try:
        path, launcher = find(a.agent_id), find(a.operator)
    except Refused as e:
        return str(e)
    launch = next((x for x in launches(launcher, undecided) if x.agent == a.agent_id), None)
    if launch is None:
        return mctx("the transcript of {operator} gives no launch of it").format(
            operator=a.operator)
    listed = turn_ended(node(launcher, launch, path, [], undecided), undecided)
    run, at = listed.run, audit.launched
    entries = run_entries(path)
    turn = turn_at(entries, run, at)
    usuals = {s.label: usual(listed, [listed], s.label) for s in run.spans}
    changed: Known[frozenset[str]] | None = None
    scope: Known[frozenset[str]] | None = None
    if a.role in EDITORS:
        t = tickets.get(a.subject)
        if t is None:
            scope = Unknown(mctx("no ticket {number} stands in the tracker").format(
                number=a.subject))
        else:
            scope = scope_of(t.path)
        changed = edited(entries, at, main)
    return RunAt(
        agent=replace(a, reports=tuple(r for r in a.reports if r.time <= at)), at=at,
        turn=turn, open_at_end=open_at(run, turn), active=active_at(run, at),
        budget=budget_at(run, at, undecided), refused=refused_at(entries, at),
        hung=hung_count(usuals, run, at),
        commands=tuple(s.command for s in run.spans if s.start <= at and s.command),
        changed=changed, scope=scope)


def reading_text(x: Reading) -> str:
    if x.fired is None:
        return mctx("undecided: {reason}").format(reason=x.reason)
    return mctx("fired") if x.fired else mctx("quiet")


def main() -> None:
    parser = argparse.ArgumentParser(description=HELP,
                                     formatter_class=argparse.RawDescriptionHelpFormatter,
                                     usage=argparse.SUPPRESS)
    parser.add_argument("session")
    args = parser.parse_args()
    started = time.time()
    main_path = main_tree()
    undecided: list[str] = []
    agents: list[Agent] = []
    calls: list[Call] = []
    messages: list[Message] = []
    passes: dict[str, tuple[str, ...] | None] = {}
    subjects: dict[str, float] = {}
    for c in commits(main_path):
        subjects[c.subject] = max(subjects.get(c.subject, c.time), c.time)
    for aid, path in operator_runs(args.session, ""):
        read_operator(aid, path, main_path, undecided, agents, calls, messages, passes,
                      subjects)
    tickets, _ = read_tickets(main_path / "tickets")
    by_id = {a.agent_id: a for a in agents if a.agent_id}
    audits = agent_audits(x for a in agents if (x := audit_of(a, undecided)) is not None)
    tally: Counter[tuple[str, str]] = Counter()
    for audit in audits:
        audited = by_id.get(audit.agent_id)
        model = ", ".join(models(find(audit.auditor))) or mctx("unknown")
        if audited is None:
            print(mctx("{agent}: no operator of the session launched it").format(
                agent=audit.agent_id))
            continue
        print(mctx("{agent} ({role}), auditor {auditor} ({models})").format(
            agent=audit.agent_id, role=audited.role, auditor=audit.auditor, models=model))
        r = run_at(audited, audit, main_path, tickets, undecided)
        if isinstance(r, str):
            print(INDENT + mctx("signals: undecided: {reason}").format(reason=r))
            fired = None
        else:
            found = signals(r)
            for x in found:
                print(INDENT + mctx("{signal}: {reading}").format(signal=x.signal,
                                                                  reading=reading_text(x)))
            fired = (True if any(x.fired for x in found)
                     else None if any(x.fired is None for x in found) else False)
        f = audit.finding
        verdict = (str(audit.read) if f is None else NO_SIGN if f.alert is None
                   else str(f.alert))
        print(INDENT + mctx("finding: {verdict}").format(verdict=verdict))
        for t in sorted(tickets.values(), key=lambda t: t.order):
            if t.domain is not Domain.AGENT or t.subject != audit.agent_id or not t.log \
                    or t.log[0].agent_id != audit.auditor:
                continue
            line = mctx("ticket {number} {kind}: {status}").format(
                number=t.number, kind=t.kind, status=t.status)
            if t.status is Status.CLOSED:
                line += mctx("; {note}").format(note=t.log[-1].note)
            print(INDENT + line)
        if f is not None:
            side = {True: mctx("a signal"), False: mctx("no signal"),
                    None: mctx("no signal fired and one undecided")}[fired]
            tally[(model, mctx("findings on runs with {side}").format(side=side))] += \
                f.alert is not None
            tally[(model, mctx("runs with {side}").format(side=side))] += 1
            if fired and f.alert is None:
                tally[(model, mctx("runs with a signal and no sign"))] += 1
    print()
    for (model, what), n in sorted(tally.items()):
        print(mctx("{model}: {what}: {n}").format(model=model, what=what, n=n))
    for line in dict.fromkeys(undecided):
        print(mctx("undecided: {line}").format(line=line), file=sys.stderr)
    print(mctx("seconds: {s}").format(s=round(time.time() - started)), file=sys.stderr)


if __name__ == "__main__":
    main()
