"""The payloads of the witness kinds: the checks over the witness file and
the cases (principles.md:126-128, :150-153, :185, :271-287)."""

from dataclasses import dataclass
from enum import StrEnum

from engine import Grid
from solver.annotations import ClaimKind, Verdict
from solver.model import Base, Branch, Case, ConstructorBranch
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
    verdict, which no case gives (principles.md:153)."""

    cases: CaseSet
    expected: GroupGrid | RejectedOutput
    actual: Outcome


@dataclass(frozen=True)
class UnlistedPayload:
    """Cases of the solver that give `actual` on an entry, which no group of the
    entry lists (solver-file.md:181-186)."""

    cases: CaseSet
    actual: Outcome


# ANNOTATION: one dataclass per sentence shape.


@dataclass(frozen=True)
class ApproximatedWithoutWitness:
    """A claim is approximated and has no `@witness` line under its
    `@approximated:` (solver-file.md:93)."""

    kind: ClaimKind
    slug: str


@dataclass(frozen=True)
class ApproximationUnwitnessed:
    """No witness under the claim's `@approximated:` shows `case` giving
    an output other than the verdict's (solver-file.md:93)."""

    kind: ClaimKind
    slug: str
    case: Case


@dataclass(frozen=True)
class ForeignUnderApproximated:
    """A `@witness` under an `@approximated:` line is `foreign`
    (solver-file.md:92)."""

    witness: str
    kind: ClaimKind
    slug: str


@dataclass(frozen=True)
class RelaxedNotScene:
    """`@relaxed <slug>` denotes a claim of another kind than a scene claim
    (procedure.md:150)."""

    slug: str
    denotes: ClaimKind


@dataclass(frozen=True)
class RelaxedNoClaim:
    """`@relaxed <slug>` denotes no claim in the header (procedure.md:150)."""

    slug: str


@dataclass(frozen=True)
class VerdictOutputUnknown:
    """The output the verdict denotes on the witness is unknown: the runner
    holds no case that takes it (principles.md:150-153)."""

    verdict: Verdict


@dataclass(frozen=True)
class WitnessEntryMissing:
    """A `@witness` line whose id the witness file does not hold."""

    witness: str


@dataclass(frozen=True)
class BranchUnwitnessed:
    """A branch of a choice point, other than its concept branch, whose
    branch comment holds no `@witness` line (style.md:50)."""

    constructor: str


@dataclass(frozen=True)
class ReassignedMismatch:
    """The `@reassigned` lines and the witness's `assign` name different
    parameters (procedure.md:150)."""

    witness: str
    reassigned: tuple[str, ...]
    assigned: tuple[str, ...]


@dataclass(frozen=True)
class StandsElsewhere:
    """The witness stands at the stored assignment, and its `assign`
    changes `changed` (principles.md:127)."""

    witness: str
    changed: tuple[str, ...]


@dataclass(frozen=True)
class NoDivergence:
    """On the witness, `model` and `first` give the same output or neither
    is defined, so it is no witness of `branch` (principles.md:126)."""

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


@dataclass(frozen=True)
class Taking:
    """One side of an unseparated pair, or a part both sides take: a base,
    None where it holds none, and `@derive` and `@store` branches."""

    base: Base | None
    branches: tuple[Branch, ...]


@dataclass(frozen=True)
class UnseparatedPayload:
    """Cases that differ by `a` and `b` and that no witness separates, and
    under `under` what both cases of each such pair take: one finding per
    pair of bases, naming the branch choices under which it holds
    (history "One finding per unseparated pair of bases")."""

    a: Taking
    b: Taking
    under: tuple[Taking, ...]


@dataclass(frozen=True)
class SubsumedPayload:
    """No run shows `subsumed` defined and differing from each case of
    `by` (principles.md:176, :179, :287)."""

    subsumed: Case
    by: CaseSet


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
    """The case condition a dropped case fails (principles.md:271-287)."""

    FIT = "Fit"
    UNDEFINED = "undefined"
    NOT_RUN = "not run"
    """No run with the case restored gives a cell at it, so no condition
    is judged."""
    ENTRY_NOT_RUN = "entry not run"
    """A witness entry's assignment is one the model cannot place, a fault
    `check_faults` reports, so the case is not run on that entry and no
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
class AssignPayload:
    """An `assign` key whose rows have `arities` arguments, where the
    relation it names takes `columns`."""

    name: str
    arities: tuple[int, ...]
    columns: int


@dataclass(frozen=True)
class TaskAssignPayload:
    """An entry of a given file whose `assign` holds strings that are no
    lib constant, each with its key in `values`, runs at `assign`, the
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
                       | AssignPayload | TaskAssignPayload)
