"""The doc editor of a change's `mctx` fragments.

Once a code editor or a `handbook-expanded` editor of a change has
reported, where the change adds or changes the text of an `mctx` fragment
(`HeldRead.fragments`) and no doc editor of the change was launched with
fragments, those fragments go to a doc editor launched for them: a change
whose `editors` field gives no doc editor first gets one in that field,
with the budget of its new `editors` set, and the doc editor the field
then gives is launched with the fragments; a change that gives one gets a
doc editor of the fragments alone (`briefs.FRAGMENTS_PART`), which is the
latest editor of its part beside the doc editor of the documents.

A change gets at most one such launch. Fragment text its drafters write
after that launch is the doc reviewer's to judge, in the review round that
follows their report."""

from pathlib import Path

from controlled_markdown import mctx
from operations import briefs
from operations.change_agents import latest_editors
from operations.filing import editor_scratch
from operations.roles import Role
from operations.state import Agent, State, Ticket
from operations.steps import Bash, Launch, Step, Undecided, agent_ids
from operations.log_commands import add_editor

DRAFTERS = (Role.CODE_EDITOR, Role.HANDBOOK_EXPANDED)
"""The editors that draft the text of the fragments their code needs."""


def drafter_ids(here: list[Agent]) -> list[str] | Undecided:
    """The agent ids of the latest drafters of `here`, which the brief of a
    doc editor gives for the code changes a move of a fragment's text
    needs."""
    return agent_ids([a for a in latest_editors(here) if a.role in DRAFTERS])


def lacking_doc_editor(t: Ticket, w: Path | None,
                       state: State) -> tuple[Role, ...] | None:
    """The `editors` field of the held change `t`, where it gives no doc
    editor while the `fragments` of `t`'s worktree `w` are not empty, and
    otherwise None."""
    if (t.editors is None or Role.DOC_EDITOR in t.editors or w is None
            or not state.held.fragments.get(w)):
        return None
    return t.editors


def drafter_reports(here: list[Agent]) -> list[float]:
    """The times of the latest reports of the drafters of `here`."""
    return [r.time for a in here if a.role in DRAFTERS and (r := a.last_report) is not None]


def fragments_due(here: list[Agent]) -> bool:
    """Whether the fragments of the change whose agents in its worktree are
    `here` are due a doc editor. `held_budgets.doc_budgets` reads a change's
    doc budget only where this holds, so it reads `HeldRead.fragments` only
    where `fragments_step` may need the budget."""
    return (not any(a.pending for a in here) and bool(drafter_reports(here))
            and not any(briefs.gives_fragments(a) for a in here))


def fragments_step(state: State, t: Ticket, w: Path,
                   here: list[Agent]) -> Step | None:
    """The step that gives the fragments of `state.held.fragments[w]` to a
    doc editor launched for them, where `fragments_due` holds: the
    addition of `doc-editor` to the `editors` field of a change that gives
    none, and otherwise the launch of a doc editor on those fragments."""
    if not fragments_due(here):
        return None
    places = state.held.fragments.get(w, ())
    if not places:
        return None
    if lacking_doc_editor(t, w, state) is not None:
        if t.number not in state.computed.doc_budgets:
            return Undecided(mctx("the budget of change {number} with a doc editor is "
                                  "unknown").format(number=t.number))
        return Bash(add_editor(t.number, Role.DOC_EDITOR, state.me))
    drafters = drafter_ids(here)
    if isinstance(drafters, Undecided):
        return drafters
    return Launch(Role.DOC_EDITOR, t.number, briefs.editor(
        Role.DOC_EDITOR, t.number, True, w,
        editor_scratch(t.number, Role.DOC_EDITOR, state.scratch), state.me,
        places, tuple(drafters), of_fragments=True), model=t.model(Role.DOC_EDITOR))
