"""The prints of the agents whose work is open under a run, of the messages
from a run's parent, and of the run's report to that parent, as
`profile_runs.py --help running` and `profile_runs.py --help one` give them."""

from collections.abc import Callable

from agent_reports import Report
from budgets import budgets_in_force, of_budget, past_budget
from context_bound_hook import CONTEXT_BOUND, bounded, past_bound
from controlled_markdown import mctx
from open_agents import Listed, parent_reports
from run_profile import clock, minutes, minutes_or_unknown, one_line
from run_records import Run, Span
from run_reads import MAIN
from ticketing.times import utc_stamp

# The number of a listed agent's last calls that `--running` prints.
RECENT_CALLS = 8


def print_span(m: Span, time_text: str) -> None:
    command = f": {one_line(m.command)}" if m.command else ""
    print(f"    {time_text:>8}  {m.label}{command}")


def active_of(listed: Listed, now: float) -> float | None:
    """The active time `--running` gives a listed agent, or None where it is
    unknown."""
    return latest_of(listed, listed.run.active_from, lambda: listed.run.active_at(now))


def self_of(listed: Listed, now: float) -> float | None:
    """The self time `--running` gives a listed agent, or None where it is
    unknown."""
    return latest_of(listed, listed.run.self_from, lambda: listed.run.self_at(now))


def latest_of(listed: Listed, over: Callable[[int], float | None],
              running: Callable[[], float | None]) -> float | None:
    """`over` of the latest message from a listed agent's parent where its
    turn has ended, and `running` otherwise."""
    r = listed.run
    return over(len(r.messages) - 1) if listed.ended and r.messages else running()


def print_running(agents: list[Listed], now: float, calls_since: float | None,
                  undecided: list[str]) -> None:
    for listed in agents:
        r = listed.run
        since = minutes_or_unknown(now - r.start if r.start is not None else None)
        last = len(r.messages) - 1
        active_time = active_of(listed, now)
        period_end = r.period_end(last) if r.messages else None
        to = (" " + mctx("to {time}").format(time=clock(period_end.time))
              if period_end else "")
        active = (mctx("{active} since {time}{to}").format(
            active=minutes(active_time), time=clock(r.messages[-1].time), to=to)
            if active_time is not None else "?")
        self_time = self_of(listed, now)
        self_text = minutes_or_unknown(self_time)
        budget = next(reversed(budgets_in_force(r, undecided)), None)
        context = f"{r.context:,}" if r.context is not None else "?"
        past = "past " if past_bound(r.context) else ""
        mark = (" " + mctx("{past}bound {bound:,}").format(
            past=past, bound=CONTEXT_BOUND) if bounded(r.agent_type) else "")
        print(f"{r.label} {r.agent_type}  parent {listed.parent}  {since}  "
              f"active {active}  self {self_text}{of_budget(budget)}  "
              f"context {context} tokens{mark}: {r.description}")
        print(f"  cwd: {r.cwd or '?'}")
        if listed.ended:
            print_ended(r, listed.end, now, undecided)
            print_report_line(r, listed.found)
        print(f"  said: {one_line(r.said, tail=True) if r.said is not None else '-'}")
        for title, spans in (("in flight", r.in_flight), ("running", listed.running)):
            if spans:
                print(f"  {title}:")
            for m in spans:
                print_span(m, minutes(now - m.start))
        recent = r.spans[-RECENT_CALLS:]
        if calls_since is None:
            print("  recent:")
        else:
            recent = [m for m in recent if m.end is None or m.end >= calls_since]
            since_text = utc_stamp(calls_since)
            none = "" if recent else " " + mctx("none")
            print("  " + mctx("recent since {time}:{none}").format(
                time=since_text, none=none))
        for m in recent:
            print_span(m, minutes(m.end - m.start) if m.end is not None else "pending")


def print_ended(r: Run, end: float | None, now: float,
                undecided: list[str]) -> None:
    if end is None:
        undecided.append(mctx("{run}: no timestamped entry of its transcripts "
                              "ends a turn, so when its turn ended is unknown").format(
            run=r.label))
        print("  " + mctx("turn ended: ?"))
        return
    print("  " + mctx("turn ended: {time}, {ago} ago").format(
        time=clock(end), ago=minutes(now - end)))


def print_messages(r: Run, undecided: list[str]) -> None:
    """Print each message from the parent of `r` with its active time, its
    self time and the budget in force for it, marking each self time past its
    budget."""
    if r.agent_type == MAIN:
        return
    print("  messages from the parent:")
    budgets = budgets_in_force(r, undecided)
    for i, (m, budget) in enumerate(zip(r.messages, budgets, strict=True)):
        active, self_time = r.active_from(i), r.self_from(i)
        past = "  past budget" if past_budget(self_time, budget) else ""
        active_text = minutes_or_unknown(active)
        self_text = minutes_or_unknown(self_time)
        print(f"    {clock(m.time)}  active {active_text}  self {self_text}"
              f"{of_budget(budget)}{past}")


def print_report_line(r: Run, found: list[Report] | None) -> None:
    if found is None:
        print("  " + mctx("report to the parent: ?"))
    elif not found:
        print("  " + mctx("report to the parent: none after the message at "
                          "{time}").format(time=clock(r.messages[-1].time)))
    else:
        last = found[-1]
        print("  " + mctx("report to the parent: {time} {kind}: {text}").format(
            time=clock(last.time), kind=last.kind.value, text=one_line(last.text)))


def print_report(r: Run, undecided: list[str]) -> None:
    """Print the latest report of the subagent of `r` that reached its
    parent after the parent's latest message to it, as `profile_runs.py --help one` gives it."""
    if r.agent_type != MAIN:
        print_report_line(r, parent_reports(r, undecided))
