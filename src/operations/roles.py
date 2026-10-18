"""The agents the operator launches, by the procedure each serves, and the
description each launch gives, from which the command reads back what each
launch of any operator of the session serves."""

import re
from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum

from handbook.agent_documents import agent_meta


class Model(StrEnum):
    """A model a launch gives as the Agent call's `model`: the one the
    agent's document gives, or the one the step sets in its place."""
    OPUS = "opus"
    SONNET = "sonnet"
    HAIKU = "haiku"


class Role(StrEnum):
    """What an agent the operator launches does, by the word its
    description gives."""
    ANALYZE = "analyze"
    CREATE = "create"
    REFINE = "refine"
    TRANSCRIPT_REVIEW = "transcript-review"
    TICKET_ANALYST = "ticket-analyst"
    TICKET_REVIEWER = "ticket-reviewer"
    ITEM_CHECKER = "item-checker"
    CODE_EDITOR = "code-editor"
    DOC_EDITOR = "doc-editor"
    HANDBOOK_EXPANDED = "handbook-expanded"
    SOLVER_FIX = "solver-fix"
    DOC_REVIEWER = "doc-reviewer"
    DESIGN_REVIEWER = "design-reviewer"
    CODE_REVIEWER = "code-reviewer"
    LIB_REVIEWER = "lib-reviewer"
    BATCH_PROFILE = "batch-profile"
    GATE = "gate"
    COST_AUDIT = "cost-audit"
    AFTER_MERGE = "after-merge"
    LISTING_WAIT = "listing-wait"
    OPERATOR = "operator"

    @property
    def agent_type(self) -> str:
        """The `subagent_type` its launch gives, where `launched_type` gives
        no other for the launch's subject."""
        return GENERAL if self in GENERAL_ROLES else TYPED_ROLES.get(self, self.value)

    @property
    def model(self) -> Model | None:
        """The agent document is read at each call so that a launch in a
        running session takes the document's current model, where the
        harness holds the definition it loaded at the session's start.
        Raises ValueError on a model that is no `Model`."""
        if self in GENERAL_ROLES:
            return GENERAL_MODELS.get(self)
        return document_model(self.agent_type)


def document_model(agent_type: str) -> Model | None:
    """The model the document of `agent_type` gives. Raises ValueError on a
    model that is no `Model`."""
    model = agent_meta(agent_type).get("model")
    return None if model is None else Model(model)


GENERAL = "general-purpose"

GENERAL_ROLES = frozenset({Role.TRANSCRIPT_REVIEW, Role.BATCH_PROFILE, Role.GATE,
                           Role.AFTER_MERGE, Role.COST_AUDIT, Role.LISTING_WAIT})
"""The roles no agent document gives, whose brief gives their work."""

TYPED_ROLES: dict[Role, str] = {Role.SOLVER_FIX: Role.HANDBOOK_EXPANDED.value}
"""The `subagent_type` of each role whose agent's document is that of
another role, where that role's own word is not an agent type."""

GENERAL_MODELS: dict[Role, Model] = {Role.GATE: Model.SONNET,
                                     Role.TRANSCRIPT_REVIEW: Model.HAIKU,
                                     Role.LISTING_WAIT: Model.HAIKU}
"""The model a launch of a role in `GENERAL_ROLES` gives, where the model it
inherits is not the one its work needs."""

AGENT_ID = r"a[0-9a-f]{16}"
"""The form of an agent id."""

PASSES = (Role.ANALYZE, Role.CREATE, Role.REFINE)
"""The passes of a solver pipeline, in their order."""

BARE_BRIEFS = (*PASSES, Role.OPERATOR)
"""The roles whose brief gives neither a report file nor a budget: their
documents give where their final reply goes."""

EDITORS = (Role.CODE_EDITOR, Role.HANDBOOK_EXPANDED, Role.DOC_EDITOR)
"""The editors a change's `editors` field may give, in the order the
command launches them, each in the change's worktree, which its brief
gives."""

BUILDERS = (Role.CODE_EDITOR, Role.HANDBOOK_EXPANDED)
"""The editors that build code: each drafts the text of the `mctx`
fragments its code needs, and a change with one gets a design review."""


def editors_of(names: Iterable[str]) -> tuple[Role, ...]:
    """The roles the names of an `editors` field give. Raises ValueError on
    a name that is no role."""
    return tuple(Role(e) for e in names)


MARK = "op"
"""The first word of each description the command gives."""

DESCRIPTION = re.compile(rf"^{MARK} (?P<role>[a-z-]+) (?P<subject>\S+)$")


@dataclass(frozen=True)
class Described:
    """What a launch's description gives: the role, and the subject the
    launch serves: a ticket's number, the numbers of tickets joined by `+`,
    a task id, an agent id, or a batch's number."""
    role: Role
    subject: str


def description(role: Role, subject: str) -> str:
    return f"{MARK} {role} {subject}"


def described(text: str) -> Described | None:
    """What `text`, an Agent call's description, gives, or None where it
    is no description the command gave."""
    m = DESCRIPTION.match(text)
    if m is None:
        return None
    try:
        return Described(Role(m["role"]), m["subject"])
    except ValueError:
        return None


class Purpose(StrEnum):
    """What a ticket analyst the operator launches settles, by the word its
    subject opens with."""
    TRIAGE = "triage"
    DRAFT = "draft"
    CHANGE = "change"
    PASS = "pass"
    STEP = "step"
    ASSESS = "assess"


DECISION_ANALYST = "decision-analyst"
DRAFT_ANALYST = "draft-analyst"

ANALYST_TYPES: dict[Purpose, str] = {Purpose.CHANGE: DECISION_ANALYST,
                                     Purpose.STEP: DECISION_ANALYST,
                                     Purpose.DRAFT: DRAFT_ANALYST}
"""The agent type that runs a ticket analyst on a purpose, where it is not
`ticket-analyst`: the role stays `Role.TICKET_ANALYST` whichever type runs
it, and the agent's name is its type."""

ANALYST_NAMES = frozenset({Role.TICKET_ANALYST.value, *ANALYST_TYPES.values()})
"""The agent names of a ticket analyst, whichever type runs it."""


def launched_type(role: Role, subject: str) -> str:
    """The `subagent_type` a launch of `role` on `subject` gives."""
    if role is Role.TICKET_ANALYST and (of := analyst_of(subject)) is not None:
        return ANALYST_TYPES.get(of[0], role.agent_type)
    return role.agent_type


def launched_model(role: Role, subject: str) -> Model | None:
    """The model a launch of `role` on `subject` gives, where its step sets
    none in its place."""
    if (agent_type := launched_type(role, subject)) == role.agent_type:
        return role.model
    return document_model(agent_type)


def parameter(value: object) -> str:
    """A parameter of a call as the command prints it."""
    return str(value).lower() if isinstance(value, bool) else str(value)


def launch_parameters(role: Role, subject: str, model: Model | None) -> dict[str, str]:
    """The parameters of the Agent call of a launch of `role` on `subject`
    other than its prompt, each as the printed launch gives it, where
    `model` is the model its step gives."""
    out = {"description": description(role, subject), "subagent_type": launched_type(role, subject),
           "run_in_background": parameter(True)}
    if (given := model or launched_model(role, subject)) is not None:
        out["model"] = str(given)
    return out


def analyst_subject(purpose: Purpose, subject: str) -> str:
    return f"{purpose}:{subject}"


def analyst_of(subject: str) -> tuple[Purpose, str] | None:
    """The purpose and the rest of a ticket analyst's subject, or None
    where it opens with no purpose."""
    head, _, rest = subject.partition(":")
    try:
        return Purpose(head), rest
    except ValueError:
        return None


JOIN = "+"


def joined(numbers: list[str]) -> str:
    return JOIN.join(numbers)


def subjects(subject: str) -> list[str]:
    """The ticket numbers a subject joined by `joined` gives."""
    return subject.split(JOIN)


LAUNCHING_EDITORS = (Role.CODE_EDITOR, Role.DOC_EDITOR)
"""The editors that launch the checks of their change, as
`changes.editor_step` gives."""

CHECKS = (Role.DESIGN_REVIEWER, Role.ITEM_CHECKER, Role.TICKET_ANALYST, Role.DOC_REVIEWER)
"""The roles of the checks of a change that its editors launch."""

CHECK_TYPES = frozenset(launched_type(r, analyst_subject(Purpose.CHANGE, "")) for r in CHECKS)
"""The `subagent_type` of each launch of `CHECKS`: a ticket analyst of a
change runs as the agent type of its purpose (`ANALYST_TYPES`)."""
