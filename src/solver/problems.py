"""What a reader of the solver model could not read, as data."""

from dataclasses import dataclass
from enum import StrEnum

from engine import ParseFailure


class ProblemKind(StrEnum):
    """The kinds of `Fault`."""

    PARSE_FAILURE = "parse-failure"
    """The solver's text is outside the grammar."""
    RETIRED_FORM = "retired-form"
    """An annotation form the handbook retired: `@invariant`, `@addition`,
    `@deviation`, `@rule` above an instance."""
    UNKNOWN_FORM = "unknown-form"
    """An `@word` no annotation form has."""
    OFF_FORM = "off-form"
    """An annotation of a known word whose text is not in the word's form."""
    UNKNOWN_IGNORE_CATEGORY = "unknown-ignore-category"
    """`@ignore: <text>` whose text is no `solver.category.Category`."""
    DIRECTIVE_UNPLACED = "directive-unplaced"
    """A `@derive`, `@store` or `@ignore: derive|store` line that stands
    above nothing it can stand on."""
    STORE_NAMES_NOTHING = "store-names-nothing"
    """`@store <rel>` above an `.init` whose instance has no such relation."""
    UNKNOWN_PROPOSER = "unknown-proposer"
    """`@derive <Proposer>` naming no proposer."""
    WITNESS_FILE_SHAPE = "witness-file-shape"
    """The witness file's shape is off."""
    NAME_DENOTES_NO_CASE = "name-denotes-no-case"
    """A name that denotes no case, wherever a name is read, a witness
    entry's group and the verdict of a `@witness`, `@derive` or `@store`
    line among them."""
    NAME_FORM = "name-form"
    """A name in none of the forms solver-file.md:193-199 lists."""
    ASSIGN_NAMES_NOTHING = "assign-names-nothing"
    """An `assign` key or string that names nothing."""
    MARKER_NAMES_NOTHING = "marker-names-nothing"
    """A case marker's name that denotes no case."""
    REPRESENTATIVE_MISSING = "representative-missing"
    """`@representative` names a task with no solver."""
    INSTANCE_OF_NOTHING = "instance-of-nothing"
    """An `.init` of a component that neither the solver's text nor a file
    it includes declares."""
    INSTANCE_UNFOLLOWED = "instance-unfollowed"
    """An instance path deeper than the model follows (`MAX_DEPTH`
    instances), named at the solver's instance it starts from."""
    BASE_OF_NOTHING = "base-of-nothing"
    """A component that extends a component no file declares."""
    TYPE_ARGUMENTS = "type-arguments"
    """An instance, or a component's base, given another number of type
    arguments than the component declares type parameters."""
    RIGID_CHARTS = "rigid-charts"
    """A RIGID call in `Params` whose block's chart relations are not one
    per name the call binds."""
    UNDECIDED = "undecided"
    """A form the model does not decide how to read. `check_faults`
    gives it the finding kind `undecided`, which does not fail a
    command."""


@dataclass(frozen=True)
class InSolver:
    line: int


@dataclass(frozen=True)
class InWitnessFile:
    """An entry of the witness file, by id; None for the file as a
    whole."""

    entry: str | None


type ProblemPlace = InSolver | InWitnessFile


@dataclass(frozen=True)
class Quoted:
    """The solver's text read at the place: a comment's content after
    `//`."""

    text: str


@dataclass(frozen=True)
class Named:
    """The name read at the place: a case name, a proposer, a relation, an
    `@ignore` category, a task id, an `assign` key or constant."""

    name: str


class Expected(StrEnum):
    """What a witness file's shape has where a fault stands
    (solver-file.md:174-190)."""

    JSON = "json"
    """The text is JSON."""
    OBJECT = "object"
    STRING = "string"
    LIST = "list"
    GRID = "grid"
    """A rectangular grid of integers 0 to 9."""
    GROUPS_OR_GRID = "groups-or-grid"
    """A list of groups, or one grid (`output`)."""
    GROUP_GRID = "group-grid"
    """A grid, a list of grids, or null (a group's `grid`)."""
    FACTS_OR_GRID = "facts-or-grid"
    """A list of facts, or a grid (an `assign` value)."""
    PRESENT = "present"
    """A field the shape requires, which is missing."""
    ABSENT = "absent"
    """No such field: the field stands and the shape has none."""
    UNIQUE = "unique"
    """An id, or a case a group lists, that stands once."""
    NONEMPTY = "nonempty"
    """A group that lists a case."""


@dataclass(frozen=True)
class ShapeFault:
    """Where a witness file leaves its shape: the path of the field from
    the entry, or from the file where the problem's place names no entry
    (a key, or a list index), and what the shape has there."""

    field: tuple[str | int, ...]
    expected: Expected


class UndecidedForm(StrEnum):
    """A form the model does not decide how to read."""

    CHOICE_FIELD_NOT_ADT = "choice-field-not-adt"
    """A field of a record `Choice` whose type is no ADT of the solver."""
    CHOICE_NOT_ADT_OR_RECORD = "choice-not-adt-or-record"
    CHOICE_NOT_ENUMERABLE = "choice-not-enumerable"
    """A `Choice` with a field of a type that has no values to enumerate,
    and no `impl_choice`."""
    GRID_CALL_NOT_CONSTANT = "grid-call-not-constant"
    """A GRID call of a parameter with a key or cell that is no
    constant."""
    FACT_NOT_CONSTANT = "fact-not-constant"
    """A fact of a parameter with a term that is no constant."""
    READ_THROUGH_NO_INSTANCE = "read-through-no-instance"
    """A `@store` line above a relation of a component that the program
    reads through no one instance."""
    SECOND_REPRESENTATIVE = "second-representative"
    GRID_FOR_KEYED_PARAMETER = "grid-for-keyed-parameter"
    """An `assign` grid for a parameter stored by other than one GRID
    call."""


@dataclass(frozen=True)
class Undecided:
    """A form the model does not decide how to read, and the name it
    stands on, where it stands on one."""

    form: UndecidedForm
    name: str | None


type Detail = Quoted | Named | ShapeFault | Undecided | ParseFailure


@dataclass(frozen=True)
class Fault:
    """What a reader of the model could not read: its kind, where it
    stands, and what was read there as typed parts (plan §D4
    `Fault`). The load functions return it beside the model and raise
    nothing for it."""

    kind: ProblemKind
    place: ProblemPlace
    detail: Detail
