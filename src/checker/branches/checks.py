"""The checks on the `@derive` and `@store` lines, on the relations
with one value on every input, and on the determination."""

from checker.finding import (
    AtFile,
    AtParameter,
    Finding,
    Kind,
    RunKind,
    WholeFile,
)
from checker.judged import NO_TASK, no_result
from checker.payloads.branches import DerivedDataPayload, DeterminationDiffPayload
from checker.runs import NoTask, Runs
from engine.quotes import quotes
from solver.aggregate import Solver
from solver.determine import Determined, NotRun


@quotes("principles.md", "Stored or derived",
        "**Two parameterizations.** Storing a value and deriving that value "
        "produce two different parameterizations.")
@quotes("solver-file.md", "Params",
        "**`@derive` directive.** The line is a branch of a choice point on "
        "the parameter")
@quotes("procedure.md", "Develop",
        "Hold as a branch each built-in derivation that fits a parameter")
def check_two_parameterizations(solver: Solver, runs: Runs) -> list[Finding]:
    """The findings on the `@derive` lines and their named `@ignore` lines:
    a second line of one branch, a line above a parameter no case of the
    solver reads, a branch that fails Fit, a named `@ignore` line that
    excludes no case, a derivation that fits with no line, and an entry of a
    branch's name that witnesses nothing."""
    return list(runs.derive_survey.findings)


@quotes("principles.md", "Stored or derived",
        "**Two parameterizations.** Storing a value and deriving that value "
        "produce two different parameterizations.")
@quotes("solver-file.md", "Program",
        "**`@store` directive.** The relation, or the instance's relation the "
        "line gives, has one value on every input, and the line is a branch "
        "of a choice point on it")
@quotes("solver-file.md", "Cases",
        "**Case markers.** Cases do not interleave: each case's Params and "
        "clauses are under its marker.")
def check_stored_or_derived(solver: Solver, runs: Runs) -> list[Finding]:
    """The findings on the `@store` lines and on the relations with one
    value on every input, and the markers under which cases they do not list
    read clauses."""
    return [f for f in runs.store_survey.findings
            if f.kind != Kind.STORE_PARAMS_ASK]


@quotes("principles.md", "Stored or derived",
        "Where a stored value fits, the concept case stores structure over "
        "colors as a parameter.")
def check_color_structure_stored(solver: Solver, runs: Runs
                                 ) -> list[Finding]:
    """A relation the `store` survey reads that the concept case reads and
    that holds one color on every input, with no `@store` line, asks for a
    Params parameter."""
    return [f for f in runs.store_survey.findings
            if f.kind == Kind.STORE_PARAMS_ASK]


@quotes("principles.md", "Models and tasks",
        "For each model, the solver stores an assignment determined by the "
        "evidence.")
@quotes("solver-file.md", "Determination",
        "`Determine` contains the determination's clauses as one relation "
        "per parameter whose value they give, with the parameter's name and "
        "schema, derived from `ex_in` and `ex_out`.")
@quotes("solver-file.md", "Determination",
        "The determination relation of a parameter with a case column gives "
        "the rows of every case.")
@quotes("solver-file.md", "Determination",
        "A derived relation has no determination relation.")
@quotes("patterns.md", "`RIGID` — a stored shape and its attached parts, in every orientation",
        "exposes them only as D4 placements that transform them together, so "
        "the stored pose is unobservable.")
def check_stored_assignment(solver: Solver, runs: Runs) -> list[Finding]:
    """A determined parameter whose `Determine` relation differs from its
    stored value is a finding; one stored by a RIGID call differs where no
    D4 image of its block's stored assembly gives the determined one. A
    parameter with a case column differs where its rows differ at a case
    the checks read (`checker.runs.Runs.differing_bases`), since each case
    reads its own rows. A
    `Determine` relation that mirrors a relation `Params` derives is a
    finding too. A determination that does not run (`KeysOff`) gives no
    finding here, since the lint finding of `check_determine_schema`
    states its fault."""
    result = runs.determined
    out: list[Finding] = []
    for d in solver.params.derived:
        if d.mirrored:
            out.append(Finding(Kind.DETERMINATION_OF_DERIVED,
                               AtParameter(d.name),
                               DerivedDataPayload(d.name)))
    if isinstance(result, Determined):
        for d in result.diffs:
            bases = runs.differing_bases(d)
            if bases == ():
                continue
            out.append(Finding(Kind.DETERMINATION_DIFF,
                               AtParameter(d.parameter),
                               DeterminationDiffPayload(d, bases)))
        return out
    if isinstance(result, NoTask):
        out.append(NO_TASK)
    elif not isinstance(result, NotRun):
        out.append(no_result(result, RunKind.DETERMINATION, None,
                             AtFile(WholeFile.SOLVER)))
    return out
