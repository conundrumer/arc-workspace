"""The command line of the `operations` mod's monitor loop: it reads the
session's agents, as `profile_runs.py --running` lists them, the
coordinator's transcript and the monitor loop's record (`ops_record`),
and gives the monitor's next step, which `operations.monitor` computes.
`HELP`, which `--help` prints, gives its usage."""

import argparse
import contextlib
import io
import json
import os
import statistics
import sys
import time
from pathlib import Path

from controlled_markdown import mctx
from engine import checkout
from handbook.paths import console_importable, importable

console_importable()
# `scripts/` is no package: the modules below import from there.
importable(checkout.scripts())

from agent_launches import session_launches  # noqa: E402
from budgets import budgets_in_force  # noqa: E402
from filed_texts import report_file, report_text  # noqa: E402
from open_agents import Listed, running_agents  # noqa: E402
from ops_record import LOOP, MONITOR, read_record, record_agents, runs  # noqa: E402
from run_prints import active_of, print_running  # noqa: E402
from run_reads import Status as TaskStatus  # noqa: E402
from run_reads import (  # noqa: E402
    agent_messages,
    agent_type,
    notifications,
    run_entries,
    session_agents,
)
from senders import MONITORS  # noqa: E402
from transcripts import (  # noqa: E402
    Refused,
    epoch,
    find,
    main_transcript,
    new_state,
    session_directory,
)
from tree_reads import main_tree, scratch  # noqa: E402

from operations import monitor  # noqa: E402
from operations.monitor import (  # noqa: E402
    HUNG_FACTOR,
    NO_SIGN,
    REPORT_FORM,
    TO,
    VERDICT,
    Audit,
    Facet,
    MonitorState,
    Read,
    Sending,
    ToCoordinator,
    Watched,
)
from operations.roles import Role  # noqa: E402
from operations.state import Agent, Call  # noqa: E402
from operations.steps import (  # noqa: E402
    BLOCK_SECONDS,
    Launch,
    Poll,
    Step,
    call,
    filed,
    key,
    with_report,
)

HELP = mctx("""
    - Usage:
        ```
        uv run python scripts/monitor.py call {monitor}
        uv run python scripts/monitor.py unfinished {monitor}
        ```
    - `call` gives the next step of the monitor loop of the `operations` mod, as one line of JSON, in the form `operate.py call` gives a step, and `operate.py made {monitor}` records the call the mod made for it. It writes the brief of a launch to a file under the session's scratchpad, and the call's prompt gives that file's path, with the report file the auditor writes. Where no step is ready, it reads the state again each {poll} seconds, for up to {block} seconds, then gives a step of kind `wait`.
    - It launches an auditor on a message to the coordinator only where the coordinator's transcript gained that message while the operations loop ran, from a start that `operate.py start {loop}` recorded to the next stop that `operate.py stop {loop}` recorded. A run with no recorded stop counts as running where no later start is recorded, and otherwise up to the latest call of either loop's record before that start. A message after that call and before that start, which may have reached the coordinator after a hot reload of the mod or the session's end had ended the run, gets no audit, and `unfinished` gives a line on it.
    - `unfinished` reads the state once and prints the part for the coordinator that the operations loop's final reply ends with: an `unfinished` item on each line on what that read left unknown, and on each audit whose report is still in no form after the request to write it again; it prints nothing where there is none. The mod runs it once the monitor loop has stopped, so the part comes from a read after the monitor's last call.
    - The session is the one `CLAUDE_CODE_SESSION_ID` gives, and the command refuses where the shell gives none.
    {report_form}
    """)

POLL_SECONDS = 60


def usual(listed: Listed, listing: list[Listed], label: str) -> float:
    """The median duration of the ended calls of `listed` with `label`, or
    where it has none, of those of every run of `listing`, or where none
    has one, `BLOCK_SECONDS`."""
    def ended(runs: list[Listed]) -> list[float]:
        return [s.end - s.start for r in runs for s in r.run.spans
                if s.label == label and s.end is not None]
    durations = ended([listed]) or ended(listing)
    return statistics.median(durations) if durations else BLOCK_SECONDS


def hung_at(listed: Listed, listing: list[Listed]) -> float | None:
    """The earliest time a call of `listed` in flight passed `HUNG_FACTOR`
    times its label's usual time, or None where none has."""
    now = time.time()
    times = [at for s in listed.run.in_flight
             if (at := s.start + HUNG_FACTOR * usual(listed, listing, s.label)) <= now]
    return min(times, default=None)


def activity(listed: Listed) -> float:
    """The time of the latest call, end of a call, end of the turn or
    report of `listed`."""
    r = listed.run
    times = [s.start for s in r.spans] + [s.end for s in r.spans if s.end is not None]
    times += [rep.time for rep in listed.found or []]
    if listed.end is not None:
        times.append(listed.end)
    if r.start is not None:
        times.append(r.start)
    return max(times, default=0.0)


def facts(listed: Listed, since: float | None, undecided: list[str]) -> str:
    """The listing `profile_runs.py --running` prints of `listed`, with its
    calls since `since`."""
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        print_running([listed], time.time(), since, undecided)
    return out.getvalue().rstrip("\n")


def watched(listing: list[Listed], audits: list[Audit], undecided: list[str]) -> list[Watched]:
    out: list[Watched] = []
    now = time.time()
    for listed in listing:
        r = listed.run
        aid = listed.launch.agent
        if aid is None or r.agent_type in MONITORS:
            continue
        past = [a.launched for a in audits if a.facet is Facet.AGENT and a.agent_id == aid]
        budget = next(reversed(budgets_in_force(r, undecided)), None)
        active = active_of(listed, now)
        out.append(Watched(
            agent_id=aid, agent_type=r.agent_type, parent=listed.parent,
            activity=activity(listed), hung=hung_at(listed, listing),
            over_budget=budget is not None and active is not None and active > budget * 60,
            facts=facts(listed, max(past, default=None), undecided), transcript=r.path))
    return out


def audit_of(a: Agent, undecided: list[str]) -> Audit | None:
    """The audit the launch `a` gives, or None where it is no auditor's, or
    where its subject is in no form `monitor.subject` gives: that launch
    counts as no audit, so the activity it was to audit stays new, and
    `undecided` gains a line on it."""
    if a.role is not Role.OP_AUDITOR or a.agent_id is None:
        return None
    given = monitor.subject_of(a.subject)
    if given is None:
        undecided.append(mctx("{agent}: this auditor's launch has the subject `{subject}`, in "
                              "no form the command gives, so it counts as no audit")
                         .format(agent=a.agent_id, subject=a.subject))
        return None
    replies = tuple(r.time for r in a.reports)
    read, found = Read.PENDING, None
    if a.last_report is not None and not a.pending:
        text: str | None = a.last_report.text
        path = report_file(a.last_report.text)
        if path is not None:
            text = report_text(path, a.agent_id, undecided)
        if text is None:
            read = Read.GONE
        else:
            found = monitor.finding(text)
            read = Read.UNREAD if found is None else Read.READ
    return Audit(a.agent_id, *given, a.launched, replies, read, found)


def sendings(calls: list[Call]) -> list[Sending]:
    return [Sending(str(c.input.get("to", "")), str(c.input.get("message", "")), c.time)
            for c in calls if c.tool == "SendMessage" and not c.error]


def to_coordinator(session: Path, since: float, undecided: list[str]) -> list[ToCoordinator]:
    """The messages to the coordinator from an agent of the session other
    than the monitor and its auditors, and the notifications of the end of
    one, that the coordinator's transcript gained after `since`."""
    parents = {kid: launcher for launcher, kids in session_launches(session)[1].items()
               for kid in kids}
    agents: dict[str, tuple[str, str, Path]] = {}
    for aid, p in session_agents(session).items():
        kind = agent_type(p)
        if kind is None or kind in MONITORS:
            continue
        if aid not in parents:
            undecided.append(mctx("{agent}: no `.meta.json` gives its parent, so its messages "
                                  "to the coordinator are not audited").format(agent=aid))
            continue
        agents[aid] = (kind, parents[aid], p)
    out: list[ToCoordinator] = []
    for e in run_entries(main_transcript(session)):
        stamp = e.get("timestamp")
        if e.get("type") != "user" or not stamp or (t := epoch(stamp)) <= since:
            continue
        for sender, text in agent_messages(e):
            if sender in agents:
                out.append(ToCoordinator(sender, *agents[sender], t, text))
        for n in notifications(e):
            if n.status is TaskStatus.RUNNING:
                continue
            for aid in n.ids:
                if aid in agents:
                    out.append(ToCoordinator(aid, *agents[aid], t, n.result or n.note or ""))
    return out


def read_monitor(me: str) -> MonitorState:
    new_state()
    session = os.environ.get("CLAUDE_CODE_SESSION_ID")
    if not session:
        raise Refused(mctx("the shell gives no `CLAUDE_CODE_SESSION_ID`"))
    undecided: list[str] = []
    ran = tuple(runs(scratch(session)))
    calls = read_record(scratch(session), me, me, {}, undecided)[0]
    agents = record_agents(calls, main_tree(), {})
    audits = [a for x in agents if (a := audit_of(x, undecided)) is not None]
    directory = session_directory(find(session))
    state = MonitorState(
        watched=tuple(watched(running_agents(find(session), undecided), audits, undecided)),
        to_coordinator=tuple(to_coordinator(directory, ran[0].start, undecided) if ran else ()),
        audits=tuple(audits), sendings=tuple(sendings(calls)), runs=ran,
        undecided=tuple(undecided))
    return state


def next_step(me: str) -> Step:
    """The monitor's next step, after a block of up to `BLOCK_SECONDS`
    while none is ready."""
    deadline = time.time() + BLOCK_SECONDS
    while True:
        s = monitor.step(read_monitor(me))
        if not isinstance(s, Poll) or time.time() + POLL_SECONDS > deadline:
            return s
        time.sleep(POLL_SECONDS)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(
        description=HELP.format(poll=POLL_SECONDS, block=BLOCK_SECONDS, monitor=MONITOR,
                                loop=LOOP,
                                report_form=REPORT_FORM.format(no_sign=NO_SIGN, to=TO,
                                                               verdict=VERDICT)),
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("action", choices=["call", "unfinished"])
    ap.add_argument("agent", choices=[MONITOR])
    args = ap.parse_args(argv)
    try:
        if args.action == "unfinished":
            print(monitor.unfinished(read_monitor(args.agent)))
            return 0
        s = next_step(args.agent)
        session = os.environ["CLAUDE_CODE_SESSION_ID"]
        pad = scratch(session)
        if isinstance(s, Launch):
            s = with_report(s, pad)
        for p, text in filed(s, pad).items():
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text)
        print(json.dumps(call(s, pad, key(s))))
    except Refused as e:
        print(mctx("refused: {reason}").format(reason=e), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
