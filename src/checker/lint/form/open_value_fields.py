"""The lint check on the fields of `OpenValue`: a field off the form
solver-file.md gives it under "Cases" (`solver.open_values.field_readings`)."""

from checker.finding import Finding, LintNamed, LintSentence
from checker.lint.view import lint
from checker.runs import Runs
from engine.quotes import quotes
from solver.aggregate import Solver
from solver.category import Category
from solver.open_values import FieldFault, FieldOff, field_readings

SENTENCE = {
    FieldFault.NO_RELATION: LintSentence.OPEN_VALUE_NO_RELATION,
    FieldFault.NO_RECORD: LintSentence.OPEN_VALUE_NO_RECORD,
    FieldFault.NO_COLUMN: LintSentence.OPEN_VALUE_NO_COLUMN,
}
"""The sentence of each way a field is off its form."""


@quotes("solver-file.md", "Cases",
        "each field with that relation's name and of a record type the "
        "solver names for that relation, whose fields are the relation's "
        "columns that tell one open value from another, under the same "
        "names.")
def check_open_value_field(solver: Solver, runs: Runs) -> list[Finding]:
    """Each field of `OpenValue` off its form, at the line its
    `FieldOff` gives."""
    return [lint(off.line, LintNamed(
                Category.OPEN_VALUE_FIELD, SENTENCE[off.fault],
                _names(off), off.missing))
            for off in field_readings(solver) if isinstance(off, FieldOff)]


def _names(off: FieldOff) -> tuple[str, ...]:
    """The names the sentence of `off` reads, in its order."""
    match off.fault:
        case FieldFault.NO_RELATION:
            return (off.field,)
        case FieldFault.NO_RECORD:
            return (off.field, off.type_name)
        case FieldFault.NO_COLUMN:
            return (off.type_name, off.field)
