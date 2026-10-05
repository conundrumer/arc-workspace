"""The names the handbook and the lib fix, which the model reads a
solver's program by. Every reader of them takes them from here."""

from typing import Annotated

from engine import RelationName, Scope
from engine.program import Primitive
from engine.quotes import quotes

PARAMS: Annotated[str,
    quotes("solver-file.md", "Params",
           "Params contains the parameterization and what derives from "
           "it.")] = "Params"
"""The component of the parameterization."""
DETERMINE: Annotated[str,
    quotes("solver-file.md", "Determination",
           "`Determine` contains the determination as one relation per "
           "determined parameter, with the parameter's name and "
           "schema")] = "Determine"
"""The component of the determination."""
PARAMS_SCOPE = Scope((PARAMS,))
"""The scope of what `Params` declares and holds."""
DETERMINE_SCOPE = Scope((DETERMINE,))
"""The scope of what `Determine` declares and holds."""
PARSE: Annotated[str,
    quotes("solver-file.md", "Parse",
           "A `.comp Parse<Key>` contains a derivation that the program and "
           "the Determine comp share.")] = "Parse"
"""The component the program and `Determine` share."""
CHOICE: Annotated[str,
    quotes("solver-file.md", "Cases",
           "A case's base is its `Choice` value"),
    quotes("solver-file.md", "Types",
           "an ADT in `Choice`, in one of these places:")] = "Choice"
"""The case type."""
TIEBREAK_RESOLUTION: Annotated[str,
    quotes("solver-file.md", "Alt outputs",
           "The solver enumerates a tiebreak's resolutions through a trailing "
           "`out` column of type "
           "`TiebreakResolution`.")] = "TiebreakResolution"
"""The type of `out`'s resolution column."""
DEMONSTRATED_CHOICE: Annotated[str,
    quotes("solver-file.md", "Demonstrated choice",
           "`DemonstratedChoice` is the `Demonstrated` type argument of a "
           "`DemonstrationConsistency` instance.")] = "DemonstratedChoice"
"""The type whose constructors are the rules a demonstration selects
among."""
DEMONSTRATION_CONSISTENCY: Annotated[str,
    quotes("solver-file.md", "Demonstrated choice",
           "`DemonstratedChoice` is the `Demonstrated` type argument of a "
           "`DemonstrationConsistency` instance.")] = "DemonstrationConsistency"
"""The lib's component that reads which values of its `Demonstrated`
type a demonstrated pair is consistent with (sets.dl)."""
DEMONSTRATED: Annotated[str,
    quotes("solver-file.md", "Demonstrated choice",
           "`DemonstratedChoice` is the `Demonstrated` type argument of a "
           "`DemonstrationConsistency` instance.")] = "Demonstrated"
"""The type parameter of `DemonstrationConsistency` whose values a
demonstrated pair selects among (sets.dl)."""
ENUMERATOR: Annotated[str,
    quotes("solver-file.md", "Cases",
           "**`impl_choice`.** The relation that enumerates the cases is "
           "`impl_choice`, and its column is `ch`.")] = "impl_choice"
"""The relation that enumerates the cases."""
IMPL = RelationName((), ENUMERATOR)
"""`impl_choice` as a run names it."""
CASE_COLUMN: Annotated[str,
    quotes("solver-file.md", "Cases",
           "**`impl_choice`.** The relation that enumerates the cases is "
           "`impl_choice`, and its column is `ch`.")] = "ch"
"""`impl_choice`'s column."""
INPUT = RelationName((), "in")
"""The input grid's cells (lib.dl, the runner contract)."""
OUTPUT: Annotated[RelationName,
    quotes("solver-file.md", "Cases",
           "A case's model reads its output grids from `out` at that "
           "case")] = RelationName((), "out")
"""The output grids' cells."""
EX_IN = RelationName((), "ex_in")
EX_OUT: Annotated[RelationName,
    quotes("solver-file.md", "Determination",
           "derived from `ex_in` and `ex_out`.")] = RelationName((), "ex_out")
"""The examples' inputs and train outputs, by example."""
PROPOSE = "propose"
"""The relation a proposer states its values in (proposers.dl)."""
LIB_FILE = "lib.dl"
PROPOSERS_FILE = "proposers.dl"
IDENT = "Ident"
"""The lib's identity type (lib.dl, `.type Ident`)."""
COLOR = "Color"
BOX: Annotated[str,
    quotes("style.md", "Box readings",
           "A Box column is read as a cell with the `Position` alias, a "
           "translation with the `Offset` alias, or a rectangle, margin, or "
           "frame change with bare `Box`.")] = "Box"
"""The lib's edge-margin record."""
COMPOSE = "compose"
"""The lib relation that places one box in another's frame, the shift of a
cell by an offset among its uses (lib/box.dl)."""
ELEM_SUFFIX = "_elem"
"""The suffix of the lib relations that enumerate an orientation type."""
DETERMINATION_DIFF = RelationName((), "_determination_diff")
"""The lib's relation of the parameters whose determination differs
(lib.dl)."""
RUN_RELATIONS = frozenset({INPUT, OUTPUT, EX_IN, EX_OUT, DETERMINATION_DIFF})
"""The relations the runner writes or reads around a solver's own: no
relation of the solver's model."""
POSITION = "Position"
"""The lib's cell type: a cell by its distances to the frame's edges."""
OFFSET = "Offset"
"""The lib's offset type."""
NUMBER = Primitive.NUMBER
"""Souffle's number type."""
UNIT = "Unit"
"""The lib's one-value type, which labels a row."""
