"""The doc editor of a change's `mctx` fragments.

Once a code editor or a `handbook-expanded` editor of a change has
reported, where the change adds or changes the text of an `mctx` fragment
(`HeldRead.fragments`) and no doc editor was launched since that report, the
fragments whose text no earlier doc editor of the fragments was launched on
(`unseen`) go to a doc editor launched for them: a change whose `editors`
field gives no doc editor first gets one in that field, with the budget of
its new `editors` set, and the doc editor the field then gives is
launched with the fragments; a change that gives one gets a doc editor
of the fragments alone (`briefs.FRAGMENTS_PART`), which is the latest
editor of its part beside the doc editor of the documents."""

import shlex
from pathlib import Path

from controlled_markdown import mctx
from operations import briefs
from operations.change_agents import latest_editors
from operations.filing import editor_scratch
from operations.roles import Role
from operations.state import Agent, Place, State, Ticket
from operations.steps import Bash, Launch, Step, Undecided, agent_ids
from operations.tracker import add_editor

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


def seen_dir(number: str, scratch: Path) -> Path:
    """The directory under the session's scratchpad `scratch` of the files
    `tree_reads.py seen` writes for the change `number`."""
    return scratch / f"{number}-fragments-seen"


def write_seen(number: str, w: Path, scratch: Path) -> str:
    """The Bash command that writes the places of the worktree `w` of the
    change `number` to a file of `seen_dir`."""
    return shlex.join(["uv", "run", "python", "scripts/tree_reads.py", "seen", str(w),
                       str(seen_dir(number, scratch))])


def unseen(state: State, t: Ticket, w: Path, here: list[Agent]) -> tuple[Place, ...]:
    """The places of `state.held.fragments[w]` that `fragments_step` gives the
    next doc editor of the fragments. A place with no text is always given:
    its file does not read as fragments, so no file of `state.held.seen` can show
    that its fragments are unchanged."""
    places = state.held.fragments.get(w, ())
    judged = [a.launched for a in here if a.role is Role.DOC_EDITOR
              and briefs.FRAGMENTS_PART in a.brief and a.last_report is not None]
    if not judged:
        return places
    before = [s for s in state.held.seen.get(t.number, ()) if s.time < max(judged)]
    if not before or (seen := before[-1].places) is None:
        return places
    return tuple(p for p in places if p.text is None or (p.file, p.text) not in seen)


def fragments_step(state: State, t: Ticket, w: Path,
                   here: list[Agent]) -> Step | None:
    """The step that gives the fragments of `unseen` to a doc editor
    launched for them, once a drafter of the change has reported and no doc
    editor was launched since its latest report: the addition of
    `doc-editor` to the `editors` field of a change that gives none, then,
    where no file of `state.held.seen` was written since that report, the
    command that writes one (`write_seen`), and otherwise the launch of a
    doc editor on those fragments."""
    reported = [r.time for a in here if a.role in DRAFTERS and (r := a.last_report) is not None]
    if not reported or any(
            a.role is Role.DOC_EDITOR and a.launched > max(reported) for a in here):
        return None
    places = unseen(state, t, w, here)
    if not places:
        return None
    if lacking_doc_editor(t, w, state) is not None:
        if t.number not in state.computed.doc_budgets:
            return Undecided(mctx("the budget of change {number} with a doc editor is "
                                  "unknown").format(number=t.number))
        return Bash(add_editor(t.number, Role.DOC_EDITOR, state.me))
    if not any(s.time > max(reported) for s in state.held.seen.get(t.number, ())):
        return Bash(write_seen(t.number, w, state.scratch))
    drafters = drafter_ids(here)
    if isinstance(drafters, Undecided):
        return drafters
    return Launch(Role.DOC_EDITOR, t.number, briefs.editor(
        Role.DOC_EDITOR, t.number, True, w,
        editor_scratch(t.number, Role.DOC_EDITOR, state.scratch), state.me,
        places, tuple(drafters), of_fragments=True), model=t.model(Role.DOC_EDITOR))
