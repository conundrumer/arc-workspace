"""The reads of the holders of assigned tickets: their transcripts, those
whose work is open or of the session, those of them that are quiet, and
the changes the operator holds."""

from collections.abc import Mapping
from dataclasses import dataclass, replace
from pathlib import Path

from controlled_markdown import mctx
from open_agents import Listed, quiet_since, work_open
from operator_state import stuck_read
from transcript_snapshots import Refused, SUBJECT_FAULTS
from transcripts import find, is_subagent
from tree_reads import (
    fragments,
    gate_outputs,
)

from operations.changes import holds
from operations.plan import earlier_open, elsewhere
from operations.state import (
    GitRead,
    HeldRead,
    ReadOnUse,
    State,
    Ticket,
)
from operations.worktrees import worktree_in
from ticketing.vocabulary import Status


@dataclass(frozen=True)
class HoldersRead:
    """The resolved transcripts of holders of assigned tickets (`found`), those
    of them whose work is open (`State.open_holders`), and
    `State.session_holders`."""
    found: Mapping[str, Path]
    open: frozenset[str]
    session: frozenset[str]


def holders_read(tickets: Mapping[str, Ticket], session: str, main_path: Path,
                 sessions_running: frozenset[str] | None, undecided: list[str] | None = None,
                 me: str = "") -> HoldersRead:
    """`HoldersRead` of `tickets`, where `main_path` is the transcript of
    `session`. A holder that is a session is open where
    `sessions_running` gives it, and any other where its work is open.
    A holder whose transcript cannot be resolved is not open."""
    if undecided is None:
        undecided = []
    holders = {t.holder for t in tickets.values() if t.status is Status.ASSIGNED and t.holder}
    found: dict[str, Path] = {}
    for h in sorted(holders):
        try:
            found[h] = find(h)
        except Refused:
            continue
    open_paths: dict[str, Path] = {}
    for h, p in found.items():
        try:
            is_open = (h in sessions_running if sessions_running is not None
                       and not is_subagent(p) else work_open(p, undecided))
        except SUBJECT_FAULTS as exc:
            undecided.append(mctx("{run}: whether holder {holder}'s work is open is unknown "
                                  "({error}), so it counts as open").format(
                                      run=h if is_subagent(p) else me, holder=h, error=exc))
            is_open = True
        if is_open:
            open_paths[h] = p
    return HoldersRead(found, frozenset(open_paths), frozenset(
        h for h, p in open_paths.items()
        if p == main_path or p.is_relative_to(main_path.parent / session)))


def with_quiet_holders(state: State, found: Mapping[str, Path], listing: list[Listed],
                       running_work: Mapping[str, tuple[str, ...]],
                       undecided: list[str] | None = None) -> State:
    """`state` with each live holder of a ticket of `plan.elsewhere`, and
    each operator of `plan.earlier_open`, that is quiet in
    `TranscriptsRead.stuck`, where `found` gives each holder's
    transcript."""
    stuck = state.transcripts.stuck
    if undecided is None:
        undecided = []
    paths = {h: found[h] for n in elsewhere(state)
             if (h := state.tracker.tickets[n].holder) is not None and h in found}
    quiet: dict[str, float] = {}
    for h in sorted(set(paths) | set(earlier_open(state))):
        if h in stuck:
            continue
        try:
            path = paths[h] if h in paths else find(h)
            q = quiet_since(h, path, listing, state.now)
        except SUBJECT_FAULTS as exc:
            undecided.append(mctx("{run}: whether {holder} is quiet is unknown ({error}), "
                                  "so it gets no stuck entry").format(
                                      run=state.me, holder=h, error=exc))
            continue
        if q is not None:
            quiet[h] = q
    added = stuck_read(state.session, quiet, (), running_work)
    return replace(state, transcripts=replace(state.transcripts, stuck={**stuck, **added}))


def read_held(tickets: Mapping[str, Ticket], me: str, tree: GitRead) -> HeldRead:
    """The read of the worktrees of the tickets of `tickets` that `me`
    holds."""
    trees = {w for t in tickets.values() if holds(t, me)
             and (w := worktree_in(t, tree.worktrees)) is not None}
    return HeldRead(gate_outputs=ReadOnUse(sorted(trees), gate_outputs),
                    fragments=ReadOnUse(sorted(trees), fragments))
