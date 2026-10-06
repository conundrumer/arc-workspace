"""The agents under a run whose work is open, as `--running` of
`profile_runs` lists them."""

from dataclasses import dataclass
from pathlib import Path

from agent_launches import Launch, launches, run_launches
from agent_reports import (TURN_ENDED, Report, ReportKind, parent_transcripts, reports,
                           stopped_after)
from agent_turns import has_ended, is_turn_entry, last_time, turn_after
from controlled_markdown import mctx
from run_profile import Run, profile
from run_reads import is_prompt, parent_label
from transcripts import agent_id, is_subagent


@dataclass
class Listed:
    """An agent `running_agents` gives. `end` is None where its turn has
    not ended or no `user` or `assistant` entry gives a time, and `found`
    is None where its turn has not ended or `parent_reports` gives None."""
    parent: str
    path: Path
    launch: Launch
    run: Run
    ended: bool
    end: float | None
    found: list[Report] | None


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


def listing(parent: str, a: Launch, child: Path, parent_open: bool,
            undecided: list[str]) -> Listed | None:
    """The agent of `a`, whose transcript is at `child`, where its work is
    open: where its turn is in progress, or where it has ended, the work of
    its parent is open, as `parent_open` gives it, and the run that launched
    it holds no report of it and no notification that it stopped, as
    `stopped_after` gives one, after the latest message it received from
    anyone, and no report of it after its parent's latest message to it. An
    agent with a turn-ending report after its last timestamped entry has
    ended its turn after every message it received, and only the end of its
    transcript is read. The parent's latest message comes from the agent's
    profile, so it is read only where the other reads leave the work
    open."""
    if reported_since(a, last_time(child), TURN_ENDED):
        return None
    if not has_ended(child) and (
            a.done is None or (child.stat().st_mtime > a.done
                               and turn_after(child, a.done, undecided))):
        return Listed(parent, child, a, profile(child, undecided), False, None, None)
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
    return Listed(parent, child, a, run, True, last_time(child, is_turn_entry), found)


def running_agents(path: Path, undecided: list[str]) -> list[Listed]:
    """The agents under the run at `path` whose work is open, as `listing`
    gives each, each parent's agents after it."""
    return agents_under(path, work_open(path, undecided), undecided)


def work_open(path: Path, undecided: list[str]) -> bool:
    """Whether the work of the run at `path` is open: where it is the main
    transcript, or where `listing` gives it from its parent's run, read up
    its parents. Where no transcript of its parent gives its launch, it is
    unknown and counts as open, and an `undecided` line names it."""
    if not is_subagent(path):
        return True
    aid = agent_id(path)
    found = parent_transcripts(path)
    launch = next((a for a in launches(found[-1], undecided) if a.agent == aid),
                  None) if found else None
    if launch is None or launch.path is None:
        undecided.append(mctx("{run}: no transcript of its parent gives its launch, "
                              "so whether its work is open is unknown, and each "
                              "agent it launched whose turn has ended is listed as "
                              "under a parent whose work is open").format(run=aid))
        return True
    return listing(parent_label(found[-1]), launch, launch.path,
                   work_open(found[-1], undecided), undecided) is not None


def agents_under(path: Path, parent_open: bool, undecided: list[str]) -> list[Listed]:
    """`running_agents` of the run at `path`, whose work is open where
    `parent_open` holds."""
    parents = run_launches(path)[1]
    out: list[Listed] = []
    for a in launches(path, undecided):
        child = a.path
        if child is None:
            continue
        listed = listing(parent_label(path), a, child, parent_open, undecided)
        if listed:
            out.append(listed)
        if agent_id(child) in parents:
            out.extend(agents_under(child, listed is not None, undecided))
    return out
