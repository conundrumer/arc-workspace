"""The command line of `op-monitor`: it reads the session's agents, as
`profile_runs.py --running` lists them, the coordinator's transcript and
the monitor's own transcript, and prints the monitor's next step, which
`operations.monitor` computes. `HELP`, which `--help` prints, gives its
usage."""

import argparse
import contextlib
import io
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
from agent_turns import first_time  # noqa: E402
from budgets import budgets_in_force  # noqa: E402
from filed_texts import report_file, report_text  # noqa: E402
from open_agents import Listed, running_agents, work_open  # noqa: E402
from operator_reads import operator_runs, read_operator  # noqa: E402
from run_prints import active_of, print_running  # noqa: E402
from run_reads import (agent_messages, agent_type, notifications, run_entries,  # noqa: E402
                       session_agents)
from run_reads import Status as TaskStatus  # noqa: E402
from senders import MONITORS  # noqa: E402
from transcripts import (Refused, epoch, find, main_transcript, new_state,  # noqa: E402
                         session_directory)
from tree_reads import main_tree, scratch  # noqa: E402

from operations import monitor  # noqa: E402
from operations.monitor import (HUNG_FACTOR, NO_SIGN, REPORT_FORM, TO, VERDICT,  # noqa: E402
                                Audit, Facet, MonitorState, Read, Sending, ToCoordinator,
                                Watched)
from operations.roles import Role  # noqa: E402
from operations.state import Agent, Call, Message  # noqa: E402
from operations.steps import (BLOCK_SECONDS, Launch, Poll, Step, filed, printed,  # noqa: E402
                              with_report)

HELP = mctx("""
    - Usage:
        ```
        uv run python scripts/monitor.py next <agent id>
        ```
    - `next` prints the next step of the monitor whose agent id it is given: one call to make, with its parameters, or the monitor's final reply. It writes the brief of a launch to a file under the session's scratchpad, and the call's prompt gives that file's path, with the report file the auditor writes. The value of a prompt or a message parameter it prints stands between two lines of three backticks, and the value to pass is the text between those lines, without them. Where no step is ready, it reads the state again each {poll} seconds, for up to {block} seconds, then prints that the monitor runs it again.
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
    one, that the coordinator's transcript gained since `since`."""
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
    path = find(me)
    agents: list[Agent] = []
    calls: list[Call] = []
    read_operator(me, path, main_tree(), undecided, agents, calls, list[Message](), {}, {})
    audits = [a for x in agents if (a := audit_of(x, undecided)) is not None]
    start = first_time(path)
    if start is None:
        raise Refused(mctx("the transcript of {agent} gives no time").format(agent=me))
    directory = session_directory(find(session))
    state = MonitorState(
        watched=tuple(watched(running_agents(find(session), undecided), audits, undecided)),
        to_coordinator=tuple(to_coordinator(directory, start, undecided)),
        audits=tuple(audits), sendings=tuple(sendings(calls)),
        operator_runs=any(work_open(p, []) for _, p in operator_runs(session, me)),
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
        description=HELP.format(poll=POLL_SECONDS, block=BLOCK_SECONDS,
                                report_form=REPORT_FORM.format(no_sign=NO_SIGN, to=TO,
                                                               verdict=VERDICT)),
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("action", choices=["next"])
    ap.add_argument("agent")
    args = ap.parse_args(argv)
    try:
        s = next_step(args.agent)
        session = os.environ["CLAUDE_CODE_SESSION_ID"]
        pad = scratch(session)
        if isinstance(s, Launch):
            s = with_report(s, pad)
        for p, text in filed(s, pad).items():
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text)
        print(printed(s, args.agent, pad))
    except Refused as e:
        print(mctx("refused: {reason}").format(reason=e), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
