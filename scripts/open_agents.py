"""The agents under a run whose work is open, as `--running` of
`profile_runs` lists them."""

from dataclasses import dataclass, field
from pathlib import Path

from agent_launches import Launch, launches, notified_after, run_launches
from agent_reports import (TURN_ENDED, Report, ReportKind, parent_transcripts, reports,
                           stopped_after)
from agent_turns import has_ended, is_turn_entry, last_time, turn_after
from controlled_markdown import mctx
from run_profile import Run, Span, profile
from run_reads import is_prompt, parent_label
from transcripts import agent_id, is_subagent


@dataclass
class Listed:
    """An agent `running_agents` gives. `end` is None where its turn has
    not ended or no `user` or `assistant` entry gives a time, and `found`
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


@dataclass
class Node:
    """An agent a run launched, as `listing` reads it: `parent` is the label
    of that run and `launcher` the path of its transcript, `path` the
    agent's transcript, `under` the agents it launched, `settled` whether a
    turn-ending report of it follows its last timestamped entry, and
    `in_progress` whether, where it is not settled, its turn is in progress
    by `turn_open` with the run's last sign that it reported."""
    parent: str
    launcher: Path
    launch: Launch
    path: Path
    under: list["Node"]
    settled: bool
    in_progress: bool


def turn_open(path: Path, sign: float | None, undecided: list[str]) -> bool:
    """Whether the turn of the agent whose transcript is at `path` is in
    progress, where `sign` is a sign outside its transcript that it ended,
    or None where none is known: it has not ended, and its transcript holds
    an entry of a turn timestamped after `sign`."""
    return not has_ended(path) and (sign is None or (
        path.stat().st_mtime > sign and turn_after(path, sign, undecided)))


def node(launcher: Path, a: Launch, path: Path, under: list[Node],
         undecided: list[str]) -> Node:
    settled = reported_since(a, last_time(path), TURN_ENDED)
    return Node(parent_label(launcher), launcher, a, path, under, settled,
                not settled and turn_open(path, a.done, undecided))


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


def listing(n: Node, parent_open: bool, told: dict[str, float],
            undecided: list[str]) -> Listed | None:
    """The agent of `n` where its work is open: where its turn is in
    progress, or where it has ended, the work of its parent is open, as
    `parent_open` gives it, and the run that launched it holds no report of
    it and no notification that it stopped, as `stopped_after` gives one,
    after the latest message it received from anyone, and no report of it
    after its parent's latest message to it. A settled agent has ended its
    turn after every message it received, and only the end of its
    transcript is read. Its turn is in progress where `in_progress` holds
    and, where `told` gives its agent id a time, `turn_open` holds with that
    time. The parent's latest message comes from the agent's profile, so it
    is read only where the other reads leave the work open."""
    a, child = n.launch, n.path
    if n.settled:
        return None
    t = told.get(a.agent or "")
    if n.in_progress and (t is None or turn_open(child, t, undecided)):
        return Listed(n.parent, child, a, profile(child, undecided), False, None, None)
    if not parent_open:
        return None
    received = last_time(child, is_prompt)
    if received is not None and (
            reported_since(a, received, frozenset(ReportKind))
            or stopped_after(a.entries, received, a.agent, a.call, undecided)):
        return None
    run = profile(child, undecided)
    found = parent_reports(run, undecided, a)
    if found:
        return None
    return Listed(n.parent, child, a, run, True, last_time(child, is_turn_entry), found)


def running_agents(path: Path, undecided: list[str]) -> list[Listed]:
    """The agents under the run at `path` whose work is open, as `listing`
    gives each, each parent's agents after it, with one `notified_turns`
    over them and the runs above it."""
    up = ancestry(path, undecided)
    down = launched_under(path, undecided)
    told = notified_turns([*up, *every_node(down)])
    return listed_under(down, open_along(up, told, undecided), told, undecided)


def work_open(path: Path, undecided: list[str]) -> bool:
    """Whether the work of the run at `path` is open: where it is the main
    transcript, or where `listing` gives it from its parent's run, read up
    its parents by `ancestry`, with one `notified_turns` over them."""
    up = ancestry(path, undecided)
    return open_along(up, notified_turns(up), undecided)


def ancestry(path: Path, undecided: list[str]) -> list[Node]:
    """The run at `path`, where it is a subagent, and each run above it
    that is a subagent, each as a `Node` with no agents under it, from the
    top. Where no transcript of a run's parent gives its launch, its work is
    unknown and counts as open, the runs above it are left out, and an
    `undecided` line names it."""
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
        out.append(node(found[-1], launch, launch.path, [], undecided))
        path = found[-1]
    return out[::-1]


def open_along(up: list[Node], told: dict[str, float], undecided: list[str]) -> bool:
    """Whether the work of the last run of `up` is open, read down from the
    first, whose parent's work counts as open, or where `up` is empty,
    True."""
    is_open = True
    for n in up:
        is_open = listing(n, is_open, told, undecided) is not None
    return is_open


def launched_under(path: Path, undecided: list[str]) -> list[Node]:
    """The agents the run at `path` launched whose transcript is known, each
    as a `Node` with the agents under it."""
    parents = run_launches(path)[1]
    out: list[Node] = []
    for a in launches(path, undecided):
        child = a.path
        if child is None:
            continue
        under = launched_under(child, undecided) if agent_id(child) in parents else []
        out.append(node(path, a, child, under, undecided))
    return out


def every_node(nodes: list[Node]) -> list[Node]:
    return [m for n in nodes for m in (n, *every_node(n.under))]


def listed_under(nodes: list[Node], parent_open: bool, told: dict[str, float],
                 undecided: list[str]) -> list[Listed]:
    """`listing` of each of `nodes`, whose parent's work is open where
    `parent_open` holds, each followed by those of the agents under it. Of
    what a listed agent's run backgrounded that is still running, an agent
    under it that `listing` does not give is left out of its `running`, and
    an agent `launched_under` gives no `Node` is kept, with an `undecided`
    line: `launches` writes one where no transcript gives its launch, and
    `unreached` the others."""
    out: list[Listed] = []
    for n in nodes:
        listed = listing(n, parent_open, told, undecided)
        below = listed_under(n.under, listed is not None, told, undecided)
        if listed:
            if not n.under and listed.run.backgrounded:
                unreached(listed, undecided)
            shown = {b.launch.call for b in below}
            closed = {c.launch.call for c in n.under} - shown
            listed.running = [m for m in listed.run.backgrounded
                              if m.call not in closed]
            out.append(listed)
        out.extend(below)
    return out


def unreached(listed: Listed, undecided: list[str]) -> None:
    """Name in `undecided` each agent the run of `listed` launched in the
    background that is still running and whose transcript is known, where
    `launched_under` read no launch of that run, since no `.meta.json` of
    its sessions gives it as a parent."""
    running = {m.call for m in listed.run.backgrounded}
    for a in launches(listed.path, undecided):
        if a.call in running and a.path is not None:
            undecided.append(mctx("{run}: no `.meta.json` gives it as the parent of "
                                  "{agent}, so whether the work of {agent} is open "
                                  "is unknown, and its launch is kept under "
                                  "`running:`").format(run=listed.run.label,
                                                       agent=agent_id(a.path)))
