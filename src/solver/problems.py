"""What a load function found malformed, unresolved or off its shape in a
solver file, its annotations or a witness file, as data."""

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

from engine import GridLayout, ParseFailure, RelationName, TypeName
from engine.quotes import quotes

if TYPE_CHECKING:
    from solver.annotations import ClaimKind, DirectiveWord, HeaderWord
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
    """An annotation of a known word whose text is not in the word's form,
    with the parts that break the form (`OffForm`)."""
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
    OUTPUT_OFF_VERDICT = "output-off-verdict"
    """A witness entry's `output` in the form the witness file does not
    take for the verdict of a line that records the entry, or for no
    verdict where no line records one (`OutputOffVerdict`)."""
    ASSIGN_NAMES_NOTHING = "assign-names-nothing"
    """An `assign` key that is no parameter and no `@store` relation."""
    ASSIGN_VALUE_UNKNOWN = "assign-value-unknown"
    """An `assign` string value that is no lib constant and no
    constructor without arguments of an ADT the solver or the lib
    declares."""
    ASSIGN_ARITY = "assign-arity"
    ASSIGN_TYPE = "assign-type"
    """An `assign` value whose facts have another number of arguments
    than the relation it names has columns outside its case columns."""
    ANCHOR_WITHOUT_STAMP = "anchor-without-stamp"
    """An `assign` grid with an anchor for a name the solver stores by no
    one `GRID_STAMP` call: by one position GRID call, by facts, by several
    GRID calls, or as a `@store` relation. An anchor locates a cell as a
    distance from a mark, and such a name has no mark."""
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
    CASE_COLUMN_OFF_FORM = "case-column-off-form"
    """A parameter's column that carries the case in another form than a
    parameter's case column (`CaseColumnOffForm`)."""
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


@quotes("solver-file.md", "File structure",
        "// @rule <slug>: <what the output takes from the input> // "
        "@approximated: <the rule the program runs> // @witness <id>: "
        "<plausibility> <verdict>")
class FormPart(StrEnum):
    """A part of an annotation line that breaks its word's form."""

    INDENT = "indent"
    """A nested word's line with fewer than two spaces after `//`."""
    PARENT = "parent"
    """A nested line with no line to nest under above it
    (`solver.annotations.NESTS_UNDER`)."""
    SLUG = "slug"
    """A claim's slug, or a slug a `@claim` line lists, off the slug's
    form, which `checker.render.faults.SLUG_FORM` states."""
    ID = "id"
    """A `@witness` line's id, off the slug's form."""
    PROPOSER = "proposer"
    """A `@derive` line's proposer, missing or off its form, which its
    sentence in `checker.render.faults.OFF_PART_TEXT` states."""
    RELATION = "relation"
    """The relation a `@store` or `@ignore` line names, off its form,
    which its sentence in `checker.render.faults.OFF_PART_TEXT` states."""
    SPACING = "spacing"
    """The spaces around the name before a `:`, off their form, which the
    spacing sentences of `checker.render.faults.OFF_PART_TEXT`, with a name,
    and `MISSING_PART_TEXT`, with none, state."""
    COLON = "colon"
    """The `:` the form takes, missing."""
    TEXT = "text"
    """The text after the `:`, missing."""
    TRAILING = "trailing"
    """Text after a word that takes none, as `@draft` takes none."""
    PLAUSIBILITY = "plausibility"
    """A plausibility, missing or no `solver.annotations.Plausibility`."""
    VERDICT = "verdict"
    """A verdict, missing or off its form, which its sentence in
    `checker.render.faults.OFF_PART_TEXT` states."""
    VALUE = "value"
    """The one word of a `@relaxed` or `@reassigned` line, missing or more
    than one."""
    REPRESENTATIVE = "representative"
    """A `@representative:` value other than a task id with at most one
    case name after it."""
    DASH = "dash"
    """The `—` before an `@ignore` line's reason, missing."""
    REASON = "reason"
    """An `@ignore` line's reason after its `—`, missing."""
    DERIVE_RELATION = "derive-relation"
    """A relation named on an `@ignore: derive` line, which names none."""


@dataclass(frozen=True)
class OffPart:
    """A part of an annotation line that breaks its word's form: the part,
    and its text as the line writes it; None for a part that is missing,
    and for `INDENT` and `PARENT`."""

    part: FormPart
    read: str | None


@dataclass(frozen=True)
class OffForm:
    """An annotation line off its word's form: the line's text, its word,
    and each part of it that breaks the form."""

    text: str
    word: "DirectiveWord | HeaderWord | ClaimKind"
    parts: tuple[OffPart, ...]


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


@quotes("solver-file.md", "Witness file",
        "An `assign` of a relation in [Params](docs/handbook/solver-file.md#params) "
        "or of a `@store` line's relation gives its facts without their case "
        "part")
@dataclass(frozen=True)
class AssignArity:
    """An `assign` value of the relation `name` whose facts have `given`
    arguments, where the relation takes `expected`: its columns outside
    its case part (`solver.run_parts.PerCase.given`), `per_case` where it has
    a case column."""

    name: str
    given: tuple[int, ...]
    expected: int
    per_case: bool


@quotes("solver-file.md", "Witness file",
        "Use a string for a lib constant and a list for a record. Write a "
        "constructor with no arguments as a string, such as "
        "`\"$Anchor\"`.")
@dataclass(frozen=True)
class AssignType:
    """An `assign` value of the relation `name` with the argument `arg`,
    as JSON writes it, in the column `column`, where that argument is no
    value of `type`: the column's type, or for a case column with fields
    outside the case, the list of those fields' types."""

    name: str
    column: str
    type: str | tuple[str, ...]
    arg: str


@quotes("solver-file.md", "Params",
        "**Case column.** Where the cases that read a relation in Params "
        "store different values of it, the relation takes a case column in "
        "the form of `out`'s, and each fact's case column is the `Choice` "
        "value of the case that stores the fact.")
@dataclass(frozen=True)
class CaseColumnOffForm:
    """A parameter's column that carries the case and is no case column
    of a parameter (`solver.columns.parameter_case_columns`): of `type`, as
    the declaration writes it, which is of the `kind` given."""

    relation: str
    column: str
    type: TypeName
    kind: "OffFormType"


class OffFormType(StrEnum):
    """What a column that carries the case is, other than `Choice`
    (`solver.case_columns.case_columns`)."""

    ADT = "adt"
    """An ADT in `Choice`."""
    RECORD = "record"
    """A record with a field of an ADT in `Choice`."""


class OutputForm(StrEnum):
    """The form of a witness entry's `output`."""

    GROUPS = "groups"
    JUDGED = "judged"
    """A bare grid, the judged output."""


@dataclass(frozen=True)
class OutputOffVerdict:
    """A witness entry's `output` in the form `held`, against the verdict
    of the line `line`; None where no line records a verdict for the
    entry."""

    held: OutputForm
    line: int | None


type Detail = (Quoted | Named | OffForm | ShapeFault | Undecided
               | GridOffLayout | AnchorWithoutStamp | GridCellOffForm
               | AssignArity | AssignType | CaseColumnOffForm
               | OutputOffVerdict | ParseFailure)


@dataclass(frozen=True)
class Fault:
    """What a load function could not read: its kind, where it
    stands, and what was read there as typed parts. The load functions
    return it beside the model and raise nothing for it, and put no
    default in place of what they could not read."""

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
