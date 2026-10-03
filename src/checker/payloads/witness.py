"""The payloads of the witness kinds: the checks over the witness file and
the cases (principles.md, under "Witnesses", "Relational form" and "Cases")."""

from dataclasses import dataclass
from enum import StrEnum

from engine import Grid
from solver.annotations import ClaimKind, Verdict
from solver.model import (
    Branch,
    Case,
    ConstructorBranch,
    DerivedAtStore,
)
from solver.solve import Outcome, PairId
from solver.witness import AssignValue, GroupGrid, RejectedOutput

type BranchRef = ConstructorBranch | Branch
"""A branch of any choice point: a constructor, or a `@derive` or `@store`
branch."""


@dataclass(frozen=True)
class CaseSet:
    """A set of the solver's cases, and the names that print it: the name
    of a lone case, else the fewest names that denote exactly the set
    among the solver's cases (`solver.names.cover`)."""

    cases: tuple[Case, ...]
    names: tuple[str, ...]


@dataclass(frozen=True)
class DriftPayload:
    """The cases that give `actual` on an entry where the entry records
    `expected`: a group's grid, or the judged output of an `other`
    verdict, which no case gives (principles.md, under "Witnesses")."""

    cases: CaseSet
    expected: GroupGrid | RejectedOutput
    actual: Outcome


@dataclass(frozen=True)
class UnlistedPayload:
    """Cases of the solver that give `actual` on an entry, which no group of the
    entry lists (solver-file.md, under "Witness file")."""

    cases: CaseSet
    actual: Outcome


# ANNOTATION: one dataclass per sentence shape.


@dataclass(frozen=True)
class ApproximatedWithoutWitness:
    """A claim is approximated and has no `@witness` line under its
    `@approximated:` (solver-file.md, under "Header")."""

    kind: ClaimKind
    slug: str


@dataclass(frozen=True)
class ApproximationUnwitnessed:
    """No witness under the claim's `@approximated:` shows `case` giving
    an output other than the verdict's (solver-file.md, under "Header")."""

    kind: ClaimKind
    slug: str
    case: Case


@dataclass(frozen=True)
class ForeignUnderApproximated:
    """A `@witness` under an `@approximated:` line is `foreign`
    (solver-file.md, under "Header")."""

    witness: str
    kind: ClaimKind
    slug: str


@dataclass(frozen=True)
class RelaxedNotScene:
    """`@relaxed <slug>` denotes a claim of another kind than a scene claim
    (procedure.md, under "Witness")."""

    slug: str
    denotes: ClaimKind


@dataclass(frozen=True)
class RelaxedNoClaim:
    """`@relaxed <slug>` denotes no claim in the header (procedure.md, under
    "Witness")."""

    slug: str


@dataclass(frozen=True)
class VerdictOutputUnknown:
    """The output the verdict denotes on the witness is unknown: the runner
    holds no case that takes it (principles.md, under "Witnesses")."""

    verdict: Verdict


@dataclass(frozen=True)
class WitnessEntryMissing:
    """A `@witness` line whose id the witness file does not hold."""

    witness: str


@dataclass(frozen=True)
class BranchUnwitnessed:
    """A branch of a choice point, other than its concept branch, whose
    branch comment holds no `@witness` line (style.md, under "Cases")."""

    constructor: str


@dataclass(frozen=True)
class ReassignedMismatch:
    """The `@reassigned` lines and the witness's `assign` name different
    parameters (procedure.md, under "Witness")."""

    witness: str
    reassigned: tuple[str, ...]
    assigned: tuple[str, ...]


@dataclass(frozen=True)
class StandsElsewhere:
    """The witness stands at the stored assignment, and its `assign`
    changes `changed` (principles.md, under "Witnesses")."""

    witness: str
    changed: tuple[str, ...]


@dataclass(frozen=True)
class NoDivergence:
    """On the witness, `model` and `first` give the same output or neither
    is defined, so it is no witness of `branch` (principles.md, under
    "Witnesses")."""

    witness: str
    model: Case
    first: Case
    branch: BranchRef


type AnnotationPayload = (ApproximatedWithoutWitness | ApproximationUnwitnessed
                          | ForeignUnderApproximated | RelaxedNotScene
                          | RelaxedNoClaim | VerdictOutputUnknown
                          | WitnessEntryMissing | ReassignedMismatch
                          | StandsElsewhere | NoDivergence
                          | BranchUnwitnessed)
"""A verdict that names no case is the fault
`NAME_DENOTES_NO_CASE`, not one of these."""

ANNOTATION_SHAPES = (ApproximatedWithoutWitness, ApproximationUnwitnessed,
                     ForeignUnderApproximated, RelaxedNotScene,
                     RelaxedNoClaim, VerdictOutputUnknown,
                     WitnessEntryMissing, ReassignedMismatch,
                     StandsElsewhere, NoDivergence, BranchUnwitnessed)
"""The classes of `AnnotationPayload`, for an `isinstance` test."""


type PointBranch = ConstructorBranch | Branch | DerivedAtStore
"""The branch a case takes at one choice point: a constructor, a `@derive`
branch or `<param>=stored`, a `@store` branch or `<rel>=derived`."""


@dataclass(frozen=True)
class UnseparatedPayload:
    """Pairs of cases of the solver that no witness separates and that
    differ by the branches `a` and `b` alone, at the points where they
    differ: `contexts` holds one case of each such pair, with the fewest
    names that cover those cases among the cases of their side that have
    a counterpart on the other, none where that is every one; `of` counts
    the pairs of the solver's cases that differ by `a` and `b` alone.
    Both cases of a pair take the same branch at every other point."""

    a: tuple[PointBranch, ...]
    b: tuple[PointBranch, ...]
    contexts: CaseSet
    of: int


@dataclass(frozen=True)
class SubsumedPayload:
    """Pairs of cases of the solver that differ by the branches `a` and `b`
    alone, where no run shows the `a` case defined and differing from the
    `b` case and some run shows them apart (principles.md, under
    "Equivalence and subsumption" and "Cases"); `contexts` and `of` as
    `UnseparatedPayload` has them."""

    a: tuple[PointBranch, ...]
    b: tuple[PointBranch, ...]
    contexts: CaseSet
    of: int


@dataclass(frozen=True)
class ConceptPayload:
    """On an entry of a judged output, the concept case gives `concept`,
    another grid than `judged`."""

    judged: Grid
    concept: Outcome


@dataclass(frozen=True)
class SeparatesPayload:
    """A name in the `separates` text that denotes a case of the solver, and that
    no group lists."""

    name: str


@dataclass(frozen=True)
class UnheldPayload:
    """Group names, as written, of cases the runner does not hold."""

    names: tuple[str, ...]


class Condition(StrEnum):
    """The case condition a dropped case fails (principles.md, under "Cases")."""

    FIT = "Fit"
    UNDEFINED = "undefined"
    NOT_RUN = "not run"
    """No run with the case restored gives a cell at it, so no condition
    is judged."""
    ENTRY_NOT_RUN = "entry not run"
    """A witness entry's assignment is one the model cannot place, a fault
    `fault_findings` reports, so the case is not run on that entry and no
    condition is judged."""
    EQUIVALENCE = "unseparated"
    SUBSUMPTION = "Subsumption"


@dataclass(frozen=True)
class DroppedPayload:
    """A case `impl_choice` drops and the first condition it fails: the
    pair it fails Fit at, or the case it is unseparated from or subsumed
    by; None for a case no run shows defined."""

    case: Case
    condition: Condition
    against: Case | PairId | None


@dataclass(frozen=True)
class UnjustifiedDropPayload:
    """A case `impl_choice` drops that fails no case condition, and the
    cases no witness separates it from."""

    case: Case
    unseparated: CaseSet


@dataclass(frozen=True)
class TaskAssignPayload:
    """An entry of a given file whose `assign` holds strings that name
    nothing (`solver.model.unknown_strings`), each with its key in `values`, runs at `assign`, the
    `assign` of the task's witness file's entry of its id."""

    values: tuple[tuple[str, str], ...]
    task_entry: str
    assign: tuple[tuple[str, AssignValue], ...]


@dataclass(frozen=True)
class ConceptUnenumeratedPayload:
    """The concept case, which the cases `impl_choice` enumerates do not
    hold."""

    concept: Case


type WitnessPayload = (DriftPayload | UnlistedPayload | AnnotationPayload
                       | UnseparatedPayload | SubsumedPayload
                       | ConceptPayload | SeparatesPayload | UnheldPayload
                       | DroppedPayload | UnjustifiedDropPayload
                       | ConceptUnenumeratedPayload
                       | TaskAssignPayload)
