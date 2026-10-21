"""The reads of the holders of assigned tickets: their transcripts, those
whose work is open or of the session, those of them that are quiet, and
the changes the operator holds."""

from collections.abc import Mapping
from dataclasses import dataclass, replace
from pathlib import Path

from open_agents import Listed, quiet_since, work_open
from operator_state import stuck_read
from transcript_snapshots import Refused
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
                 sessions_running: frozenset[str] | None) -> HoldersRead:
    """`HoldersRead` of `tickets`, where `main_path` is the transcript of
    `session`. A holder that is a session is open where
    `sessions_running` gives it, and any other where its work is open.
    A holder whose transcript cannot be resolved is not open."""
    holders = {t.holder for t in tickets.values() if t.status is Status.ASSIGNED and t.holder}
    found: dict[str, Path] = {}
    for h in sorted(holders):
        try:
            found[h] = find(h)
        except Refused:
            continue
    open_paths = {h: p for h, p in found.items()
                  if (h in sessions_running if sessions_running is not None
                      and not is_subagent(p) else work_open(p, []))}
    return HoldersRead(found, frozenset(open_paths), frozenset(
        h for h, p in open_paths.items()
        if p == main_path or p.is_relative_to(main_path.parent / session)))


def with_quiet_holders(state: State, found: Mapping[str, Path], listing: list[Listed],
                       running_work: Mapping[str, tuple[str, ...]]) -> State:
    """`state` with each live holder of a ticket of `plan.elsewhere`, and
    each operator of `plan.earlier_open`, that is quiet in
    `TranscriptsRead.stuck`, where `found` gives each holder's
    transcript."""
    stuck = state.transcripts.stuck
    paths = {**{h: found[h] for n in elsewhere(state)
                if (h := state.tracker.tickets[n].holder) is not None},
             **{o: find(o) for o in earlier_open(state)}}
    quiet = {h: q for h, path in paths.items()
             if h not in stuck and (q := quiet_since(h, path, listing, state.now)) is not None}
    added = stuck_read(state.session, quiet, (), running_work)
    return replace(state, transcripts=replace(state.transcripts, stuck={**stuck, **added}))


def read_held(tickets: Mapping[str, Ticket], me: str, tree: GitRead) -> HeldRead:
    """The read of the worktrees of the tickets of `tickets` that `me`
    holds."""
    trees = {w for t in tickets.values() if holds(t, me)
             and (w := worktree_in(t, tree.worktrees)) is not None}
    return HeldRead(gate_outputs=ReadOnUse(sorted(trees), gate_outputs),
                    fragments=ReadOnUse(sorted(trees), fragments))
