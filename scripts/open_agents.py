"""The agents under a run whose work is open, as `--running` of
`profile_runs` lists them."""

from bisect import bisect_left
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass, field
from pathlib import Path

from agent_deliveries import handback_accepted
from agent_launches import Launch, children_of, launch_of, launches
from agents_pending import notified_after
from agent_reports import (TURN_ENDED, Report, ReportKind, parent_transcripts, reports,
                           stopped_after)
from agent_turns import has_ended, is_turn_entry, last_time, turn_after, turn_end
from controlled_markdown import mctx
from run_backgrounds import may_still_run
from run_profiler import profile
from senders import is_interrupt_note
from run_records import Run, Span
from run_reads import is_prompt, parent_label
from file_reads import mtime
from state_reads import DERIVED, Kept, state_cache
from entry_reads import entries_back
from transcript_snapshots import Entry, SUBJECT_FAULTS
from transcripts import agent_id, chain, is_subagent

from operations.constants import BLOCK_SECONDS, stuck_reached


@dataclass
class Listed:
    """An agent `running_agents` gives. `end` is None where its turn has
    not ended or `agent_turns.turn_end` gives None, and `found`
    is None where its turn has not ended or `received_reports` gives None.
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


def turn_ended_idle(listing: list[Listed]) -> frozenset[str]:
    """The agents whose turns ended with no running commands or children."""
    parents = {x.parent for x in listing}
    return frozenset(aid for x in listing
                     if (aid := x.launch.agent) is not None and x.ended and not x.running
                     and aid not in parents)


type CallTimes = dict[str, list[float]]
"""The durations of the ended calls of some runs by label, each list
sorted."""


def call_times(runs: Iterable[Run]) -> CallTimes:
    times: CallTimes = {}
    for r in runs:
        for s in r.spans:
            if s.end is not None:
                times.setdefault(s.label, []).append(s.end - s.start)
    for durations in times.values():
        durations.sort()
    return times


def median_without(times: CallTimes, call: Span) -> float | None:
    """The median of the durations `times` gives the label of `call`, with
    the duration of `call` itself left out, or None where none is left."""
    durations = times.get(call.label, [])
    n = len(durations)
    if call.end is None:
        skip = n
    else:
        skip = bisect_left(durations, call.end - call.start)
        n -= 1
    if n == 0:
        return None

    def at(i: int) -> float:
        return durations[i if i < skip else i + 1]
    return at(n // 2) if n % 2 else (at(n // 2 - 1) + at(n // 2)) / 2


def usual(own: CallTimes, among: CallTimes, call: Span) -> float:
    """The usual time of `call`, with `own` the `call_times` of its run and
    `among` those of the runs profiled, as `profile_runs.py --help one`
    gives it."""
    found = median_without(own, call)
    if found is None:
        found = median_without(among, call)
    return BLOCK_SECONDS if found is None else found


HUNG_FACTOR = 10
"""How many times a call's usual time a call in flight runs before it
counts as hung, once. A call whose usual time no run gives takes
`constants.BLOCK_SECONDS` as its usual time."""


def hung_from(start: float, usual: float) -> float:
    """The time at which a call that began at `start`, with `usual` as its
    label's usual time, counts as hung."""
    return start + HUNG_FACTOR * usual


def hung_time(own: CallTimes, among: CallTimes, s: Span) -> float:
    """The time the call `s` counts as hung (`hung_from`), with `own` and
    `among` as `usual` takes them."""
    return hung_from(s.start, usual(own, among, s))


@state_cache(DERIVED, notes="undecided")
def profiled(path: Path, undecided: list[str]) -> Run:
    """`run_profiler.profile` of the run at `path`, held."""
    return profile(path, undecided)


def reported_since(a: Launch, since: float | None,
                   kinds: frozenset[ReportKind]) -> bool:
    """Whether the sessions of `a` hold a report of it of one of
    `kinds` after `since`. The `undecided` lines of that read are dropped:
    a report it finds settles the agent whatever they name, and where it
    finds none, the agent's report is read again with them."""
    return since is not None and any(r.kind in kinds for r in a.reports(since, []))


def received_reports(r: Run, undecided: list[str],
                     launch: Launch | None = None) -> list[Report] | None:
    """The received reports of `r`, as `profile_runs.py --help one` gives
    them, or None where the parent's latest message is unknown.
    `launch`, where given, is the launch of `r`."""
    if r.unknown or not r.messages:
        undecided.append(mctx("{run}: the latest message from its parent is "
                              "unknown, so whether a report was received "
                              "after it is unknown").format(run=r.label))
        return None
    since = r.messages[-1].time
    return (launch.reports(since, undecided) if launch
            else reports(r.path, since, undecided))


@dataclass(frozen=True)
class Launched:
    """An agent a run launched, as `held_under` holds it: `parent` is the
    label of that run and `launcher` the path of its transcript, `path` the
    agent's transcript, `under` the agents it launched, or None where they
    are not read, `settled` whether a turn-ending report of it follows its
    last timestamped entry, and `in_progress` whether, where it is not
    settled, its turn is in progress by `turn_open` with the run's last
    sign that it reported."""
    parent: str
    launcher: Path
    launch: Launch
    path: Path
    under: tuple["Launched", ...] | None
    settled: bool
    in_progress: bool
    fault: str | None = None


@dataclass
class Node:
    """An agent a run launched, as one read of `listing` reads it: what
    `found` gives, with `under` the agents it launched, or None where
    `nodes_under` has not read them, and `in_progress` as `found` gives it
    until `settle_turns` reads it, and from then on with the latest
    notification of it as well. `own` is what `own_work` gives and `busy`
    what `is_busy` gives, each None where it has not been read. `cut` is
    the end of its launcher's turn, where `cut_off` found its call cut off
    with that turn."""
    found: Launched
    under: list["Node"] | None
    in_progress: bool
    own: list[str] | None = None
    busy: bool | None = None
    fault: str | None = None
    cut: float | None = None

    @property
    def parent(self) -> str:
        return self.found.parent

    @property
    def launcher(self) -> Path:
        return self.found.launcher

    @property
    def launch(self) -> Launch:
        return self.found.launch

    @property
    def path(self) -> Path:
        return self.found.path

    @property
    def settled(self) -> bool:
        return self.found.settled


def walked(found: Launched) -> Node:
    """The `Node` of `found`, and of each agent under it that it gives, for
    one read of `listing`."""
    return Node(found, None if found.under is None else [walked(f) for f in found.under],
                found.in_progress, fault=found.fault)


def turn_open(path: Path, sign: float | None, undecided: list[str]) -> bool:
    """Whether the turn of the agent whose transcript is at `path` is in
    progress, where `sign` is a sign outside its transcript that it ended,
    or None where none is known: it has not ended, and its transcript holds
    an entry of a turn timestamped after `sign`."""
    return not has_ended(path) and (sign is None or (
        mtime(path) > sign and turn_after(path, sign, undecided)))


def launched(launcher: Path, a: Launch, path: Path, under: tuple[Launched, ...] | None,
             undecided: list[str]) -> Launched:
    settled = launch_settled(launcher, a.call, path)
    return Launched(parent_label(launcher), launcher, a, path, under, settled,
                    not settled and turn_open(path, a.done, undecided))


@state_cache(DERIVED, kept=Kept.DISK)
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
    starts: list[float | None] = []
    readable: list[Node] = []
    for n in left:
        if n.fault is not None:
            continue
        try:
            start = last_time(n.path, is_turn_entry)
        except SUBJECT_FAULTS as exc:
            n.fault = str(exc)
            continue
        readable.append(n)
        starts.append(start)
    left = readable
    if not left:
        return {}
    return notified_after([(n.launcher, n.launch) for n in left],
                          min(n.launch.since if t is None else t
                              for n, t in zip(left, starts)))


def settle_turns(nodes: list[Node], undecided: list[str]) -> None:
    told = notified_turns(nodes)
    for n in nodes:
        if n.fault is not None:
            continue
        notes: list[str] = []
        try:
            t = told.get(n.launch.agent or "")
            if n.in_progress and t is not None:
                n.in_progress = turn_open(n.path, t, notes)
        except SUBJECT_FAULTS as exc:
            n.fault = str(exc)
        else:
            undecided.extend(notes)


def turn_ended_at(n: Node) -> float | None:
    """The end of the turn of `n`, whose turn is not in progress, as
    `profile_runs.py --help running` gives it."""
    if n.cut is not None:
        return n.cut
    ids = {n.launch.call}
    if n.launch.agent is not None:
        ids.add(n.launch.agent)
    notified = (e.time for e in n.launch.entries if e.time > n.launch.since
                and any(who in ids for who, _ in e.signs))
    return max((t for t in (last_time(n.path), n.launch.done, *notified) if t is not None),
               default=None)


def cut_off(pairs: Iterable[tuple[Node, Node]], undecided: list[str]) -> None:
    """Apply the parent turn cutoff of `profile_runs.py --help running`
    to each launcher and agent of `pairs`, each launcher before the agents
    under it. Each agent keeps the end of its launcher's turn as `cut`."""
    for up, n in pairs:
        if (up.fault is not None or n.fault is not None or up.in_progress
                or not n.in_progress or n.launch.answered):
            continue
        notes: list[str] = []
        try:
            n.cut = turn_ended_at(up)
            n.in_progress = turn_open(n.path, n.cut, notes)
        except SUBJECT_FAULTS as exc:
            n.fault = str(exc)
        else:
            undecided.extend(notes)


def descents(nodes: list[Node]) -> Iterator[tuple[Node, Node]]:
    """Each launcher and agent under `nodes` at any depth that has been
    read, each launcher before the agents under it."""
    for n in nodes:
        for m in n.under or []:
            yield n, m
        yield from descents(n.under or [])


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
    received = last_time(child, is_received)
    if any(closes(n, received, undecided) for closes in CLOSING_SIGNS):
        return None
    listed = turn_ended(n, undecided)
    return None if listed.found else listed


def is_received(entry: Entry) -> bool:
    """Whether an entry is a message the agent received, as
    `profile_runs.py --help running` gives one."""
    return is_prompt(entry) and not is_interrupt_note(entry)


def reported_after(n: Node, received: float | None, undecided: list[str]) -> bool:
    return reported_since(n.launch, received, frozenset(ReportKind))


def stopped(n: Node, received: float | None, undecided: list[str]) -> bool:
    return received is not None and stopped_after(n.launch.entries, received, undecided)


def interrupted(n: Node, received: float | None, undecided: list[str]) -> bool:
    return received is not None and (stop := last_time(n.path, is_interrupt_note)) is not None \
        and stop > received


def handed_back(n: Node, received: float | None, undecided: list[str]) -> bool:
    """Whether the run of `n` holds, after the latest message it received,
    a result of `handback_accepted`."""
    for p in reversed(chain(n.path)):
        for e in entries_back(p):
            if is_received(e):
                return False
            r = e.get("toolUseResult")
            if e.get("type") == "user" and isinstance(r, dict) and handback_accepted(r):
                return True
    return False


type ClosingSign = Callable[[Node, float | None, list[str]], bool]
"""A condition on an agent and the time of the latest message it received,
None where it received none, under which its work closed after that
message."""

CLOSING_SIGNS: tuple[ClosingSign, ...] = (reported_after, stopped, interrupted, handed_back)


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
                  turn_end(n.path), received_reports(run, undecided, n.launch))


def is_busy(n: Node, undecided: list[str]) -> bool:
    """Whether the agent of `n` is work of its own of each run above it, as
    `profile_runs.py --help running` gives that work."""
    if n.fault is not None:
        return True
    if n.busy is None:
        n.busy = n.in_progress or bool(own_work(n, undecided))
        if not n.busy:
            for child in nodes_under(n, undecided):
                try:
                    busy = is_busy(child, undecided)
                except SUBJECT_FAULTS as exc:
                    child.fault = str(exc)
                    busy = True
                if busy:
                    n.busy = True
                    break
    return n.busy


def own_work(n: Node, undecided: list[str]) -> list[str]:
    """The work of its own of the run of `n`, as
    `profile_runs.py --help running` gives it, other than an agent `nodes_under`
    gives."""
    if n.own is None:
        n.own = []
        reached = {m.launch.call for m in nodes_under(n, undecided)}
        if may_still_run(n.path, frozenset(reached), undecided):
            agents = {a.call: a.agent for a in launches(n.path, undecided)}
            n.own = [agents.get(m.call) or f"`{m.label}`"
                     for m in profiled(n.path, undecided).backgrounded
                     if m.call not in reached]
    return n.own


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
    cut_off([*zip(up, up[1:]), *descents(up[-1:] if up else down)], undecided)
    return listed_under(down, open_along(up, undecided), undecided)


def quiet_since(agent: str, path: Path, listing: list[Listed], now: float) -> float | None:
    """The time of the latest timestamped entry of the transcript at `path`,
    the run of `agent`, and of the transcript of each agent under it in
    `listing`, at any depth by `Listed.parent`, where the stretch from that
    entry to `now` has reached `STUCK_SECONDS` (`stuck_reached`), and None
    otherwise, or where no such transcript gives a time."""
    reached = {agent}
    while added := {aid for x in listing if x.parent in reached
                    and (aid := x.launch.agent) is not None and aid not in reached}:
        reached |= added
    paths = [path, *(x.path for x in listing if x.launch.agent in reached - {agent})]
    latest = max((t for p in paths if (t := last_time(p)) is not None), default=None)
    return latest if latest is not None and stuck_reached(latest, now) else None


@state_cache(DERIVED, notes="undecided")
def work_open(path: Path, undecided: list[str]) -> bool:
    """Whether the work of the run at `path` is open: where it is the main
    transcript, or where `listing` gives it from its parent's run, read up
    its parents by `ancestry`, with one `settle_turns` over them."""
    up = ancestry(path, undecided)
    settle_turns(up, undecided)
    cut_off(zip(up, up[1:]), undecided)
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
        try:
            node = launched(found[-1], launch, launch.path, None, undecided)
        except SUBJECT_FAULTS as exc:
            node = Launched(parent_label(found[-1]), found[-1], launch, launch.path,
                            None, False, True, str(exc))
        out.append(walked(node))
        path = found[-1]
    return out[::-1]


def open_along(up: list[Node], undecided: list[str]) -> bool:
    """Whether the work of the last run of `up` is open, read down from the
    first, whose parent's work counts as open, or where `up` is empty,
    True."""
    is_open = True
    for n in up:
        try:
            if n.fault is None:
                is_open = listing(n, is_open, undecided) is not None
        except SUBJECT_FAULTS as exc:
            n.fault = str(exc)
        if n.fault is not None:
            undecided.append(mctx("{run}: whether its work is open is unknown ({fault}), "
                                  "so it counts as open").format(
                                      run=n.launch.agent, fault=n.fault))
            is_open = True
    return is_open


def launched_under(path: Path, undecided: list[str]) -> list[Node]:
    """The agents the run at `path` launched whose transcript is known, each
    as a `Node` with the agents under it, from `held_under`."""
    return [walked(f) for f in held_under(path, undecided)]


@state_cache(DERIVED, notes="undecided")
def held_under(path: Path, undecided: list[str]) -> tuple[Launched, ...]:
    """The agents the run at `path` launched whose transcript is known, each
    with the agents under it, held, so that a change of one run reads again
    only the runs above it."""
    out: list[Launched] = []
    for a in launches(path, undecided):
        child = a.path
        if child is None:
            continue
        try:
            under = held_under(child, undecided) if children_of(path, agent_id(child)) else ()
            node = launched(path, a, child, under, undecided)
        except SUBJECT_FAULTS as exc:
            node = Launched(parent_label(path), path, a, child, (), False, True, str(exc))
        out.append(node)
    return tuple(out)


def nodes_under(n: Node, undecided: list[str]) -> list[Node]:
    if n.fault is not None:
        return []
    if n.under is None:
        n.under = launched_under(n.path, undecided)
        settle_turns(every_node(n.under, undecided), undecided)
        cut_off(descents([n]), undecided)
    return n.under


def every_node(nodes: list[Node], undecided: list[str]) -> list[Node]:
    out: list[Node] = []
    for n in nodes:
        out.append(n)
        try:
            under = nodes_under(n, undecided)
        except SUBJECT_FAULTS as exc:
            n.fault = str(exc)
            continue
        out.extend(every_node(under, undecided))
    return out


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
        start = len(undecided)
        listed = None
        try:
            under = nodes_under(n, undecided)
            if n.fault is None:
                listed = listing(n, parent_open, undecided)
                if listed and not under and listed.run.backgrounded:
                    unreached(listed, undecided)
        except SUBJECT_FAULTS as exc:
            n.fault = str(exc)
        if n.fault is not None:
            del undecided[start:]
            undecided.append(mctx("{run}: its run cannot be read ({fault}), "
                                  "so it is left out of the running agents").format(
                                      run=n.launch.agent, fault=n.fault))
            continue
        below = listed_under(under, listed is not None, undecided)
        if listed:
            shown = {b.launch.call for b in below}
            closed = {c.launch.call for c in under if c.fault is None} - shown
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
