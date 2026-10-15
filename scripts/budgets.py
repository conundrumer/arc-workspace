"""The budget of each agent type, and of each role of
`roles.GENERAL_ROLES`, for a run and for one item of a brief that gives
items, the runs its budget cut, and the budget in force for each message
from a run's parent, as `profile_runs.py --help budget`
and `profile_runs.py --help messages` give them."""

import re
from dataclasses import dataclass
from functools import cache
from pathlib import Path

from agent_reports import parent_type
from context_bound_hook import OPERATOR
from controlled_markdown import mctx
from engine import checkout
from handbook.agents import agent_names, agent_prompt_text, agent_sources
from operations import brief_reading, briefs
from operations.reports import BUDGET_PASSED
from operations.roles import GENERAL, GENERAL_ROLES, Role, described
from run_profile import clock, minutes, one_line, percentile
from run_records import Message, Part, Run
from run_reads import parent_id
from transcripts import is_subagent
from transcript_entries import Refused

# The terms of the budget of a type or a role, which `profile_runs.py --help budget` states.
BUDGET_FACTOR = 2
MEDIAN_RUNS = 5
LOW_WAIT_PCT = 10

# The opening of a line that words a budget.
BUDGET_OPENING = re.compile(r"budget\s*:", re.I)


def low_wait(r: Run) -> bool:
    waited = r.parts[Part.WAITS] + r.parts[Part.IDLE]
    return waited * 100 < r.wall * LOW_WAIT_PCT


def budget_group(r: Run) -> str | None:
    """The budget `r` joins, as `--help budget` gives it: the role its description
    gives where its agent type is `general-purpose`, None where that
    description gives no role of `roles.GENERAL_ROLES`, and otherwise its
    agent type."""
    if r.agent_type != GENERAL:
        return r.agent_type
    d = described(r.description)
    return None if d is None else general_group(d.role)


def general_group(role: Role) -> str | None:
    """The budget of its own that `role` has where it is a role of
    `roles.GENERAL_ROLES`, and None where it has none."""
    return role.value if role in GENERAL_ROLES else None


def role_group(role: Role) -> str:
    """The budget a brief of `role` gets, as `budget_group` names it."""
    group = general_group(role)
    return role.agent_type if group is None else group


def type_window(kind: str, undecided: list[str]) -> float | None:
    """The start of the window of the budget `kind`, as `--help budget` gives it: the
    time of the last commit that changed its paths, or None where it has
    no paths or no commit changed them."""
    if kind in GENERAL_ROLES:
        sources = [Path(briefs.__file__)]
    elif kind in agent_names():
        sources = agent_sources(kind)
    else:
        return None
    paths = [str(checkout.shown(p)) for p in sources]
    out = checkout.git_out(checkout.ROOT, "log", "-1", "--format=%ct", "--",
                           *paths).strip()
    if not out:
        undecided.append(mctx("{kind}: no commit changed its paths, so it has "
                              "no window").format(kind=kind))
        return None
    return float(out)


@dataclass(frozen=True)
class Budget:
    """The budget of an agent type or a role in seconds, for a run or for one item, the
    runs it is taken over, and its basis."""
    seconds: float
    runs: int
    basis: str


def measured(r: Run, per_item: bool) -> float | None:
    """The wall time of `r`, or where `per_item`, its wall time per item of
    its brief, or None where its brief gives no items."""
    if not per_item:
        return r.wall
    count = brief_reading.items(r.messages[0].text) if r.messages else None
    return None if count is None else r.wall / count


def type_budget(kind: str, runs: list[Run], since_date: float | None, per_item: bool,
                undecided: list[str]) -> Budget | None:
    """The budget `kind`, an agent type or a role, over `runs`, its runs, as `--help budget`
    gives it, for a run, or where `per_item`, for one item of a brief that
    gives items, or None where it gets none. `since_date` is the start of
    the window `--since` sets, where it is given."""
    rs = [(r, w) for r in runs
          if operator_launched(r, undecided) and censored(r, undecided) is False
          and (w := measured(r, per_item)) is not None]
    which = (mctx("runs an operator launched, not cut, whose brief gives "
                  "items") if per_item
             else mctx("runs an operator launched, not cut"))
    since = since_date if since_date is not None else type_window(kind, undecided)
    window: list[tuple[Run, float]] = []
    if since is not None:
        for r, w in rs:
            if r.start is None:
                undecided.append(mctx("{run}: its start is unknown, so it is "
                                      "left out of the window").format(run=r.label))
            elif r.start >= since:
                window.append((r, w))
    if len(window) >= MEDIAN_RUNS:
        basis = mctx("{which} since {date}").format(which=which, date=clock(since))
        chosen = window
    else:
        basis = mctx("{which}, waits and idle under {pct}% of "
                     "wall").format(which=which, pct=LOW_WAIT_PCT)
        chosen = [(r, w) for r, w in rs if low_wait(r)]
        if len(chosen) < MEDIAN_RUNS:
            undecided.append(mctx("{kind}: its {which} with waits and "
                                  "idle under {pct}% of wall number {count}, "
                                  "fewer than {least}, so it has no "
                                  "budget{per}").format(
                kind=kind, which=which, count=len(chosen), pct=LOW_WAIT_PCT,
                least=MEDIAN_RUNS, per=" " + mctx("per item") if per_item else ""))
            return None
    return Budget(BUDGET_FACTOR * percentile([w for _, w in chosen], 50), len(chosen), basis)


def print_budgets(runs: list[Run], since_date: float | None,
                  undecided: list[str]) -> None:
    """Print the budget of each agent type and of each role of
    `roles.GENERAL_ROLES`, its budget per item where some of its runs have
    a brief that gives items, their bases, and the runs each is taken
    over."""
    groups: dict[str, list[Run]] = {}
    for r in runs:
        if (group := budget_group(r)) is not None:
            groups.setdefault(group, []).append(r)
    print(f"{'type or role':<18} {'budget':>7} {'runs':>4}  basis")
    for kind in sorted(groups):
        rs = groups[kind]
        b = type_budget(kind, rs, since_date, False, undecided)
        if b is not None:
            print(f"{kind:<18} {minutes(b.seconds):>7} {b.runs:>4}  {b.basis}")
        if any(measured(r, True) is not None for r in rs):
            b = type_budget(kind, rs, since_date, True, undecided)
            if b is not None:
                print(f"{'':<18} {minutes(b.seconds):>7} {b.runs:>4}  "
                      + mctx("per item, {basis}").format(basis=b.basis))


def budget_openings(text: str) -> list[str]:
    """The lines of `text` that open with `Budget:`, past a list marker."""
    lines = (brief_reading.unmarked(line) for line in text.splitlines())
    return [line for line in lines if BUDGET_OPENING.match(line)]


def message_name(r: Run, m: Message) -> str:
    """How an `undecided` line names a message from the parent of `r`."""
    if m is r.messages[0]:
        return mctx("the brief")
    return mctx("the message at {time}").format(time=clock(m.time))


def budgets_in_force(r: Run, undecided: list[str]) -> list[float | None]:
    """The budget in minutes in force for each message from the parent of
    `r`, which the latest message up to it states, as `--help messages` gives it, or
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
            match = brief_reading.BUDGET_LINE.fullmatch(line)
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


def operator_launched(r: Run, undecided: list[str]) -> bool:
    """Whether an operator launched `r`, as `--help budget` gives it. A run whose
    parent's type is unknown is left out, and an `undecided` line names
    it."""
    if not is_subagent(r.path):
        return False
    try:
        kind = parent_type(r.path)
    except Refused:
        kind = None
    if kind is None:
        undecided.append(mctx("{run}: the type of its parent {parent} is "
                              "unknown, so it is left out of its type's "
                              "budget").format(run=r.label, parent=parent_id(r.path)))
        return False
    return kind == OPERATOR


@cache
def acts_at_budget(kind: str) -> bool:
    """Whether the documents of the agent type `kind` give what it does at
    its budget, as `--help budget` gives it."""
    return kind in agent_names() and f"`{BUDGET_PASSED}`" in agent_prompt_text(kind)


def censored(r: Run, undecided: list[str]) -> bool | None:
    """Whether `r` is censored, cut by its budget as `--help budget` gives it,
    or None where it gives that unknown."""
    if not acts_at_budget(r.agent_type):
        return False
    unknown = False
    for i, budget in enumerate(budgets_in_force(r, undecided)):
        if budget is None:
            continue
        self_time = r.self_from(i)
        if self_time is None:
            unknown = True
        elif past_budget(self_time, budget):
            return True
    if unknown:
        undecided.append(mctx("{run}: the self time of a message with a budget "
                              "in force is unknown, so whether its budget cut it "
                              "is unknown, and it is left out of its type's "
                              "budget").format(run=r.label))
        return None
    return False


def past_budget(self_time: float | None, budget: float | None) -> bool:
    """Whether a self time in seconds is known and past a budget in minutes."""
    return self_time is not None and budget is not None and self_time > budget * 60


def of_budget(budget: float | None) -> str:
    """The text that follows a self time to give its budget in minutes."""
    return f" of budget {minutes(budget * 60)}" if budget is not None else ""
