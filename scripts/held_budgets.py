"""The spend and the budgets of the changes an operator holds, and of the
change it takes next, as `operations.state.Computed` gives them."""

from pathlib import Path

from spends import budget, spend
from transcript_snapshots import SUBJECT_FAULTS
from controlled_markdown import mctx

from operations import change_agents, change_fragments, change_take, changes
from operations.roles import Role, launched_type
from operations.state import Budget, Spend, State
from operations.worktrees import worktree


def change_spend(state: State, undecided: list[str]) -> dict[str, Spend]:
    """The spend of each change `state.me` holds whose spend reads, that of
    the agents of `change_agents.elsewhere_on` included, each pending one
    read as still running."""
    out: dict[str, Spend] = {}
    for t in changes.held(state):
        agents = {a.agent_id: a for a in (*change_agents.of_change(state, t),
                                          *change_agents.elsewhere_on(state, t.number))
                  if a.agent_id is not None}
        pending = {i: launched_type(a.role, a.subject) for i, a in agents.items() if a.pending}
        try:
            s = spend(list(agents), pending, undecided)
        except SUBJECT_FAULTS as exc:
            undecided.append(mctx("{run}: the spend of change {change} is unknown ({error}), "
                                  "so no budget overrun acts on it").format(
                                      run=state.me, change=t.number, error=exc))
            continue
        if s is not None:
            out[t.number] = s
    return out


def change_budgets(state: State, tickets: Path, undecided: list[str]) -> dict[str, Budget]:
    """The budgets of the ready changes not held by `change_take.ready_hold`.
    Admission's run takes and pace must already be computed. Filter before
    reading history, without ranking, which needs these budgets itself.
    """
    known: dict[frozenset[Role], Budget | None] = {}
    out: dict[str, Budget] = {}
    held = change_take.ready_hold(state)
    for t in change_take.ready(state):
        if t.editors is None or held(t) is not None:
            continue
        key = frozenset(t.editors)
        if key not in known:
            known[key] = budget(tickets, key, state.now, undecided, state.me)
        if (b := known[key]) is not None:
            out[t.number] = b
    return out


def doc_budgets(state: State, tickets: Path, undecided: list[str]) -> dict[str, Budget]:
    """The budgets `Computed.doc_budgets` gives, read for each held change
    where `change_fragments.fragments_due` holds."""
    out: dict[str, Budget] = {}
    for t in changes.held(state):
        w = worktree(t, state)
        if w is None or not change_fragments.fragments_due(
                change_agents.editors_in(change_agents.of_change(state, t), w)):
            continue
        editors = change_fragments.lacking_doc_editor(t, w, state)
        if editors is None:
            continue
        b = budget(tickets, frozenset({*editors, Role.DOC_EDITOR}), state.now, undecided, state.me)
        if b is not None:
            out[t.number] = b
    return out
