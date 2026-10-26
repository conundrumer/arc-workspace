"""The stage of the work on a ticket: the stages in their order, the stage
of the work an agent of each role does, and the stage a ticket's agents
put it at."""

from enum import IntEnum
from collections.abc import Mapping

from operations.roles import Role
from operations.state import Ticket
from ticketing.vocabulary import Kind, Status


class Stage(IntEnum):
    """The stages of a ticket's work, in their order."""
    TRIAGE = 0
    DESIGN = 1
    BUILD = 2
    REVIEW = 3
    MERGE = 4


ROLE_STAGE: Mapping[Role, Stage] = {
    Role.TICKET_ANALYST: Stage.TRIAGE, Role.TRANSCRIPT_REVIEW: Stage.TRIAGE,
    Role.COST_AUDIT: Stage.TRIAGE, Role.LISTING_WAIT: Stage.TRIAGE, Role.OPERATOR: Stage.TRIAGE,
    Role.TICKET_REVIEWER: Stage.DESIGN, Role.DESIGN_REVIEWER: Stage.DESIGN,
    Role.CODE_EDITOR: Stage.BUILD, Role.DOC_EDITOR: Stage.BUILD, Role.HANDBOOK_EXPANDED: Stage.BUILD,
    Role.SOLVER_FIX: Stage.BUILD, Role.ANALYZE: Stage.BUILD, Role.CREATE: Stage.BUILD,
    Role.REFINE: Stage.BUILD,
    Role.ITEM_CHECKER: Stage.REVIEW, Role.CODE_REVIEWER: Stage.REVIEW, Role.DOC_REVIEWER: Stage.REVIEW,
    Role.LIB_REVIEWER: Stage.REVIEW, Role.BATCH_PROFILE: Stage.REVIEW,
    Role.AFTER_MERGE: Stage.MERGE,
}
"""The stage of the work an agent of each role does."""

assert set(ROLE_STAGE) == set(Role), "each role has a stage"


def stage(roles: list[Role], change: Ticket | None) -> Stage:
    """The stage of a ticket at whose work, or that of its change
    `change`, agents of `roles` are: the highest of theirs, and at least
    Design for a ticket in `tickets/draft/` and Build for a change past
    it."""
    floor = (Stage.DESIGN if change is not None and change.status is Status.DRAFT
             else Stage.TRIAGE if change is None or change.kind is not Kind.CHANGE else Stage.BUILD)
    return max([floor, *(ROLE_STAGE[r] for r in roles)])
