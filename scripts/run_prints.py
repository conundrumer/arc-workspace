"""The prints of the agents running under a run, of the messages from a
run's parent, and of the run's report to that parent, as the HELP of
`profile_runs` gives them."""

from agent_launches import Report, reports
from budgets import budgets_in_force, of_budget
from controlled_markdown import mctx
from run_profile import Run, Span, clock, minutes, one_line
from run_reads import MAIN

# The number of a running agent's last calls that `--running` prints.
RECENT_CALLS = 8


def print_span(m: Span, time_text: str) -> None:
    command = f": {one_line(m.command)}" if m.command else ""
    print(f"    {time_text:>8}  {m.label}{command}")


def print_running(runs: list[tuple[str, Run]], now: float,
                  undecided: list[str]) -> None:
    for parent, r in runs:
        since = minutes(now - r.start) if r.start is not None else "?"
        active_time = r.active_at(now)
        ended = r.period_end(len(r.messages) - 1) if r.messages else None
        to = " " + mctx("to {time}").format(time=clock(ended.time)) if ended else ""
        active = (mctx("{active} since {time}{to}").format(
            active=minutes(active_time), time=clock(r.messages[-1].time), to=to)
            if active_time is not None else "?")
        budget = next(reversed(budgets_in_force(r, undecided)), None)
        context = f"{r.context:,}" if r.context is not None else "?"
        print(f"{r.label} {r.agent_type}  parent {parent}  {since}  "
              f"active {active}{of_budget(budget)}  "
              f"context {context} tokens: {r.description}")
        print(f"  cwd: {r.cwd or '?'}")
        print(f"  said: {one_line(r.said, tail=True) if r.said is not None else '-'}")
        for title, spans in (("in flight", r.in_flight), ("running", r.backgrounded)):
            if spans:
                print(f"  {title}:")
            for m in spans:
                print_span(m, minutes(now - m.start))
        print("  recent:")
        for m in r.spans[-RECENT_CALLS:]:
            print_span(m, minutes(m.end - m.start) if m.end is not None else "pending")


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


def print_report(r: Run, undecided: list[str]) -> None:
    """Print the latest report of the subagent of `r` that reached its
    parent after the parent's latest message to it, as HELP gives it."""
    if r.agent_type == MAIN:
        return
    found: list[Report] | None = None
    if r.unknown or not r.messages:
        undecided.append(mctx("{run}: the latest message from its parent is "
                              "unknown, so whether a report reached the parent "
                              "after it is unknown").format(run=r.label))
    else:
        found = reports(r.path, r.messages[-1].time, undecided)
    if found is None:
        print("  " + mctx("report to the parent: ?"))
    elif not found:
        print("  " + mctx("report to the parent: none after the message at "
                          "{time}").format(time=clock(r.messages[-1].time)))
    else:
        last = found[-1]
        print("  " + mctx("report to the parent: {time} {kind}: {text}").format(
            time=clock(last.time), kind=last.kind.value, text=one_line(last.text)))
