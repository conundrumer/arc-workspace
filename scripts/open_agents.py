"""The agents under a run whose work is open, as `--running` of
`profile_runs` lists them."""

import statistics
from dataclasses import dataclass, field
from pathlib import Path

from agent_deliveries import handed_back
from agent_launches import Launch, children_of, launch_of, launches
from agents_pending import notified_after
from agent_reports import (TURN_ENDED, Report, ReportKind, parent_transcripts, reports,
                           stopped_after)
from agent_turns import has_ended, is_turn_entry, last_time, turn_after, turn_end
from controlled_markdown import mctx
from command_labels import AGENT_TOOLS
from run_backgrounds import background_ends, backgrounds
from run_profiler import profile
from run_records import Run, Span
from run_reads import (BACKGROUND_TASK, LaunchStatus, blocks, is_prompt, parent_label,
                       run_entries, tool_calls)
from state_reads import DERIVED, mtime, state_cache
from transcripts import agent_id, is_subagent

from operations.steps import BLOCK_SECONDS


@dataclass
class Listed:
    """An agent `running_agents` gives. `end` is None where its turn has
    not ended or `agent_turns.turn_end` gives None, and `found`
    is None where its turn has not ended or `parent_reports` gives None.
    `running` is what its run backgrounded that is still running, as
    `listed_under` gives it."""
    parent: str
    path: Path
    launch: Launch
    run: Run
    ended: bool
    end: float | None
    found: list[Report] | None
    running: list[Span] = field(default_factory=list)


def usual(run: Run, runs: list[Run], call: Span) -> float:
    """The usual time of `call` of `run`, among the runs `runs`, as
    `profile_runs.py --help one` gives it."""
    def ended(among: list[Run]) -> list[float]:
        return [s.end - s.start for r in among for s in r.spans
                if s.label == call.label and s.end is not None and s.call != call.call]
    durations = ended([run]) or ended(runs)
    return statistics.median(durations) if durations else BLOCK_SECONDS


HUNG_FACTOR = 10
"""How many times a call's usual time a call in flight runs before it
counts as hung, once. A call whose usual time no run gives takes
`steps.BLOCK_SECONDS` as its usual time."""


def hung_from(start: float, usual: float) -> float:
    """The time at which a call that began at `start`, with `usual` as its
    label's usual time, counts as hung."""
    return start + HUNG_FACTOR * usual


def hung_time(run: Run, runs: list[Run], s: Span) -> float:
    """The time the call `s` of `run` counts as hung (`hung_from`)."""
    return hung_from(s.start, usual(run, runs, s))


@state_cache(DERIVED, notes="undecided")
def profiled(path: Path, undecided: list[str]) -> Run:
    """`run_profiler.profile` of the run at `path`, held."""
    return profile(path, undecided)


def reported_since(a: Launch, since: float | None,
                   kinds: frozenset[ReportKind]) -> bool:
    """Whether the run that launched `a` holds a report of it of one of
    `kinds` after `since`. The `undecided` lines of that read are dropped:
    a report it finds settles the agent whatever they name, and where it
    finds none, the agent's report is read again with them."""
    return since is not None and any(r.kind in kinds for r in a.reports(since, []))


def parent_reports(r: Run, undecided: list[str],
                   launch: Launch | None = None) -> list[Report] | None:
    """The reports of the subagent of `r` that reached its parent after the
    parent's latest message to it, as `profile_runs.py --help one` gives them, or None where that
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


@dataclass
class Node:
    """An agent a run launched, as `listing` reads it: `parent` is the label
    of that run and `launcher` the path of its transcript, `path` the
    agent's transcript, `under` the agents it launched, or None where
    `nodes_under` has not read them, `settled` whether a turn-ending report
    of it follows its last timestamped entry, and `in_progress` whether,
    where it is not settled, its turn is in progress by `turn_open` with
    the run's last sign that it reported, and once `settle_turns` has read
    it, with the latest notification of it as well. `own` is what
    `own_work` gives and `busy` what `is_busy` gives, each None where it
    has not been read."""
    parent: str
    launcher: Path
    launch: Launch
    path: Path
    under: list["Node"] | None
    settled: bool
    in_progress: bool
    own: list[str] | None = None
    busy: bool | None = None


def turn_open(path: Path, sign: float | None, undecided: list[str]) -> bool:
    """Whether the turn of the agent whose transcript is at `path` is in
    progress, where `sign` is a sign outside its transcript that it ended,
    or None where none is known: it has not ended, and its transcript holds
    an entry of a turn timestamped after `sign`."""
    return not has_ended(path) and (sign is None or (
        mtime(path) > sign and turn_after(path, sign, undecided)))


def node(launcher: Path, a: Launch, path: Path, under: list[Node] | None,
         undecided: list[str]) -> Node:
    settled = launch_settled(launcher, a.call, path)
    return Node(parent_label(launcher), launcher, a, path, under, settled,
                not settled and turn_open(path, a.done, undecided))


@state_cache(DERIVED)
def launch_settled(launcher: Path, call: str, path: Path) -> bool:
    """`Node.settled` of the agent whose transcript is at `path`, launched
    by the Agent call `call` of the run at `launcher`."""
    return reported_since(launch_of(launcher, call), last_time(path), TURN_ENDED)


def notified_turns(nodes: list[Node]) -> dict[str, float]:
    """`notified_after` of the agents of `nodes` whose turn is in progress,
    from the earliest of their last turn entries, or where an agent's
    transcript holds no timestamped one, from its launch."""
    left = [n for n in nodes if n.in_progress and n.launch.agent]
    if not left:
        return {}
    starts = [last_time(n.path, is_turn_entry) for n in left]
    return notified_after([(n.launcher, n.launch) for n in left],
                          min(n.launch.since if t is None else t
                              for n, t in zip(left, starts)))


def settle_turns(nodes: list[Node], undecided: list[str]) -> None:
    told = notified_turns(nodes)
    for n in nodes:
        t = told.get(n.launch.agent or "")
        if n.in_progress and t is not None:
            n.in_progress = turn_open(n.path, t, undecided)


def listing(n: Node, parent_open: bool, undecided: list[str]) -> Listed | None:
    """The agent of `n` where its work is open, by the rule
    `profile_runs.py --help running` gives, with the work of its parent open
    where `parent_open` holds: by `by_rule`, or where that gives it as not
    open, by `unknown_work`."""
    return by_rule(n, parent_open, undecided) or unknown_work(n, undecided)


def by_rule(n: Node, parent_open: bool, undecided: list[str]) -> Listed | None:
    """`listing` but for the case of `unknown_work`. A settled agent has
    ended its turn after every message it received, and only the end of its
    transcript is read. The parent's latest message comes from the agent's
    profile, so it is read only where the other reads leave the work
    open."""
    a, child = n.launch, n.path
    if n.settled:
        return None
    if n.in_progress:
        return Listed(n.parent, child, a, profiled(child, undecided), False, None, None)
    if not parent_open:
        return None
    received = last_time(child, is_prompt)
    if received is not None and (
            reported_since(a, received, frozenset(ReportKind))
            or stopped_after(a.entries, received, a.agent, a.call, undecided)):
        return None
    if handed_back(child):
        return None
    listed = turn_ended(n, undecided)
    return None if listed.found else listed


def unknown_work(n: Node, undecided: list[str]) -> Listed | None:
    """The agent of `n` where its turn has ended and work of its own still
    runs, as `profile_runs.py --help running` gives that
    work, with the `undecided` line that names it with that work: the
    agents under it that `is_busy` gives, and `own_work`."""
    below = [agent_id(m.path) for m in every_node(nodes_under(n, undecided), undecided)
             if is_busy(m, undecided)]
    own = own_work(n, undecided)
    if not below and not own:
        return None
    undecided.append(mctx("{run}: its turn has ended while work of its own still "
                          "runs: {work}; whether its work is open is unknown, and "
                          "it counts as open").format(
        run=agent_id(n.path), work=", ".join([*below, *own])))
    return turn_ended(n, undecided)


def turn_ended(n: Node, undecided: list[str]) -> Listed:
    """The agent of `n` as listed where its turn has ended."""
    run = profiled(n.path, undecided)
    return Listed(n.parent, n.path, n.launch, run, True,
                  turn_end(run_entries(n.path)), parent_reports(run, undecided, n.launch))


def is_busy(n: Node, undecided: list[str]) -> bool:
    """Whether the agent of `n` is work of its own of each run above it, as
    `profile_runs.py --help running` gives that work."""
    if n.busy is None:
        n.busy = (n.in_progress or bool(own_work(n, undecided))
                  or any(is_busy(m, undecided) for m in nodes_under(n, undecided)))
    return n.busy


def own_work(n: Node, undecided: list[str]) -> list[str]:
    """The work of its own of the run of `n`, as
    `profile_runs.py --help running` gives it, other than an agent `nodes_under`
    gives."""
    if n.own is None:
        n.own = []
        reached = {m.launch.call for m in nodes_under(n, undecided)}
        if may_still_run(n.path, reached, undecided):
            agents = {a.call: a.agent for a in launches(n.path, undecided)}
            n.own = [agents.get(m.call) or f"`{m.label}`"
                     for m in profiled(n.path, undecided).backgrounded
                     if m.call not in reached]
    return n.own


def may_still_run(path: Path, reached: set[str], undecided: list[str]) -> bool:
    """Whether a call the run at `path` backgrounded, other than a call of
    `reached`, may still run. Only the lines that name such a call or its
    ids are read, which spares `profile` the whole run where none still
    runs."""
    results = run_entries(path, {BACKGROUND_TASK, LaunchStatus.ASYNC_LAUNCHED.value})
    calls = {str(b["tool_use_id"]) for e in results for b in blocks(e, "tool_result")
             if b.get("tool_use_id")} - reached
    if not calls:
        return False
    found = {c: b for c, b in backgrounds(results, tool_calls(run_entries(path, calls), AGENT_TOOLS),
                                          undecided).items() if c in calls}
    if not found:
        return False
    ids = set().union(*(b.ids for b in found.values()))
    return None in background_ends(found, run_entries(path, ids)).values()


@state_cache(DERIVED, notes="undecided")
def running_agents(path: Path, undecided: list[str]) -> list[Listed]:
    """The agents under the run at `path` whose work is open, as `listing`
    gives each, each parent's agents after it, with one `settle_turns`
    over them and the runs above it."""
    up = ancestry(path, undecided)
    down = launched_under(path, undecided)
    if up:
        up[-1].under = down
    settle_turns([*up, *every_node(down, undecided)], undecided)
    return listed_under(down, open_along(up, undecided), undecided)


@state_cache(DERIVED, notes="undecided")
def work_open(path: Path, undecided: list[str]) -> bool:
    """Whether the work of the run at `path` is open: where it is the main
    transcript, or where `listing` gives it from its parent's run, read up
    its parents by `ancestry`, with one `settle_turns` over them."""
    up = ancestry(path, undecided)
    settle_turns(up, undecided)
    return open_along(up, undecided)


def ancestry(path: Path, undecided: list[str]) -> list[Node]:
    """The run at `path`, where it is a subagent, and each run above it
    that is a subagent, each as a `Node` whose agents under it are not read,
    from the top. Where no transcript of a run's parent gives its launch,
    its work is unknown and counts as open, the runs above it are left out,
    and an `undecided` line names it."""
    out: list[Node] = []
    while is_subagent(path):
        aid = agent_id(path)
        found = parent_transcripts(path)
        launch = next((a for a in launches(found[-1], undecided) if a.agent == aid),
                      None) if found else None
        if launch is None or launch.path is None:
            undecided.append(mctx("{run}: no transcript of its parent gives its launch, "
                                  "so whether its work is open is unknown, and each "
                                  "agent it launched whose turn has ended is listed as "
                                  "under a parent whose work is open").format(run=aid))
            break
        out.append(node(found[-1], launch, launch.path, None, undecided))
        path = found[-1]
    return out[::-1]


def open_along(up: list[Node], undecided: list[str]) -> bool:
    """Whether the work of the last run of `up` is open, read down from the
    first, whose parent's work counts as open, or where `up` is empty,
    True."""
    is_open = True
    for n in up:
        is_open = listing(n, is_open, undecided) is not None
    return is_open


def launched_under(path: Path, undecided: list[str]) -> list[Node]:
    """The agents the run at `path` launched whose transcript is known, each
    as a `Node` with the agents under it."""
    out: list[Node] = []
    for a in launches(path, undecided):
        child = a.path
        if child is None:
            continue
        under = launched_under(child, undecided) if children_of(path, agent_id(child)) else []
        out.append(node(path, a, child, under, undecided))
    return out


def nodes_under(n: Node, undecided: list[str]) -> list[Node]:
    if n.under is None:
        n.under = launched_under(n.path, undecided)
        settle_turns(every_node(n.under, undecided), undecided)
    return n.under


def every_node(nodes: list[Node], undecided: list[str]) -> list[Node]:
    return [m for n in nodes
            for m in (n, *every_node(nodes_under(n, undecided), undecided))]


def listed_under(nodes: list[Node], parent_open: bool,
                 undecided: list[str]) -> list[Listed]:
    """`listing` of each of `nodes`, whose parent's work is open where
    `parent_open` holds, each followed by those of the agents under it,
    with each listed agent's `running` as
    `profile_runs.py --help running` gives it. Of the `undecided` lines that rule
    asks for, `launches` writes the one of an agent whose launch no
    transcript gives, and `unreached` the others."""
    out: list[Listed] = []
    for n in nodes:
        under = nodes_under(n, undecided)
        listed = listing(n, parent_open, undecided)
        below = listed_under(under, listed is not None, undecided)
        if listed:
            if not under and listed.run.backgrounded:
                unreached(listed, undecided)
            shown = {b.launch.call for b in below}
            closed = {c.launch.call for c in under} - shown
            listed.running = [m for m in listed.run.backgrounded
                              if m.call not in closed]
            out.append(listed)
        out.extend(below)
    return out


def unreached(listed: Listed, undecided: list[str]) -> None:
    """The `undecided` line of each agent the run of `listed` launched
    whose transcript is known, where `launched_under` read no launch of that
    run, as `profile_runs.py --help running` gives it."""
    running = {m.call for m in listed.run.backgrounded}
    for a in launches(listed.path, undecided):
        if a.call in running and a.path is not None:
            undecided.append(mctx("{run}: no `.meta.json` gives it as the parent of "
                                  "{agent}, so whether the work of {agent} is open "
                                  "is unknown, and its launch is kept under "
                                  "`running:`").format(run=listed.run.label,
                                                       agent=agent_id(a.path)))
