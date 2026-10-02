"""What a reader of the solver model could not read, as data."""

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

from engine import GridLayout, ParseFailure, RelationName
from engine.quotes import quotes

if TYPE_CHECKING:
    from solver.annotations import DirectiveWord
    from solver.model import DeriveBranch


@quotes("solver-file.md", "Witness file",
        "A `<name>` fixes the branch at some choice points, in one of these "
        "forms.")
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
    TWO_LINES_ON_DERIVATION = "two-lines-on-derivation"
    """A `@derive <Proposer>` line and an `@ignore: derive <Proposer>`
    line on one parameter for the same proposer: two lines on one
    derivation, named `<param>=<Proposer>` at the `@ignore` line."""
    WITNESS_FILE_SHAPE = "witness-file-shape"
    """The witness file's shape is off."""
    NAME_DENOTES_NO_CASE = "name-denotes-no-case"
    """A name that denotes no case, wherever a name is read, a witness
    entry's group and the verdict of a `@witness`, `@derive` or `@store`
    line among them."""
    NAME_FORM = "name-form"
    """A name in none of the name forms."""
    ASSIGN_NAMES_NOTHING = "assign-names-nothing"
    """An `assign` key or string that names nothing."""
    ANCHOR_WITHOUT_STAMP = "anchor-without-stamp"
    """An `assign` grid with an anchor for a name the solver stores by no
    one `GRID_STAMP` call: by one position GRID call, by facts, by several
    GRID calls, or as a `@store` relation."""
    GRID_CELL_OFF_FORM = "grid-cell-off-form"
    """An `assign` grid for a parameter whose GRID layout takes members
    alone, with a cell other than 0 and 1."""
    GRID_OFF_LAYOUT = "grid-off-layout"
    """An `assign` grid with no anchor for a stamp parameter, of another
    size than the solver's `GRID_STAMP` layout for it, or for a parameter
    the solver stores by no one GRID call."""
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
    """A form the model does not decide how to read. `fault_findings`
    gives it the finding kind `undecided`, which does not fail a
    command."""


@dataclass(frozen=True)
class InSolver:
    line: int


class WitnessFileRole(StrEnum):
    """The witness file a fault stands in."""

    TASK = "task"
    """The solver's own: `programs/witnesses/<task_id>.wit.json`, or the
    file `--witness-file` reads in its place."""
    GIVEN = "given"
    """A file the command names in its place."""
    ASSIGN = "assign"
    """The `--assign` object a command line gives, read as an entry's
    `assign`."""


@dataclass(frozen=True)
class InWitnessFile:
    """An entry of the witness file `file`, by id; None for the file as a
    whole."""

    entry: str | None
    file: WitnessFileRole


type ProblemPlace = InSolver | InWitnessFile


@dataclass(frozen=True)
class Quoted:
    """The solver's text read at the place: a comment's content after
    `//`."""

    text: str


@dataclass(frozen=True)
class Named:
    """The name read at the place: a case name, a proposer, a relation, an
    `@ignore` category, a task id, an `assign` key or constant, as its
    text; a relation an operation names, as its `RelationName`; a
    derivation, as its `DeriveBranch`; a directive's word, as its
    `DirectiveWord`."""

    name: "str | RelationName | DeriveBranch | DirectiveWord"


@quotes("solver-file.md", "Witness file",
        "`programs/witnesses/<task_id>.wit.json` holds the witnesses the "
        "solver's cases are pinned to.")
class Expected(StrEnum):
    """What a witness file's shape has where a fault stands."""

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
    ANCHORED_GRID = "anchored-grid"
    """An object of a `grid` and an `anchor`, the row and column of a cell
    of that grid (an `assign` value)."""
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


@quotes("solver-file.md", "Cases",
        "**`impl_choice`.** The relation that enumerates the cases is "
        "`impl_choice`, and its column is `ch`.")
class UndecidedForm(StrEnum):
    """A form the model does not decide how to read."""

    CHOICE_FIELD_NOT_ADT = "choice-field-not-adt"
    """A field of a record `Choice` whose type is no ADT of the solver."""
    CHOICE_NOT_ADT_OR_RECORD = "choice-not-adt-or-record"
    CHOICE_NOT_ENUMERABLE = "choice-not-enumerable"
    """A `Choice` with a field of a type that has no values to enumerate:
    with no `impl_choice` the solver has no case, and with one, no form with
    every case restored is built."""
    GRID_CALL_NOT_CONSTANT = "grid-call-not-constant"
    """A GRID call of a parameter with a key or cell that is no
    constant."""
    FACT_NOT_CONSTANT = "fact-not-constant"
    """A fact of a parameter with a term that is no constant."""
    READ_THROUGH_NO_INSTANCE = "read-through-no-instance"
    """A `@store` line above a relation of a component that the program
    reads through no one instance."""
    SECOND_REPRESENTATIVE = "second-representative"
    BRANCH_UNWITNESSED = "every-case-of-the-branch-unwitnessed"
    """A `@derive` line whose branch some case of the solver takes and no
    witnessed case takes."""


@dataclass(frozen=True)
class Undecided:
    """A form the model does not decide how to read, and the name it
    stands on, where it stands on one."""

    form: UndecidedForm
    name: str | None


@quotes("patterns.md", "`GRID_HxW` for grid data",
        "The layout is a picture with one token carrying the `@` prefix, and "
        "each member cell is emitted as its offset from that anchor.")
@dataclass(frozen=True)
class GridOffLayout:
    """An `assign` grid with no anchor that the solver's layout does not
    place: the parameter, its one `GRID_STAMP` layout, None where the
    solver stores it by no one GRID call, and the height and width of the
    grid the entry gives."""

    name: str
    layout: GridLayout | None
    given: tuple[int, int]


class Storage(StrEnum):
    """How the solver stores a name that has no one GRID call."""

    FACTS = "facts"
    GRID_CALLS = "grid-calls"
    """Several GRID calls."""
    STORED_RELATION = "stored-relation"
    """A `@store` line's relation."""


@quotes("patterns.md", "`GRID_HxW` for grid data",
        "To choose between a grid and a stamp, ask what locates a cell in the "
        "data at hand: a position in a frame whose extent the data fixes "
        "takes a grid, and a distance from a mark takes a stamp.")
@dataclass(frozen=True)
class AnchorWithoutStamp:
    """An `assign` grid with an anchor for a name stored by no one
    `GRID_STAMP` call: the name, and its one GRID call's layout or how it is
    stored otherwise."""

    name: str
    storage: GridLayout | Storage


@quotes("patterns.md", "`GRID_HxW` for grid data",
        "`GRID_STAMP_HxW` takes `1` for a member cell and emits `rel(delta)` "
        "for it")
@dataclass(frozen=True)
class GridCellOffForm:
    """An `assign` grid for a parameter whose layout takes members alone,
    with a cell other than 0 and 1: the parameter, its layout, the cell's
    row and column, and its value."""

    name: str
    layout: GridLayout
    cell: tuple[int, int]
    value: int


type Detail = (Quoted | Named | ShapeFault | Undecided | GridOffLayout
               | AnchorWithoutStamp | GridCellOffForm | ParseFailure)


@dataclass(frozen=True)
class Fault:
    """What a reader of the model could not read: its kind, where it
    stands, and what was read there as typed parts (plan §D4
    `Fault`). The load functions return it beside the model and raise
    nothing for it."""

    kind: ProblemKind
    place: ProblemPlace
    detail: Detail


@quotes("solver-file.md", "Witness file",
        "A `<name>` fixes the branch at some choice points, in one of these "
        "forms.")
@dataclass(frozen=True)
class NameFault:
    """A name that stands in no name form, or that denotes no case
    (`solver.names.denote`), before its place is known: the reader of the
    name knows where it stands, and `at` gives the `Fault` there."""

    kind: ProblemKind
    name: Named

    def at(self, place: ProblemPlace) -> Fault:
        """The fault at `place`."""
        return Fault(self.kind, place, self.name)
