"""The names the handbook and the lib fix, which the model reads a
solver's program by. Every reader of them takes them from here."""

from engine import RelationName

PARAMS = "Params"
"""The component of the parameterization (solver-file.md:112)."""
DETERMINE = "Determine"
"""The component of the determination (solver-file.md:157)."""
PARSE = "Parse"
"""The component the program and `Determine` share (solver-file.md:155)."""
CHOICE = "Choice"
"""The case type (solver-file.md:22, :124-131)."""
TIEBREAK_RESOLUTION = "TiebreakResolution"
"""The type of `out`'s resolution column (solver-file.md:168)."""
ENUMERATOR = "impl_choice"
"""The relation that enumerates the cases (solver-file.md:108)."""
CASE_COLUMN = "ch"
"""`impl_choice`'s column (solver-file.md:108)."""
INPUT = RelationName((), "in")
"""The input grid's cells (lib.dl, the runner contract)."""
OUTPUT = RelationName((), "out")
"""The output grids' cells (solver-file.md:36, :98)."""
EX_IN = RelationName((), "ex_in")
EX_OUT = RelationName((), "ex_out")
"""The examples' inputs and train outputs, by example (solver-file.md:158,
:162)."""
PROPOSE = "propose"
"""The relation a proposer states its values in (proposers.dl)."""
LIB_FILE = "lib.dl"
PROPOSERS_FILE = "proposers.dl"
IDENT = "Ident"
"""The lib's identity type (solver-file.md:161)."""
COLOR = "Color"
BOX = "Box"
"""The lib's edge-margin record (style.md, "Box readings")."""
ELEM_SUFFIX = "_elem"
"""The suffix of the lib relations that enumerate an orientation type."""
CONCEPT = "concept"
"""The name of the concept case (solver-file.md:194)."""
STORED = "stored"
"""The reading of a stored branch, `<rel>=stored` (solver-file.md:199)."""
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
NUMBER = "number"
"""Souffle's number type."""
UNIT = "Unit"
"""The lib's one-value type, which labels a row."""
