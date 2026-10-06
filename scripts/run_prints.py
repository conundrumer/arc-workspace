"""The prints of the agents whose work is open under a run, of the messages
from a run's parent, and of the run's report to that parent, as the HELP of
`profile_runs` gives them."""

from agent_launches import Launch, Listed, Report, reports
from budgets import budgets_in_force, of_budget
from controlled_markdown import mctx
from run_profile import Run, Span, clock, minutes, one_line
from run_reads import MAIN

# The number of a listed agent's last calls that `--running` prints.
RECENT_CALLS = 8


def print_span(m: Span, time_text: str) -> None:
    command = f": {one_line(m.command)}" if m.command else ""
    print(f"    {time_text:>8}  {m.label}{command}")


def print_running(runs: list[tuple[Listed, Run]], now: float,
                  undecided: list[str]) -> None:
    """Print each agent of `runs` whose work is open, as HELP gives it: an
    agent whose turn has ended is passed over where a report of it reached
    its parent after the parent's latest message to it."""
    for listed, r in runs:
        found = parent_reports(r, undecided, listed.launch) if listed.ended else None
        if found:
            continue
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
        print(f"{r.label} {r.agent_type}  parent {listed.parent}  {since}  "
              f"active {active}{of_budget(budget)}  "
              f"context {context} tokens: {r.description}")
        print(f"  cwd: {r.cwd or '?'}")
        if listed.ended:
            print_ended(r, listed.end, now, undecided)
            print_report_line(r, found)
        print(f"  said: {one_line(r.said, tail=True) if r.said is not None else '-'}")
        for title, spans in (("in flight", r.in_flight), ("running", r.backgrounded)):
            if spans:
                print(f"  {title}:")
            for m in spans:
                print_span(m, minutes(now - m.start))
        print("  recent:")
        for m in r.spans[-RECENT_CALLS:]:
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


def parent_reports(r: Run, undecided: list[str],
                   launch: Launch | None = None) -> list[Report] | None:
    """The reports of the subagent of `r` that reached its parent after the
    parent's latest message to it, as HELP gives them, or None where that
    message or the parent's transcripts are unknown. With `launch`, its
    launch, they are read from the transcripts of the run that launched
    it."""
    if r.unknown or not r.messages:
        undecided.append(mctx("{run}: the latest message from its parent is "
                              "unknown, so whether a report reached the parent "
                              "after it is unknown").format(run=r.label))
        return None
    since = r.messages[-1].time
    return (launch.reports(since, undecided) if launch
            else reports(r.path, since, undecided))


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
