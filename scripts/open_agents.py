"""The agents under a run whose work is open, as `--running` of
`profile_runs` lists them."""

from dataclasses import dataclass
from pathlib import Path

from agent_launches import Launch, launches, run_launches
from agent_reports import TURN_ENDED, Report, ReportKind, reports
from agent_turns import has_ended, is_turn_entry, last_time, turn_after
from controlled_markdown import mctx
from run_profile import Run, profile
from run_reads import is_prompt, parent_label
from transcripts import agent_id


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


def listing(parent: str, a: Launch, child: Path,
            undecided: list[str]) -> Listed | None:
    """The agent of `a`, whose transcript is at `child`, where its work is
    open: where its turn is in progress, or where it has ended and the run
    that launched it holds no report of it after the latest message it
    received from anyone, nor after its parent's latest message to it. An
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
    if reported_since(a, last_time(child, is_prompt), frozenset(ReportKind)):
        return None
    run = profile(child, undecided)
    found = parent_reports(run, undecided, a)
    if found:
        return None
    return Listed(parent, child, a, run, True, last_time(child, is_turn_entry), found)


def running_agents(path: Path, undecided: list[str]) -> list[Listed]:
    """The agents under the run at `path` whose work is open, as `listing`
    gives each, each parent's agents after it."""
    parents = run_launches(path)[1]
    out: list[Listed] = []
    for a in launches(path, undecided):
        child = a.path
        if child is None:
            continue
        if (listed := listing(parent_label(path), a, child, undecided)):
            out.append(listed)
        if agent_id(child) in parents:
            out.extend(running_agents(child, undecided))
    return out
