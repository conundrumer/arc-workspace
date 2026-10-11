"""The agents the operator launches, by the procedure each serves, and the
description each launch gives, from which the command reads back what each
launch of any operator of the session serves."""

import re
from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum

from handbook.agents import agent_meta


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
    DOC_REVIEWER = "doc-reviewer"
    CODE_REVIEWER = "code-reviewer"
    BATCH_PROFILE = "batch-profile"
    BATCH_GATE = "batch-gate"
    AFTER_MERGE = "after-merge"
    OPERATOR = "operator"

    @property
    def agent_type(self) -> str:
        """The `subagent_type` its launch gives."""
        return GENERAL if self in GENERAL_ROLES else self.value

    @property
    def model(self) -> Model | None:
        """For a role in `GENERAL_ROLES`, the model `GENERAL_MODELS` gives,
        or None where it gives none. For any other role, the model the
        front matter of its agent document in this tree gives, read at each
        call so that a launch in a running session takes the document's
        current model, where the harness holds the definition it loaded at
        the session's start. Raises ValueError on a model that is no
        `Model`."""
        if self in GENERAL_ROLES:
            return GENERAL_MODELS.get(self)
        model = agent_meta(self.agent_type).get("model")
        return None if model is None else Model(model)


GENERAL = "general-purpose"

GENERAL_ROLES = frozenset({Role.TRANSCRIPT_REVIEW, Role.BATCH_PROFILE, Role.BATCH_GATE,
                           Role.AFTER_MERGE})
"""The roles no agent document gives, whose brief gives their work."""

GENERAL_MODELS: dict[Role, Model] = {Role.TRANSCRIPT_REVIEW: Model.SONNET}
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
