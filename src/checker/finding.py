"""The one finding type: a kind from one closed Enum, a typed location, and
a payload dataclass per kind."""

from dataclasses import dataclass
from enum import StrEnum

from engine import Atom, ParseFailure, RelationName, RunFailure, Term
from engine.program import AtomLiteral, Comparison
from solver.annotations import CaseMarker, IgnoreLine
from solver.category import Category
from solver.model import Case
from solver.problems import Fault, ProblemKind
from solver.solve import PairId
from checker.payloads.branches import BranchesPayload
from checker.payloads.witness import (  # noqa: F401  (re-exported)
    ANNOTATION_SHAPES,
    AnnotationPayload,
    ApproximatedWithoutWitness,
    ApproximationUnwitnessed,
    AssignPayload,
    BranchRef,
    ConceptPayload,
    Condition,
    DriftPayload,
    DroppedPayload,
    ForeignUnderApproximated,
    NoDivergence,
    ReassignedMismatch,
    RelaxedNoClaim,
    RelaxedNotScene,
    SeparatesPayload,
    StandsElsewhere,
    SubsumedPayload,
    TaskAssignPayload,
    UnheldPayload,
    UnjustifiedDropPayload,
    UnlistedPayload,
    UnseparatedPayload,
    VerdictOutputUnknown,
    WitnessEntryMissing,
    WitnessPayload,
)


class Kind(StrEnum):
    """Every kind of finding (plan §D5 `Finding`): the kinds the checks
    give, and each fault kind (`ProblemKind`) as a member of its own, so
    that `Kind(problem.kind)` is a fault's finding kind."""

    # Witness kinds (procedure.md:169-181).
    DRIFT = "drift"
    UNLISTED = "unlisted"
    ANNOTATION = "annotation"
    UNSEPARATED = "unseparated"
    SUBSUMED = "subsumed"
    CONCEPT = "concept"
    """No principle stands behind it (`check_concept_output`); outside
    `FAILING`."""
    SEPARATES = "separates"
    """No principle stands behind it (`check_separates`); outside
    `FAILING`."""
    UNHELD = "unheld"
    DROPPED = "dropped"
    """A case `impl_choice` drops, and a case condition it fails; outside
    `FAILING`."""
    DROP_UNJUSTIFIED = "drop-unjustified"
    """A case `impl_choice` drops that fails no case condition
    (procedure.md:210)."""
    CONCEPT_UNENUMERATED = "concept-unenumerated"
    """The concept case is not among the cases `impl_choice` enumerates
    (solver-file.md:109)."""
    ASSIGN = "assign"
    TASK_ASSIGN = "task-assign"

    # Lint: the payload's category says which (solver-file.md:134).
    LINT = "lint"
    HINT = "hint"

    # `@derive` and `@store` kinds (solver-file.md:120-122, :137-138).
    IDLE_BRANCH_IGNORE = "idle-ignore"
    """An `@ignore: derive|store <name>` line that excludes no case
    (solver-file.md:122)."""
    MISSING_BRANCH_LINE = "missing-branch-line"
    DUPLICATE_BRANCH_LINE = "duplicate-branch-line"
    BRANCH_WITNESS_MISSING = "branch-witness-missing"
    BRANCH_ENTRY = "branch-entry"
    DERIVE_UNREAD = "derive-unread"
    DERIVE_FIT = "derive-fit"
    DERIVE_UNPLACED = "derive-unplaced"
    STORE_PARAMETER_NAME = "store-parameter-name"
    STORE_VALUES = "store-values"
    STORE_NO_VALUE = "store-no-value"
    STORE_UNTAKEN = "store-untaken"
    STORE_HOMONYMS = "store-homonyms"
    STORE_IDENT_KEY = "store-ident-key"
    """A `@store` line on a relation with an `Ident` column: an ordinal
    the program assigns names no object in another run, so the tool runs
    no case of the branch (plan §D5 `FAILING`)."""
    STORE_PARAMS_ASK = "store-params-ask"
    STORE_ROW_CAP = "store-row-cap"
    MARKER_UNOWNED = "marker-unowned"
    DETERMINATION_DIFF = "determination-diff"
    """A determined parameter whose determination differs from its stored
    value (solver-file.md:158-161)."""
    DETERMINATION_OF_DERIVED = "determination-of-derived"
    """A `Determine` relation that mirrors a relation `Params` derives
    (solver-file.md:160)."""
    NO_TASK = "no-task"
    """A check that runs over the task's examples, on a solver whose task
    has no task file."""
    NOT_CHECKED = "not-checked"
    """The store check did not run: no relation both reads `in` and feeds
    `out`; outside `FAILING`."""

    # Runs that gave no result.
    TIMEOUT = "timeout"
    RUN_FAILED = "failed"

    # The fault kinds (plan §D4 `Fault`), each a member of its own under
    # its `ProblemKind` name and value, through `check_faults`. Among them
    # `UNDECIDED`, a case the principles do not decide (plan §G3), which
    # the checks give too; outside `FAILING`.
    locals().update({k.name: k.value for k in ProblemKind})


# Locations


@dataclass(frozen=True)
class AtLine:
    """A line of the solver file."""

    line: int


class WitnessFileRole(StrEnum):
    TASK = "task"
    """`programs/witnesses/<task_id>.wit.json`."""
    GIVEN = "given"
    """A file the command names in its place."""


@dataclass(frozen=True)
class AtEntry:
    """A witness file entry, by id."""

    entry: str
    file: WitnessFileRole
    assigned: bool = True
    """Whether the location prints, after the id, the names the entry's
    `assign` reassigns; the entry of a `@derive` or `@store` branch's
    name is printed by its id alone, as the branch sections print it."""


@dataclass(frozen=True)
class AtCase:
    case: Case


@dataclass(frozen=True)
class AtRelation:
    relation: RelationName


@dataclass(frozen=True)
class AtParameter:
    parameter: str


@dataclass(frozen=True)
class AtPair:
    pair: PairId


class WholeFile(StrEnum):
    SOLVER = "solver"
    WITNESS_FILE = "witness file"


@dataclass(frozen=True)
class AtFile:
    """A whole file."""

    file: WholeFile


type Where = AtLine | AtEntry | AtCase | AtRelation | AtParameter | AtPair | AtFile


# Payloads

@dataclass(frozen=True)
class FaultPayload:
    """The payload of every fault kind."""

    problem: Fault


class LintSentence(StrEnum):
    """Which sentence a lint finding states; the renderer holds each
    sentence's text."""

    RESERVED_WORD = "reserved word"
    SHADOWED_TYPE = "shadowed type"
    LIB_NAME = "lib name"
    LIB_PRIVATE = "lib private"
    LIB_INTERNAL_COMP = "lib internal comp"
    NO_PROPOSAL_ENTRY = "no proposal entry"
    PROPOSAL_UNREAD = "proposal unread"
    PARSE_UNREAD = "parse unread"
    FAMILY_NOT_PARSED = "family not parsed"
    FAMILY_RECORD = "family record"
    FAMILY_NO_CASE = "family no case"
    FAMILY_NO_CHOICE = "family no choice"
    MARKER_SLASH = "marker slash"
    ORDINARY_RELAXED = "ordinary relaxed"
    ONE_CASE_UNKNOWN_FAILED = "one case unknown failed"
    ONE_CASE_UNKNOWN_TIMEOUT = "one case unknown timeout"
    ONE_CASE = "one case"
    NO_TASK_ID = "no task id"
    HEADER_ORDER = "header order"
    HEADER_PROSE = "header prose"
    DRAFT_PLACE = "draft place"
    REVIEW_KIND = "review kind"
    FIELD_TWICE = "field twice"
    SIBLING_DROPS = "sibling drops"
    SLUG_TWICE = "slug twice"
    UNKNOWN_KEYWORD = "unknown keyword"
    NO_KEYWORDS = "no keywords"
    NO_RULE = "no rule"
    GLOSS_ABOVE = "gloss above"
    OWN_LINE = "own line"
    CONCEPT_WITNESS = "concept witness"
    WITNESS_PLACE = "witness place"
    UNREAD_FIELD = "unread field"
    CASE_SECTION_BEFORE = "case section before"
    CASE_SECTION_UNDER = "case section under"
    CASE_SECTION_READ = "case section read"
    CASE_SECTION_UNJUDGED = "case section unjudged"
    CASE_SECTION_READ_UNJUDGED = "case section read unjudged"
    BRANCH_APPROXIMATED = "branch approximated"
    CLAIM_UNSTATED = "claim unstated"
    INSTANCE_UNCLAIMED = "instance unclaimed"
    CONCEPT_UNCLAIMED = "concept unclaimed"
    BANNED_TYPE = "banned type"
    DEAD = "dead"
    ALIAS = "alias"
    NEGATED_USE = "negated use"
    CHOICE_DOMAIN = "choice domain"
    MARKER_LISTS_NO_CASE = "marker lists no case"
    SHARED_UNREAD = "shared unread"
    CHOICE_TAG = "choice tag"
    CROSS_CHOICE = "cross choice"
    RAW_AGGREGATE = "raw aggregate"
    ATOM_TWICE = "atom twice"
    ATOM_ADDS_NOTHING = "atom adds nothing"
    NEGATED_VALUE = "negated value"
    NAMED_COMPLEMENT = "named complement"
    DECL_PLACEMENT = "decl placement"
    LONG_CLAUSE = "long clause"
    PASS_THROUGH = "pass through"
    SINGLE_CONSUMER = "single consumer"
    CHAIN_JOIN = "chain join"
    ARGMAX = "argmax"
    CONST_PRODUCT = "const product"
    CONST_JOIN = "const join"
    COMMON_SUBEXPR = "common subexpr"
    COMMON_SUBEXPR_MERGE = "common subexpr merge"
    TYPED_ORDER_COMPARES = "typed order compares"
    TYPED_ORDER_ORDERS = "typed order orders"
    TYPED_ORDER_RANKS = "typed order ranks"
    LIB_IDIOM = "lib idiom"
    COMP_IDIOM_MEMBER = "comp idiom member"
    COMP_IDIOM_IMAGE = "comp idiom image"
    DOMAIN_ENUMERATOR = "domain enumerator"
    IDLE_IGNORE = "idle ignore"
    IGNORE_ON_DECL = "ignore on decl"
    IGNORE_UNPLACED = "ignore unplaced"


type Code = Atom | AtomLiteral | Comparison | Term
"""A piece of the solver's code a lint sentence quotes; the renderer
writes it."""


@dataclass(frozen=True)
class LintFragment:
    """A lint finding whose message is the code fragment that fires: a
    literal, a lib constant macro, an operator, a functor, or a chart
    name. `on_relation` says the finding stands on a relation, which an
    `@ignore` line of its category keeps."""

    category: Category
    fragment: str
    on_relation: bool = False


@dataclass(frozen=True)
class LintNamed:
    """A lint sentence over names of the solver, the lib or the handbook:
    relations, types, constructors, words, slugs, in the order the
    sentence reads them."""

    category: Category
    sentence: LintSentence
    names: tuple[str, ...]
    more: tuple[str, ...] = ()
    """A second list the sentence names, where it names two."""
    on_relation: bool = False


@dataclass(frozen=True)
class LintCounted:
    """A lint sentence with a count beside its names: a width with a
    limit, or a count of literals and the line of the clause shared
    with."""

    category: Category
    sentence: LintSentence
    names: tuple[str, ...]
    count: int
    other: int
    on_relation: bool = False


@dataclass(frozen=True)
class LintCode:
    """A lint sentence that quotes code: the code as it stands, then the
    code that states it directly, where the sentence gives one."""

    category: Category
    sentence: LintSentence
    code: tuple[Code, ...]
    rewritten: tuple[Code, ...]
    names: tuple[str, ...] = ()
    on_relation: bool = False


@dataclass(frozen=True)
class LintMarked:
    """A lint sentence over a name and the place it stands or belongs: a
    case marker, a component, or neither (above every marker)."""

    category: Category
    sentence: LintSentence
    name: str
    marker: CaseMarker | None
    comp: str | None = None
    on_relation: bool = False
    cases: tuple[str, ...] = ()
    """The cases the sentence names, through `cover`, where it names
    them."""


class LabelWord(StrEnum):
    """The annotation a witness line opens with."""

    WITNESS = "witness"
    DERIVE = "derive"
    STORE = "store"


@dataclass(frozen=True)
class LintLabeled:
    """A lint sentence over a `@witness`, `@derive` or `@store` line: its
    word, the witness id or proposer it names (None for `@store`), and the
    `@relaxed` slugs it carries."""

    category: Category
    sentence: LintSentence
    word: LabelWord
    name: str | None
    relaxed: tuple[str, ...]
    on_relation: bool = False


@dataclass(frozen=True)
class LintRun:
    """A lint sentence over the outcome of a run: the cases the runner
    holds, or a run that failed."""

    category: Category
    sentence: LintSentence
    outcome: Case | RunFailure
    on_relation: bool = False


@dataclass(frozen=True)
class LintFamily:
    """A lint sentence on a `@representative` line: the sibling's task
    id, the case the line gives, and the sibling's parse failure where it
    does not parse."""

    category: Category
    sentence: LintSentence
    task_id: str
    case: str
    failure: ParseFailure | None = None
    on_relation: bool = False


@dataclass(frozen=True)
class LintIgnore:
    """A lint sentence over an `@ignore` line, and the relation it stands
    on where it stands on one."""

    category: Category
    sentence: LintSentence
    ignore: IgnoreLine
    site: RelationName | None
    on_relation: bool = False


type LintPayload = (LintFragment | LintNamed | LintCounted | LintCode
                    | LintMarked | LintLabeled | LintRun | LintFamily
                    | LintIgnore)
"""The payload of `LINT` and `HINT`: its category says which lint."""

LINT_SHAPES = (LintFragment, LintNamed, LintCounted, LintCode, LintMarked,
               LintLabeled, LintRun, LintFamily, LintIgnore)
"""The classes of `LintPayload`, for an `isinstance` test."""


class RunKind(StrEnum):
    """The run that gave no result."""

    CASE = "case"
    PAIR = "pair"
    DROPPED_CASE = "dropped case"
    """The runs of a dropped case on its own (`witness --every-case`)."""
    WITNESS = "witness"
    DELETION = "deletion"
    DETERMINATION = "determination"
    PROBE = "probe"
    STORE_SEARCH = "store search"


@dataclass(frozen=True)
class NoResultPayload:
    """The payload of `TIMEOUT` and `RUN_FAILED`: which run, of which case,
    and the engine's failure. `TIMEOUT` stands for either limit, and
    `failure`, a `CpuLimit` or a `WallLimit`, names which; `RUN_FAILED`
    stands for every other failure."""

    run: RunKind
    case: Case | None
    failure: RunFailure


@dataclass(frozen=True)
class UndecidedPayload:
    """A `@store` line's relation that holds one set of rows on every
    input and gives no value the store survey reads: whether it is fixed
    task data, which the principles do not decide."""

    relation: RelationName


type Payload = (WitnessPayload | FaultPayload | LintPayload
                | BranchesPayload | NoResultPayload | UndecidedPayload)


@dataclass(frozen=True)
class Finding:
    """One finding of any check (plan §D5 `Finding`)."""

    kind: Kind
    where: Where
    payload: Payload


FAILING = frozenset(Kind) - {
    Kind(ProblemKind.UNDECIDED), Kind.HINT, Kind.STORE_ROW_CAP, Kind.UNLISTED,
    Kind.CONCEPT, Kind.SEPARATES, Kind.DROPPED, Kind.TASK_ASSIGN,
    Kind.NOT_CHECKED,
}
"""The kinds that fail a command's check (plan §D5 `FAILING`)."""
