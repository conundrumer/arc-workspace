"""The kinds of launch that no batch holds (`batches`), each declared
once, in `KINDS`, by its role and the test of its subject, and the read
of a ticket analyst's subject that the test of the process assessment
applies."""

from collections.abc import Callable
from dataclasses import dataclass
from functools import cache

from operations.roles import Purpose, Role, analyst_of
from operations.state import DOC_REVIEW, Agent, Review, State


def analysis(role: Role, subject: str) -> tuple[Purpose, str] | None:
    """The purpose and the rest of the subject of a launch of `role` on
    `subject`, or None where it is no ticket analyst's or its subject opens
    with no purpose."""
    return analyst_of(subject) if role is Role.TICKET_ANALYST else None


def any_subject(_: str) -> bool:
    return True


@dataclass(frozen=True)
class Unbatched:
    """A kind of launch that no batch holds: the launches of `role` on a
    subject that `subject` accepts."""
    role: Role
    subject: Callable[[str], bool] = any_subject

    def matches(self, role: Role, subject: str) -> bool:
        return role is self.role and self.subject(subject)

    def agents(self, state: State) -> list[Agent]:
        """The agents of the session of this kind, in launch order."""
        return [a for a in state.transcripts.agents if self.matches(a.role, a.subject)]


PROFILE = Unbatched(Role.BATCH_PROFILE)
"""The profile agent of After a batch."""

GATE = Unbatched(Role.GATE)

STANDING = Unbatched(Role.DOC_REVIEWER, lambda s: s.startswith(DOC_REVIEW))
"""The standing doc review."""

ASSESSMENT = Unbatched(Role.TICKET_ANALYST, lambda s: (
    (parsed := analyst_of(s)) is not None and parsed[0] is Purpose.ASSESS))
"""The process assessment."""

COST_AUDIT = Unbatched(Role.COST_AUDIT)

LOAD_CHECK = Unbatched(Role.LOAD_CHECK)
"""The load check of an alert of the machine watcher."""

KINDS = (PROFILE, *(Unbatched(r.role) for r in Review), GATE, STANDING, ASSESSMENT,
         COST_AUDIT, LOAD_CHECK)


@cache
def follows(role: Role, subject: str) -> bool:
    """Whether a launch of `role` on `subject` is one no batch holds."""
    return any(k.matches(role, subject) for k in KINDS)
