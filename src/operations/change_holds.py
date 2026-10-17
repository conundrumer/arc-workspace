"""The steps a change is held on that a ruling can decide, each with its
text and its choices (`Hold`): the step on what its editors leave
(`left_hold`, `questions_hold`) and the review of its documents
(`findings_hold`, `unreplied_hold`). A ruling is keyed on the text of its
step, so the step that holds and each read of its ruling build that text
here."""

from dataclasses import dataclass

from controlled_markdown import mctx
from operations.directives import Decision
from operations.reports import NO_FINDING, OPEN_LABELS, items_of
from operations.state import Agent


LEFT_CHOICES = {
    Decision.MERGE: mctx("go on to the merge; the close of the change closes its open question "
                       "tickets"),
    Decision.AGAIN: mctx("launch another ticket analyst on what the item checker leaves for a "
                       "decision")}
"""The choices of a step held on what the editors of a change leave."""


@dataclass(frozen=True)
class Hold:
    text: str
    choices: dict[Decision, str]


def left_hold(a: Agent, number: str) -> Hold | None:
    """The step held on the `decision:` and `unfinished:` items of the
    latest reply of `a`, the ticket analyst on what the editors of change
    `number` leave, or None where that reply gives none."""
    items = items_of(a, OPEN_LABELS)
    if items is None:
        return None
    return Hold(mctx("ticket analyst {agent} on change {number} leaves these items for the "
                     "coordinator:").format(agent=a.agent_id, number=number) + (
                         "\n" + items + "\n" + mctx("The change is held on them")), LEFT_CHOICES)


def questions_hold(a: Agent, number: str) -> Hold:
    """The step held on the open question tickets of change `number` once
    `a`, the ticket analyst on what its editors leave, returned."""
    return Hold(mctx("ticket analyst {agent} returned on change {number}, and its question "
                     "tickets stand open").format(agent=a.agent_id, number=number), LEFT_CHOICES)


REVIEW_CHOICES = {Decision.PASSES: mctx("the review passes"),
                  Decision.AGAIN: mctx("launch another doc reviewer")}
"""The choices of a step held on the review of a change's documents."""


def findings_hold(r: Agent, number: str) -> Hold:
    """The step held on the reply of `r`, the doc reviewer of change
    `number`, that does not open with `NO_FINDING`."""
    return Hold(mctx("the reply of doc reviewer {agent} on change {number} does not open with "
                     "`{no_finding}`").format(agent=r.agent_id, number=number,
                                              no_finding=NO_FINDING), REVIEW_CHOICES)


def unreplied_hold(r: Agent, number: str) -> Hold:
    """The step held on `r`, the doc reviewer of change `number`, that has
    not replied since its editors ended."""
    return Hold(mctx("doc reviewer {agent} of change {number} has not replied since its editors "
                     "ended").format(agent=r.agent_id, number=number), REVIEW_CHOICES)
