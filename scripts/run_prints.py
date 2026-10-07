"""The prints of the agents whose work is open under a run, of the messages
from a run's parent, and of the run's report to that parent, as the HELP of
`profile_runs` gives them."""

import time

from agent_reports import Report
from budgets import budgets_in_force, of_budget
from context_bound_hook import CONTEXT_BOUND, OPERATOR, past_bound
from controlled_markdown import mctx
from open_agents import Listed, parent_reports
from run_profile import Run, Span, clock, minutes, one_line
from run_reads import MAIN
from ticket_log import TIME_FORM

# The number of a listed agent's last calls that `--running` prints.
RECENT_CALLS = 8


def print_span(m: Span, time_text: str) -> None:
    command = f": {one_line(m.command)}" if m.command else ""
    print(f"    {time_text:>8}  {m.label}{command}")


def print_running(agents: list[Listed], now: float, calls_since: float | None,
                  undecided: list[str]) -> None:
    for listed in agents:
        r = listed.run
        since = minutes(now - r.start) if r.start is not None else "?"
        last = len(r.messages) - 1
        active_time = (r.active_from(last) if listed.ended and r.messages
                       else r.active_at(now))
        period_end = r.period_end(last) if r.messages else None
        to = (" " + mctx("to {time}").format(time=clock(period_end.time))
              if period_end else "")
        active = (mctx("{active} since {time}{to}").format(
            active=minutes(active_time), time=clock(r.messages[-1].time), to=to)
            if active_time is not None else "?")
        budget = next(reversed(budgets_in_force(r, undecided)), None)
        context = f"{r.context:,}" if r.context is not None else "?"
        past = "past " if past_bound(r.agent_type, r.context) else ""
        mark = ("" if r.agent_type != OPERATOR else
                " " + mctx("{past}bound {bound:,}").format(
                    past=past, bound=CONTEXT_BOUND))
        print(f"{r.label} {r.agent_type}  parent {listed.parent}  {since}  "
              f"active {active}{of_budget(budget)}  "
              f"context {context} tokens{mark}: {r.description}")
        print(f"  cwd: {r.cwd or '?'}")
        if listed.ended:
            print_ended(r, listed.end, now, undecided)
            print_report_line(r, listed.found)
        print(f"  said: {one_line(r.said, tail=True) if r.said is not None else '-'}")
        for title, spans in (("in flight", r.in_flight), ("running", r.backgrounded)):
            if spans:
                print(f"  {title}:")
            for m in spans:
                print_span(m, minutes(now - m.start))
        recent = r.spans[-RECENT_CALLS:]
        if calls_since is None:
            print("  recent:")
        else:
            recent = [m for m in recent if m.end is None or m.end >= calls_since]
            since_text = time.strftime(TIME_FORM, time.gmtime(calls_since))
            none = "" if recent else " " + mctx("none")
            print("  " + mctx("recent since {time}:{none}").format(
                time=since_text, none=none))
        for m in recent:
            print_span(m, minutes(m.end - m.start) if m.end is not None else "pending")


def print_ended(r: Run, end: float | None, now: float,
                undecided: list[str]) -> None:
    if end is None:
        undecided.append(mctx("{run}: no `user` or `assistant` entry gives a "
                              "time, so when its turn ended is unknown").format(
            run=r.label))
        print("  " + mctx("turn ended: ?"))
        return
    print("  " + mctx("turn ended: {time}, {ago} ago").format(
        time=clock(end), ago=minutes(now - end)))


def print_messages(r: Run, undecided: list[str]) -> None:
    """Print each message from the parent of `r` with its active time and
    the budget in force for it, marking each active time past its budget."""
    if r.agent_type == MAIN:
        return
    print("  messages from the parent:")
    budgets = budgets_in_force(r, undecided)
    for i, (m, budget) in enumerate(zip(r.messages, budgets, strict=True)):
        active = r.active_from(i)
        past = ("  past budget" if active is not None and budget is not None
                and active > budget * 60 else "")
        active_text = minutes(active) if active is not None else "?"
        print(f"    {clock(m.time)}  active {active_text}{of_budget(budget)}{past}")


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
    parent after the parent's latest message to it, as HELP gives it."""
    if r.agent_type != MAIN:
        print_report_line(r, parent_reports(r, undecided))
