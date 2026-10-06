"""The budget of each agent type, and the budget in force for each message
from a run's parent, as the HELP of `profile_runs` gives them."""

import re

from controlled_markdown import mctx
from engine import checkout
from handbook.agents import agent_names, agent_sources
from run_profile import (Message, Part, Run, by_agent_type, clock, minutes,
                         one_line, percentile)

# The terms of a type's budget, which HELP states.
BUDGET_FACTOR = 2
WINDOW_RUNS = 5
LOW_WAIT_PCT = 10

# A brief line that states a budget, and the opening of a line that words one.
BUDGET_LINE = re.compile(r"Budget: (\d+(?:\.\d+)?) minutes\.?")
BUDGET_OPENING = re.compile(r"budget\s*:", re.I)
LIST_MARKER = re.compile(r"^\s*(?:[-*+]|\d+[.)])?\s*")


def low_wait(r: Run) -> bool:
    waited = r.parts[Part.WAITS] + r.parts[Part.IDLE]
    return waited * 100 < r.wall * LOW_WAIT_PCT


def type_window(kind: str, undecided: list[str]) -> float | None:
    """The start of the window of the agent type `kind`, as HELP gives it:
    the time of the last commit that changed its paths, or None where it
    has no agent document or no commit changed them."""
    if kind not in agent_names():
        return None
    paths = [str(checkout.shown(p)) for p in agent_sources(kind)]
    out = checkout.git_out(checkout.ROOT, "log", "-1", "--format=%ct", "--",
                           *paths).strip()
    if not out:
        undecided.append(mctx("{kind}: no commit changed its paths, so it has "
                              "no window").format(kind=kind))
        return None
    return float(out)


def print_budgets(runs: list[Run], since_date: float | None,
                  undecided: list[str]) -> None:
    """Print each agent type's budget, its basis, and the runs it is taken
    over. `since_date` is the start of the window `--since` sets, where it
    is given."""
    by_type = by_agent_type(runs)
    print(f"{'type':<18} {'budget':>7} {'runs':>4}  basis")
    for kind in sorted(by_type):
        rs = by_type[kind]
        since = since_date if since_date is not None else type_window(kind, undecided)
        window: list[Run] = []
        if since is not None:
            for r in rs:
                if r.start is None:
                    undecided.append(mctx("{run}: its start is unknown, so it is "
                                          "left out of the window").format(run=r.label))
                elif r.start >= since:
                    window.append(r)
        if len(window) >= WINDOW_RUNS:
            basis, chosen = mctx("since {date}").format(date=clock(since)), window
        else:
            basis = mctx("waits and idle under {pct}% of wall").format(pct=LOW_WAIT_PCT)
            chosen = [r for r in rs if low_wait(r)]
        if not chosen:
            undecided.append(mctx("{kind}: no run has waits and idle under "
                                  "{pct}% of wall, so it has no budget").format(
                kind=kind, pct=LOW_WAIT_PCT))
            continue
        budget = BUDGET_FACTOR * percentile([r.wall for r in chosen], 50)
        print(f"{kind:<18} {minutes(budget):>7} {len(chosen):>4}  {basis}")


def budget_openings(text: str) -> list[str]:
    """The lines of `text` that open with `Budget:`, past a list marker."""
    lines = (LIST_MARKER.sub("", line).strip() for line in text.splitlines())
    return [line for line in lines if BUDGET_OPENING.match(line)]


def message_name(r: Run, m: Message) -> str:
    """How an `undecided` line names a message from the parent of `r`."""
    if m is r.messages[0]:
        return mctx("the brief")
    return mctx("the message at {time}").format(time=clock(m.time))


def budgets_in_force(r: Run, undecided: list[str]) -> list[float | None]:
    """The budget in minutes in force for each message from the parent of
    `r`, which the latest message up to it states, as HELP gives it, or
    None."""
    for text in r.unknown:
        undecided.append(mctx("{run}: the sender of the message `{text}` is "
                              "unknown, so the run has no active time and no "
                              "budget").format(run=r.label, text=one_line(text)))
    budget: float | None = None
    budgets: list[float | None] = []
    for m in r.messages:
        stated: set[float] = set()
        for line in budget_openings(m.text):
            match = BUDGET_LINE.fullmatch(line)
            if match:
                stated.add(float(match.group(1)))
            else:
                undecided.append(mctx("{run}: the line `{line}` of {message} is "
                                      "not of the form `Budget: N minutes`, so "
                                      "it gives no budget").format(
                    run=r.label, line=line, message=message_name(r, m)))
        if len(stated) > 1:
            undecided.append(mctx("{run}: {message} states more than one budget, "
                                  "{values}, so it gives none").format(
                run=r.label, message=message_name(r, m),
                values=", ".join(f"{v:g}" for v in sorted(stated))))
        if stated:
            budget = next(iter(stated)) if len(stated) == 1 else None
        budgets.append(None if r.unknown else budget)
    return budgets


def of_budget(budget: float | None) -> str:
    """The text that follows an active time to give its budget in minutes."""
    return f" of budget {minutes(budget * 60)}" if budget is not None else ""
