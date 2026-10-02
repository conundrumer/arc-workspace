"""The payloads of the `@derive` and `@store` kinds and of the
determination check (solver-file.md, under "Params", "Program" and
"Determination")."""

from dataclasses import dataclass

from engine import RelationName, Row
from solver.annotations import CaseMarker, IgnoreLine
from solver.model import Branch, DeriveBranch, StoreBranch
from solver.solve import PairId, ParamDiff

type BranchName = DeriveBranch | StoreBranch
"""A `@derive` or `@store` branch, whose name the renderer prints through
`solver.names.name`; a branch whose line does not stand yet holds none
(`DeriveBranch.line`), or, for a `@store` branch, the line the survey
judges it with."""


@dataclass(frozen=True)
class IdleIgnorePayload:
    """A named `@ignore: derive` or `@ignore: store` line that excludes
    no case of the solver (solver-file.md, under "Params" and "Program"): the
    line, the branch of the `@derive` or `@store` line it stands under (None
    where it stands under none), and the branches its name contains."""

    ignore: IgnoreLine
    under: DeriveBranch | StoreBranch | None
    contains: tuple[Branch, ...]


@dataclass(frozen=True)
class MissingLinePayload:
    """A derivation that fits, or a relation with one value on every
    input, with no `@derive` or `@store` line and no bare `@ignore` line
    in its place. `cases` names the `Choice` cases at which the relation
    has the value, where another case of it has another value, by the
    fewest names that denote exactly them (`solver.names.cover`)."""

    branch: BranchName
    cases: tuple[str, ...] = ()


@dataclass(frozen=True)
class ExcludedPayload:
    """A `@derive` or `@store` line no case of the solver takes: its
    branch, the line of each named `@ignore` line under it, where those
    lines exclude cases of it, and whether `impl_choice` excludes cases
    of it."""

    branch: BranchName
    ignores: tuple[int, ...]
    impl_choice: bool


@dataclass(frozen=True)
class BranchPayload:
    """The payload of the kinds that concern one branch by its name."""

    branch: BranchName


@dataclass(frozen=True)
class BranchEntryPayload:
    """The witness file's entry of a branch's name, at whose assignment
    each case that takes the branch gives the output of the case that
    takes the point's first branch there and the same branches
    elsewhere."""

    branch: BranchName
    entry: str


@dataclass(frozen=True)
class DuplicatePayload:
    """Two lines of one branch: the first, and the one after it."""

    branch: BranchName
    first_line: int
    second_line: int


@dataclass(frozen=True)
class DeriveFitPayload:
    branch: DeriveBranch
    pair: PairId


@dataclass(frozen=True)
class StoreValuesPayload:
    """A `@store` relation that holds `values` values at each of `cases`,
    named by the fewest names that denote exactly them
    (`solver.names.cover`), so its branch's name denotes that many
    branches there."""

    relation: RelationName
    branch: StoreBranch
    values: int
    cases: tuple[str, ...]


@dataclass(frozen=True)
class RelationPayload:
    """The payload of the store kinds that concern one relation."""

    relation: RelationName


@dataclass(frozen=True)
class NotBetween:
    """The relation is no program relation between `in` and `out`."""


@dataclass(frozen=True)
class Unread:
    """No case of the solver reads the relation."""


@dataclass(frozen=True)
class NoAnchor:
    """The value stands at another place on each input, and the runner
    picks no anchor."""


@dataclass(frozen=True)
class KeyedBy:
    """The value varies by the columns `keys`, an id the runner stores
    nothing under."""

    keys: tuple[str, ...]


@dataclass(frozen=True)
class DiffersOn:
    """The relation gives another value on the input `pair`."""

    pair: PairId


@dataclass(frozen=True)
class NoRows:
    """The relation holds no row on any input."""


type NoValue = NotBetween | Unread | NoAnchor | KeyedBy | DiffersOn | NoRows
"""Why a `@store` line's relation gives no value the runner can store."""


@dataclass(frozen=True)
class StoreNoValuePayload:
    relation: RelationName
    reason: NoValue


@dataclass(frozen=True)
class ColorAskPayload:
    """A relation, at the columns `columns` where they are fewer than its
    own, that holds one color on every input (principles.md, under
    "Stored or derived"): its rows there, and the `Choice` cases at which it
    has them where another case of it has another value, by the fewest names that
    denote exactly them (`solver.names.cover`)."""

    relation: RelationName
    columns: tuple[str, ...]
    types: tuple[str, ...]
    value: tuple[Row, ...]
    cases: tuple[str, ...]


@dataclass(frozen=True)
class RowCapPayload:
    """The relations over the row cap on some input, which are not
    checked."""

    relations: tuple[RelationName, ...]
    cap: int


@dataclass(frozen=True)
class HomonymsPayload:
    """A branch's name that denotes the `@store` branches of several
    relations (solver-file.md, under "Witness file")."""

    branch: StoreBranch
    relations: tuple[RelationName, ...]


@dataclass(frozen=True)
class MarkerUnownedPayload:
    marker: CaseMarker
    clause_lines: tuple[int, ...]


@dataclass(frozen=True)
class DeterminationDiffPayload:
    """A determined parameter whose determination differs from its stored
    value (solver-file.md, under "Determination")."""

    diff: ParamDiff


@dataclass(frozen=True)
class DerivedDataPayload:
    """A `Determine` relation named for a relation `Params` derives
    (solver-file.md, under "Determination")."""

    relation: str


@dataclass(frozen=True)
class NoTaskPayload:
    """The solver's task has no task file, so a check that runs over its
    examples runs nothing."""


@dataclass(frozen=True)
class NotCheckedPayload:
    """No relation both reads `in` and feeds `out`, so the store check
    has no relation to check."""


type BranchesPayload = (IdleIgnorePayload | MissingLinePayload
                        | BranchPayload | ExcludedPayload | BranchEntryPayload
                        | DuplicatePayload | DeriveFitPayload
                        | StoreValuesPayload | RelationPayload
                        | StoreNoValuePayload | ColorAskPayload
                        | RowCapPayload | HomonymsPayload
                        | MarkerUnownedPayload | DeterminationDiffPayload
                        | DerivedDataPayload | NoTaskPayload
                        | NotCheckedPayload)
"""The payload of every kind of this family."""
