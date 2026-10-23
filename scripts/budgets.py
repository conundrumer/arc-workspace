"""The budget of each agent type, and of each role of
`roles.GENERAL_ROLES`, for a run and for one item of a brief that gives
items, as `profile_runs.py --help budget` gives it, and the budget of a
brief over every run under the project directories (`group_budgets`)."""

import json
import subprocess
import sys
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path

from agent_reports import parent_type
from context_bound_hook import OPERATOR
from controlled_markdown import mctx
from engine import checkout
from handbook.agents import agent_names, agent_sources
from operations import brief_reading, briefs
from operations.roles import GENERAL, GENERAL_ROLES, Role, described
from run_profile import clock, minutes, percentile
from run_records import Part, Run
from run_reads import parent_id
from run_store import RunStore
from transcripts import agent_transcripts, is_subagent
from transcript_snapshots import Refused

# The terms of the budget of a type or a role, which `profile_runs.py --help budget` states.
BUDGET_FACTOR = 2
MEDIAN_RUNS = 5
LOW_WAIT_PCT = 10

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


def brief_items(r: Run) -> int | None:
    """The number of items the brief of `r` gives, or None where it gives none."""
    return brief_reading.items(r.messages[0].text) if r.messages else None


@dataclass(frozen=True)
class Measure:
    """The figures the budget is taken from for one run: its `label`, `start`,
    `wall`, its wall time `per_item` of its brief (None where the brief gives
    no items), whether its waits and idle are under `LOW_WAIT_PCT` of wall
    (`low_wait`), whether an operator `launched` it (False where it joins no
    group), and its `group` of `budget_group`."""
    label: str
    start: float | None
    wall: float
    per_item: float | None
    low_wait: bool
    launched: bool
    group: str | None


def measure(r: Run, undecided: list[str]) -> Measure:
    """The `Measure` of `r`. A run that joins a group and whose parent's type
    is unknown is left out of its type's budget, and an `undecided` line
    names it."""
    group = budget_group(r)
    count = brief_items(r)
    waited = r.parts[Part.WAITS] + r.parts[Part.IDLE]
    return Measure(
        label=r.label, start=r.start, wall=r.wall,
        per_item=None if count is None else r.wall / count,
        low_wait=waited * 100 < r.wall * LOW_WAIT_PCT,
        launched=group is not None and operator_launched(r, undecided),
        group=group)


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


def type_budget(kind: str, runs: list[Measure], since_date: float | None, per_item: bool,
                undecided: list[str]) -> Budget | None:
    """The budget `kind`, an agent type or a role, over `runs`, its runs, as `--help budget`
    gives it, for a run, or where `per_item`, for one item of a brief that
    gives items, or None where it gets none. `since_date` is the start of
    the window `--since` sets, where it is given."""
    rs = [(m, w) for m in runs
          if m.launched and (w := m.per_item if per_item else m.wall) is not None]
    which = (mctx("runs an operator launched whose brief gives items") if per_item
             else mctx("runs an operator launched"))
    since = since_date if since_date is not None else type_window(kind, undecided)
    window: list[tuple[Measure, float]] = []
    if since is not None:
        for m, w in rs:
            if m.start is None:
                undecided.append(mctx("{run}: its start is unknown, so it is "
                                      "left out of the window").format(run=m.label))
            elif m.start >= since:
                window.append((m, w))
    if len(window) >= MEDIAN_RUNS:
        basis = mctx("{which} since {date}").format(which=which, date=clock(since))
        chosen = window
    else:
        basis = mctx("{which}, waits and idle under {pct}% of "
                     "wall").format(which=which, pct=LOW_WAIT_PCT)
        chosen = [(m, w) for m, w in rs if m.low_wait]
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
    groups: dict[str, list[Measure]] = {}
    for m in map(lambda r: measure(r, undecided), runs):
        if m.group is not None:
            groups.setdefault(m.group, []).append(m)
    print(f"{'type or role':<18} {'budget':>7} {'runs':>4}  basis")
    for kind in sorted(groups):
        rs = groups[kind]
        b = type_budget(kind, rs, since_date, False, undecided)
        if b is not None:
            print(f"{kind:<18} {minutes(b.seconds):>7} {b.runs:>4}  {b.basis}")
        if any(m.per_item is not None for m in rs):
            b = type_budget(kind, rs, since_date, True, undecided)
            if b is not None:
                print(f"{'':<18} {minutes(b.seconds):>7} {b.runs:>4}  "
                      + mctx("per item, {basis}").format(basis=b.basis))


type GroupBudget = Callable[[str, int | None], float | None]
"""The budget in seconds of a group of `budget_group`, for a brief that
gives no items where the count is None, and otherwise for a brief that
gives that many items, or None where it gets none."""


CHUNK_RUNS = 1000
"""The most runs one child process of `group_budgets` reads."""


def chunk_measures(kind: str, agents: list[str]) -> tuple[list[Measure], list[str]]:
    """The `Measure` of each run of `agents` whose agent type is `kind`, with
    the `undecided` lines the reads appended. The records read are written
    to the store."""
    store = RunStore()
    undecided: list[str] = []
    measures = []
    for agent in agents:
        path, typed = store.last_and_type(agent)
        if typed == kind:
            measures.append(measure(store.profile(path, undecided), undecided))
    store.flush()
    return measures, undecided


def run_chunk(kind: str, agents: list[str]) -> tuple[list[Measure], list[str]]:
    """`chunk_measures`, run in a child process, so that the heap of the
    reads goes with the child. A child that exits non-zero raises with its
    standard error."""
    done = subprocess.run([sys.executable, __file__], input=json.dumps([kind, agents]),
                          capture_output=True, text=True)
    if done.returncode != 0:
        raise RuntimeError(f"the child that read {len(agents)} agents of {kind} "
                           f"exited {done.returncode}: {done.stderr}")
    measures, undecided = json.loads(done.stdout)
    return [Measure(**m) for m in measures], undecided


def group_budgets(undecided: list[str]) -> GroupBudget:
    """The `GroupBudget` over every run under the project directories. The
    agent type of each run is read through `run_store`, and the runs of a
    group's agent type are read in child processes of at most `CHUNK_RUNS`
    runs (`run_chunk`), at the first budget asked of the group."""
    store = RunStore()
    agents = agent_transcripts()
    held: dict[str, list[Measure]] = {}
    budgets: dict[tuple[str, bool], Budget | None] = {}

    def budget(group: str, items: int | None) -> float | None:
        kind = GENERAL if group in GENERAL_ROLES else group
        if kind not in held:
            of_kind = [a for a in agents if store.last_and_type(a)[1] == kind]
            store.flush()
            held[kind] = []
            for i in range(0, len(of_kind), CHUNK_RUNS):
                measures, lines = run_chunk(kind, of_kind[i:i + CHUNK_RUNS])
                held[kind].extend(measures)
                undecided.extend(lines)
        key = (group, items is not None)
        if key not in budgets:
            budgets[key] = type_budget(group, [m for m in held[kind] if m.group == group],
                                       None, items is not None, undecided)
        b = budgets[key]
        if b is None:
            return None
        return b.seconds if items is None else b.seconds * items
    return budget


def run_budget(budget: GroupBudget, r: Run) -> float | None:
    """The budget in minutes of `r`, that of its group of `budget_group` for
    the items of its brief, or None where it has none."""
    group = budget_group(r)
    seconds = budget(group, brief_items(r)) if group is not None else None
    return None if seconds is None else seconds / 60


def budget_of(role: Role, items: int | None, undecided: list[str]) -> float | None:
    """The budget in seconds of a brief of `role`, as `group_budgets` gives it."""
    return group_budgets(undecided)(role_group(role), items)


def past_budget(self_time: float | None, budget: float | None) -> bool:
    """Whether a self time in seconds is known and past a budget in minutes."""
    return self_time is not None and budget is not None and self_time > budget * 60


def of_budget(budget: float | None) -> str:
    """The text that follows a self time to give its budget in minutes."""
    return f" of budget {minutes(budget * 60)}" if budget is not None else ""


if __name__ == "__main__":
    kind, agents = json.load(sys.stdin)
    measures, lines = chunk_measures(kind, agents)
    json.dump([[asdict(m) for m in measures], lines], sys.stdout)
