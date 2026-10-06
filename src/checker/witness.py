"""The checks over the witness file and the cases: the witness rules
(principles.md, under "Witnesses" and "Relational form") and the case conditions the
witness file is the evidence for (principles.md, under "Cases"), with what
`record` computes for an entry."""

from collections.abc import Sequence
from dataclasses import dataclass, replace

from checker.branches import groups_of, shows_apart, untaken_lines
from checker.finding import (
    AtCase,
    AtEntry,
    AtFile,
    AtLine,
    AtPair,
    Finding,
    Kind,
    RunKind,
    Where,
    WholeFile,
)
from checker.judged import (
    Misses,
    VerdictCase,
    base_constructors,
    concept_among,
    concept_case,
    differ,
    enumeration_failed,
    fit,
    is_timeout,
    model_named,
    no_result,
    representative,
    verdict_case,
)
from checker.payloads.witness import (
    ApproximatedWithoutWitness,
    ApproximationUnwitnessed,
    BranchUnwitnessed,
    CaseSet,
    ConceptPayload,
    ConceptUnenumeratedPayload,
    Condition,
    DriftPayload,
    DroppedPayload,
    ForeignUnderApproximated,
    NoDivergence,
    PointBranch,
    ReassignedMismatch,
    RelaxedNoClaim,
    RelaxedNotScene,
    SeparatesPayload,
    StandsElsewhere,
    SubsumedPayload,
    TaskAssignPayload,
    ListsNoCasePayload,
    UnjustifiedDropPayload,
    UnlistedPayload,
    UnseparatedPayload,
    VerdictOutputUnknown,
    WitnessEntryMissing,
)
from checker.readable import finding_of
from checker.runs import Runs
from engine import (
    RunFailure,
)
from engine.program import DeclId
from engine.quotes import guard, quotes
from solver.annotations import (
    Claim,
    ClaimKind,
    NamedVerdict,
    Plausibility,
    Verdict,
    VerdictWord,
    WitnessLine,
)
from solver.model import (
    Case,
    base_case,
    ConstructorBranch,
    DeriveBranch,
    DerivedAtStore,
    Solver,
    StoreBranch,
    StoredAtDerive,
    assignable,
    branch_witnesses,
    concept_branch,
    constructor_at,
    constructor_named,
    constructor_places,
    enumerates,
    every_base,
    is_concept_branch,
    is_concept_case,
    other_branches,
    unknown_strings,
    point_at,
)
from solver.names import (
    cover,
    denote,
    denoted_cases,
    model_of,
    name,
    names_in,
)
from solver.problems import (
    Fault,
    InSolver,
    InWitnessFile,
    Named,
    NameFault,
    ProblemKind,
    WitnessFileRole,
)
from solver.outcome import Grids, Outcome, is_result
from solver.solve import (
    PairRuns,
    at_once,
    branch_model,
    constructor_denoted,
    examples,
    pairs,
    taken,
    task_inputs,
)
from solver.witness import (
    AssignRows,
    Entry,
    GroupGrid,
    Groups,
    NoOutput,
    RejectedOutput,
    Resolutions,
    Undefined,
    WitnessFile,
)

# What the checks read


def _at(runs: Runs, entry: Entry) -> AtEntry:
    return AtEntry(entry.id, runs.file_role)


def _shown(runs: Runs, case: Case) -> bool:
    """A case whose findings the runs show: every case of the solver, and under the
    `witness --every-case` form a case whose base the solver's own
    `impl_choice` holds."""
    return runs.kept is None or any(k.base == case.base for k in runs.kept)


def _shown_cases(runs: Runs, cases: Sequence[Case] | None = None
                 ) -> list[Case]:
    """The cases of `cases`, the cases the checks read where None, whose
    findings the runs show (`_shown`)."""
    return [c for c in (runs.cases_or_none if cases is None else cases)
            if _shown(runs, c)]


def _emits_nothing(o: object) -> bool:
    """A run that gives no cell at the case."""
    return isinstance(o, Undefined) and isinstance(o.reason, NoOutput)


def _defined(o: object) -> bool:
    return isinstance(o, Grids)


def _records(expected: GroupGrid, got: Outcome) -> bool:
    """A group's grid records the outcome: its grid, its list of grids, one
    per resolution (history 1119), or null for undefined."""
    match expected:
        case Undefined():
            return isinstance(got, Undefined)
        case Resolutions(grids=gs):
            return isinstance(got, Grids) and got.grids == gs
        case _:
            return isinstance(got, Grids) and got.grids == (expected,)


def _judged_entries(runs: Runs) -> list[tuple[Entry, RejectedOutput]]:
    """The entries the checks read that hold a judged output
    (solver-file.md, under "Witness file") at an assignment the model places,
    each with that output."""
    return [(e, e.output) for e in runs.entries
            if isinstance(e.output, RejectedOutput)
            and not isinstance(runs.assignment(e), Fault)]


def _gives(output: RejectedOutput) -> Grids:
    """The outcome of a case that gives the judged output `output`: its
    one grid."""
    return Grids((output.grid,))


type Inputs = list[dict[Case, Outcome]]
"""The inputs a pair of cases is compared on, each as the outcome of every
case of the solver there."""


def _inputs(runs: Runs) -> Inputs:
    """What every case of the solver gives on each recorded input
    (`Runs.recorded`)."""
    return runs.outcomes_at(runs.cases_or_none, runs.recorded)


def _outcomes_of(runs: Runs, case: Case) -> list[Outcome]:
    """What `case` gives on each input `_inputs` reads, in its order."""
    return [runs.grid_outcome(g, a, case) for g, a in runs.recorded]


def _alone_outcomes(runs: Runs, cases: Sequence[Case]
                    ) -> dict[Case, list[Outcome]]:
    """`_outcomes_of` each case on its own (`Runs.alone`), the runs of
    every case on every input made at once."""
    alone = [runs.alone(a) for a in cases]
    at_once(lambda r: r.cases, alone)
    items = [(r, a, g, at) for a, r in zip(cases, alone, strict=True)
             for g, at in r.recorded]
    at_once(lambda i: i[0].grid_outcome(i[2], i[3], i[1]), items)
    return {a: _outcomes_of(r, a) for a, r in zip(cases, alone, strict=True)}


def _reads_inputs(runs: Runs) -> bool:
    """The equivalence and subsumption checks compare cases over the
    inputs of the task's witness file: a solver with no witness file
    compares none, and neither do the runs of a given file (`witness
    --file`), whose report has only the findings at its witnesses."""
    return runs.given is None and runs.solver.witness_file is not None


def _failures(got: Sequence[tuple[Case, Outcome | Fault]], run: RunKind,
              where: Where) -> list[Finding]:
    """The runs on one input that gave no result: a timeout per case whose
    run reached a limit, and the first failure of another kind, once per
    input."""
    out: list[Finding] = []
    failed = False
    for c, o in got:
        if is_timeout(o):
            out.append(no_result(o, run, c, where))
        elif not isinstance(o, Grids | Undefined | Fault) and not failed:
            failed = True
            out.append(no_result(o, run, None, where))
    return out


def _pair_failures(runs: Runs) -> list[Finding]:
    """The runs of the solver's cases on the task's pairs, at the stored
    assignment, that gave no result, each at its pair."""
    solver_cases = runs.cases_or_none
    task = runs.solver.given_task
    return [f for (pair, _ex), (g, a) in zip(examples(task), task_inputs(task),
                                            strict=True)
            for f in _failures([(c, runs.grid_outcome(g, a, c))
                                for c in solver_cases],
                               RunKind.PAIR, AtPair(pair))]


def _case_pairs(runs: Runs, case: Case) -> tuple[PairRuns, ...]:
    """`case` on every train and test pair at the stored assignment
    (`solver.solve.pairs`)."""
    got = pairs(runs.engine, runs.solver, runs.limits, [case],
                runs.outcomes_at)
    if not isinstance(got, tuple):
        raise ValueError("`pairs` of given cases enumerates no case")
    return got


def _agree(inputs: Inputs, a: Case, b: Case) -> bool | None:
    """Whether `a` and `b` agree on every input; None where a run of either
    gave no result on an input where they do not already differ, so no
    input is known to separate them."""
    unknown = False
    for got in inputs:
        x, y = got[a], got[b]
        if not is_result(x) or not is_result(y):
            unknown = True
            continue
        if differ(x, y):
            return False
    return None if unknown else True


def _subsumes(inputs: Inputs, a: Case, b: Case) -> bool:
    """No input shows `a` defined and differing from `b` (`shows_apart`),
    and some input shows `a` undefined where `b` is defined, so the two
    are not equivalent there (principles.md, under "Equivalence and
    subsumption"). An input with no result for either shows nothing, and
    then no subsumption is found."""
    apart = False
    for got in inputs:
        x, y = got[a], got[b]
        if not is_result(x) or not is_result(y):
            return False
        if shows_apart(x, y):
            return False
        if not _defined(x) and _defined(y):
            apart = True
    return apart


def _unseparated(runs: Runs, inputs: Inputs) -> list[tuple[Case, Case]]:
    """Each unordered pair of cases of the solver that agree on every input, in the
    order of the solver's cases. A solver with no witness file compares no
    pair."""
    if not _reads_inputs(runs):
        return []
    solver_cases = runs.cases_or_none
    return [(a, b) for i, a in enumerate(solver_cases) for b in solver_cases[i + 1:]
            if _agree(inputs, a, b) is True]


# The entries


@quotes("solver-file.md", "Witness file",
        "`programs/witnesses/<task_id>.wit.json` holds the witnesses the "
        "solver's cases are pinned to.")
@quotes("solver-file.md", "Witness file",
        "the fewest names whose cases together are exactly the cases that "
        "give this output")
@quotes("solver-file.md", "Witness file",
        "the parameters the witness reassigns, which may include a `@store` "
        "line's relation")
@quotes("principles.md", "Witnesses",
        "**verdict**: the annotator's judgment of the output that the "
        "generator would pair with the witness.")
def check_entry_outputs(solver: Solver, runs: Runs) -> list[Finding]:
    """Per entry of the witness file: the cases a group names whose output
    is not the group's grid (`drift`), the solver's cases no group names
    (`unlisted`), the group names that denote none of the solver's cases
    (`lists-no-case`), an `assign` whose rows do not have the columns of the
    parameter or `@store` relation it names (`assign`), and the runs that
    give no result. An entry whose id names a case of the solver need not
    list it. A given file is an Analyze file, which lists no case of the
    solver, and it has no `unlisted` finding; an entry of it whose `assign`
    names what the model cannot place runs at the `assign` of the task's own
    entry of its id (`task-assign`). Where the run that enumerates the
    solver's cases fails, that failure is the one finding, since no check of
    the report has cases to read."""
    solver_cases = runs.cases
    if not isinstance(solver_cases, tuple):
        return [enumeration_failed(solver_cases)]
    out: list[Finding] = []
    for entry in runs.entries:
        entry, noted = _placed(solver, runs, entry)
        out += noted
        if entry is None:
            continue
        out += _failures([(c, runs.outcome(entry, c)) for c in solver_cases],
                         RunKind.WITNESS, _at(runs, entry))
        if isinstance(entry.output, Groups):
            out += _groups(solver, runs, entry, solver_cases)
    return out


def _placed(solver: Solver, runs: Runs, entry: Entry
            ) -> tuple[Entry | None, list[Finding]]:
    """The entry as it runs, None where its assignment cannot be placed,
    and the findings that say so."""
    at = runs.assignment(entry)
    if isinstance(at, Fault):
        task = solver.witness_file
        task_entry = None if runs.given is None or task is None \
            else task.entry(entry.id)
        values = _unknown_constants(solver, entry)
        if values is not None and task_entry is not None \
                and not isinstance(runs.assignment(task_entry),
                                   Fault):
            return replace(entry, assign=task_entry.assign), [Finding(
                Kind.TASK_ASSIGN, _at(runs, entry),
                TaskAssignPayload(values, task_entry.id, task_entry.assign))]
        known = any(p.kind == at.kind and p.place == at.place
                    for p in solver.problems)
        return None, [] if known and runs.given is None \
            else [finding_of(at)]
    return entry, []


def _unknown_constants(solver: Solver, entry: Entry
                       ) -> tuple[tuple[str, str], ...] | None:
    """Each string of the entry's `assign` that names nothing
    (`solver.model.unknown_strings`), with its key; None where a key names
    no parameter or stored relation, or every string names something."""
    out: list[tuple[str, str]] = []
    for key, value in entry.assign:
        if not assignable(solver, key):
            return None
        if isinstance(value, AssignRows):
            out += [(key, s) for s in unknown_strings(solver, value.rows)]
    return tuple(out) or None


def _case_set(runs: Runs, cases: Sequence[Case]) -> CaseSet:
    """`cases` with the names that print them: a lone case's name, else
    the fewest names that denote exactly them among the solver's cases
    (`solver.names.cover`)."""
    solver = runs.solver
    names = (name(solver, cases[0]),) if len(cases) == 1 \
        else cover(solver, cases, runs.cases_or_none)
    return CaseSet(tuple(cases), names)


def _merged(rows: Sequence[tuple[Case, object, Outcome]]
            ) -> list[tuple[tuple[Case, ...], object, Outcome]]:
    """One row per distinct expected and actual pair, with the cases that
    give it, in the order the cases come in."""
    out: list[tuple[list[Case], object, Outcome]] = []
    for case, want, got in rows:
        for cases, w, g in out:
            if w == want and g == got:
                cases.append(case)
                break
        else:
            out.append(([case], want, got))
    return [(tuple(cs), w, g) for cs, w, g in out]


def _groups(solver: Solver, runs: Runs, entry: Entry,
            solver_cases: Sequence[Case]) -> list[Finding]:
    """The groups of one entry read against the runs: a group's names
    denote sets of the solver's cases (`solver.names.denoted_cases`), and
    together the groups name each case once, by the group of its output
    (solver-file.md, under "Witness file"). A case a name denotes whose output
    is not its group's grid is `drift`: the name reaches into another group. A case
    no group names is `unlisted`, and a name that denotes none of the
    solver's cases `lists-no-case`. Under the `witness --every-case` form the
    names denote the solver's cases still, those the solver's own
    `impl_choice` holds (`_shown`): a dropped case is judged by
    `check_case_conditions` alone (solver-file.md, under "Witness file"). A
    given file's name is read as the case that stands for the model of the
    branches it names (`_model_set`):
    the file gives each branch's output, and no other case is compared
    with it (procedure.md, under "Analyze after the concept" and "Witness").
    The names denote cases of the solver, and the `drift` and `unlisted`
    findings are on `solver_cases`, the witnessed cases, alone."""
    assert isinstance(entry.output, Groups)
    witnessed = frozenset(solver_cases)
    every = runs.solver_cases
    solver_cases = _shown_cases(runs, every if isinstance(every, tuple)
                                else solver_cases)
    where = _at(runs, entry)
    drift: list[tuple[Case, object, Outcome]] = []
    problems: list[Finding] = []
    listing_none: list[str] = []
    named: set[Case] = set()
    for group in entry.output.groups:
        in_group: set[Case] = set()
        for n in group.cases:
            task_file = runs.file_role is WitnessFileRole.TASK
            cases = denoted_cases(solver, n, solver_cases) \
                if task_file else _model_set(solver, n, solver_cases)
            if isinstance(cases, NameFault):
                # The task's file's names are read with the model; a given
                # file's are read here.
                if not task_file:
                    problems.append(finding_of(cases.at(InWitnessFile(
                        entry.id, runs.file_role))))
            elif not cases:
                listing_none.append(n)
            in_group |= set() if isinstance(cases, NameFault) else cases
        named |= in_group
        for case in solver_cases:
            if case not in in_group or case not in witnessed:
                continue
            got = runs.outcome(entry, case)
            if not is_result(got):
                continue
            if not _records(group.grid, got):
                drift.append((case, group.grid, got))
    out: list[Finding] = []
    for cases, want, got in _merged(drift):
        assert isinstance(want, (tuple, Resolutions, Undefined))
        out.append(Finding(Kind.DRIFT, where, DriftPayload(
            _case_set(runs, cases), want, got)))
    out += problems
    if listing_none:
        out.append(Finding(Kind.LISTS_NO_CASE, where,
                           ListsNoCasePayload(tuple(listing_none))))
    if runs.given is not None or _unread_names(solver, entry):
        return out
    own = _own(solver, entry, solver_cases)
    rows: list[tuple[Case, object, Outcome]] = []
    for c in solver_cases:
        if c in named or c in own or c not in witnessed:
            continue
        got = runs.outcome(entry, c)
        if not is_result(got):
            continue
        rows.append((c, None, got))
    out += [Finding(Kind.UNLISTED, where,
                    UnlistedPayload(_case_set(runs, cases), got))
            for cases, _w, got in _merged(rows)]
    return out


def _model_set(solver: Solver, text: str, solver_cases: Sequence[Case]
               ) -> frozenset[Case] | NameFault:
    """A given file's group name read as a branch's model
    (procedure.md, under "Analyze after the concept" and "Witness"): the one
    case of the solver's cases that stands for that model
    (`solver.solve.branch_model`; solver-file.md, under "Cases"), none where
    no case takes the branch; the problem where the name denotes nothing."""
    d = denote(solver, text)
    if isinstance(d, NameFault):
        return d
    model = branch_model(solver, solver_cases, d)
    return frozenset() if model is None else frozenset({model})


def _own(solver: Solver, entry: Entry, solver_cases: Sequence[Case]
         ) -> frozenset[Case]:
    """The cases the entry's id denotes, which its groups need not name;
    none where the id is no name."""
    got = denoted_cases(solver, entry.id, solver_cases)
    return frozenset() if isinstance(got, NameFault) else got


def _unread_names(solver: Solver, entry: Entry) -> bool:
    """A group of the entry holds a name that denotes no model: which cases
    the entry lists is then not known, so no case is found unlisted and no
    `separates` name found missing."""
    return isinstance(entry.output, Groups) and any(
        isinstance(denote(solver, n), NameFault)
        for g in entry.output.groups for n in g.cases)


@quotes("principles.md", "Witnesses",
        "`other`: an output that no case produces.")
@quotes("solver-file.md", "Witness file",
        "when the verdict is other: the annotator's judged output")
def check_other_verdict(solver: Solver, runs: Runs) -> list[Finding]:
    """An entry of a judged output on which cases of the solver give that
    output is a finding, one per entry with the cases that give it."""
    solver_cases = _shown_cases(runs)
    out: list[Finding] = []
    for entry, judged in _judged_entries(runs):
        cases = tuple(c for c in solver_cases
                      if runs.outcome(entry, c) == _gives(judged))
        if cases:
            out.append(Finding(Kind.DRIFT, _at(runs, entry), DriftPayload(
                _case_set(runs, cases), judged, _gives(judged))))
    return out


@quotes("procedure.md", "Witness",
        "Run the solver against the Analyze file: `uv run python "
        "scripts/run_dl.py witness <task_id> --file "
        "work/task/<task_id>/witnesses.json`.")
@quotes("procedure.md", "Witness",
        "A branch whose model's output differs from the one the Analyze file "
        "gives the branch is an error in the solver to fix, unless the "
        "Analyze file erred; then it goes in the review as a departure, "
        "with why.")
def check_concept_output(solver: Solver, runs: Runs) -> list[Finding]:
    """On an entry of a given file with a judged output, the concept case
    gives that output; an entry where it gives another is a finding. Only
    a given file is read. Its kind, `concept`, is a hint outside
    `FAILING`. Where no case read is the concept case, the enumeration's
    failure or `check_concept_enumerated` is the finding, and this check
    gives none."""
    if runs.given is None:
        return []
    concept = concept_case(solver, runs.cases_or_none)
    if concept is None:
        return []
    out: list[Finding] = []
    for entry, judged in _judged_entries(runs):
        got = runs.outcome(entry, concept)
        if not is_result(got):
            continue
        if got != _gives(judged):
            out.append(Finding(Kind.CONCEPT, _at(runs, entry),
                               ConceptPayload(judged.grid, got)))
    return out


@guard("A name in an entry's `separates` text that denotes a case of the "
       "solver no group of the entry names.")
def check_separates(solver: Solver, runs: Runs) -> list[Finding]:
    """An entry's `separates` text names the models its input separates
    (solver-file.md, under "Witness file"), and each group lists the cases it
    records (solver-file.md, under "Witness file"): a name in the text denotes
    a model, the named branches with every other point at its concept branch
    (principles.md, under "Choice points and open parameters"), and where that
    model is a case of the solver no group names, the name is a finding. An
    entry of a judged output has no groups, and an entry need not name the
    cases its id names; a group's names denote sets of cases
    (`solver.names.denoted_cases`). No principle states this: the text is
    prose for the reader of the file.
    Its kind, `separates`, is a hint outside `FAILING`."""
    solver_cases = runs.cases_or_none
    out: list[Finding] = []
    for entry in runs.entries:
        if not isinstance(entry.output, Groups) \
                or _unread_names(solver, entry):
            continue
        written = {n for g in entry.output.groups for n in g.cases}
        named = set(_own(solver, entry, solver_cases))
        for n in written:
            got = denoted_cases(solver, n, solver_cases)
            if not isinstance(got, NameFault):
                named |= got
        for n in names_in(entry.separates):
            if n in written:
                continue
            case = model_named(solver, n, solver_cases)
            if case is None or isinstance(case, NameFault) \
                    or case not in solver_cases or case in named \
                    or not _shown(runs, case):
                continue
            out.append(Finding(Kind.SEPARATES, _at(runs, entry),
                               SeparatesPayload(n)))
    return out


# The `@witness` lines


def _merged_witnesses(solver: Solver) -> list[WitnessLine]:
    """The `@witness` lines, one per id, the first line's, with the
    `@reassigned` and `@relaxed` lines of every line of the id."""
    out: dict[str, WitnessLine] = {}
    for w in solver.annotations.witnesses:
        if w.id in out:
            first = out[w.id]
            out[w.id] = replace(
                first,
                relaxed=first.relaxed + tuple(
                    s for s in w.relaxed if s not in first.relaxed),
                reassigned=first.reassigned + tuple(
                    s for s in w.reassigned if s not in first.reassigned))
        else:
            out[w.id] = w
    return list(out.values())


def _header_claims(solver: Solver, runs: Runs) -> tuple[Claim, ...] | Fault:
    """The claims of the header, a sibling's being its representative's
    (solver-file.md, under "Header"); the model's fault where the representative
    has no solver file, since its claims are then unknown."""
    def header(s: Solver) -> tuple[Claim, ...]:
        return tuple(c for c in s.annotations.claims if c.constructor is None)

    rep = solver.annotations.representative
    if rep is None or rep.task_id == solver.stem:
        return header(solver)
    other = representative(solver, runs.engine)
    if other is None:
        missing = solver.fault(ProblemKind.REPRESENTATIVE_MISSING)
        assert missing is not None, \
            "a representative the header names is loaded or missing"
        return missing
    return header(solver) + header(other)


@quotes("principles.md", "Witnesses",
        "**divergence witness**: an input on which one of these holds:")
@quotes("principles.md", "Witnesses",
        "A witness breaks a scene claim when the concept case's claim, read "
        "at the assignment the witness stands at, is false of it.")
@quotes("procedure.md", "Witness",
        "`@relaxed` for the scene claim it breaks, which rules out "
        "`ordinary`, and `@reassigned` for each parameter that the assignment "
        "it stands at changes.")
def check_witness_lines(solver: Solver, runs: Runs) -> list[Finding]:
    """The `@witness` lines and the witness file agree: each line's id is an
    entry of the file; the `@reassigned` lines of a witness name the
    parameters its `assign` changes; each `@relaxed` line of a `@witness`,
    `@derive` or `@store` line names a scene claim of the header.
    A given file is not the task's, and its entries are not read here; with no
    witness file, there is nothing to compare. Where the header's claims are
    unknown (`_header_claims`), no `@relaxed` line is checked, and the fault
    that says so is `fault_findings`'s."""
    if runs.given is not None or solver.witness_file is None:
        return []
    claims = _header_claims(solver, runs)
    kinds = None if isinstance(claims, Fault) \
        else {c.slug: c.kind for c in claims}
    out: list[Finding] = []

    def relaxed(where: Where, slugs: Sequence[str]) -> None:
        if kinds is None:
            return
        for slug in slugs:
            kind = kinds.get(slug)
            if kind == ClaimKind.SCENE:
                continue
            out.append(Finding(Kind.ANNOTATION, where,
                               RelaxedNoClaim(slug) if kind is None
                               else RelaxedNotScene(slug, kind)))

    for w in _merged_witnesses(solver):
        entry = runs.entry(w.id)
        if entry is None:
            out.append(Finding(Kind.ANNOTATION, AtLine(w.line),
                               WitnessEntryMissing(w.id)))
        else:
            assigned = tuple(k for k, _v in entry.assign)
            if sorted(w.reassigned) != sorted(assigned):
                out.append(Finding(Kind.ANNOTATION, _at(runs, entry),
                                   ReassignedMismatch(w.id, w.reassigned,
                                                      assigned)))
        relaxed(_at(runs, entry) if entry is not None else AtLine(w.line),
                w.relaxed)
    for line in (*solver.annotations.derives, *solver.annotations.stores):
        relaxed(AtLine(line.line), line.relaxed)
    return out


def _verdict_case(solver: Solver, runs: Runs, verdict: Verdict
                  ) -> VerdictCase:
    """The case a `@witness` line's verdict denotes
    (`checker.judged.verdict_case`)."""
    return verdict_case(solver, verdict, runs.cases_or_none, None)


@quotes("principles.md", "Witnesses",
        "`concept`: the concept case's output. the branch's name: the output "
        "of that branch's model. `any`: the output of any case defined on the "
        "witness.")
@quotes("principles.md", "Choice points and open parameters",
        "A branch's model takes that branch, and the concept branch at every "
        "other choice point it takes.")
def check_verdict_denotes(solver: Solver, runs: Runs) -> list[Finding]:
    """A verdict of a `@witness`, `@derive` or `@store` line whose name
    denotes a model that neither the runner holds nor `model_of` can build
    denotes an output no run gives, and is a finding. A name that denotes no
    model is a fault, which `fault_findings` reports."""
    if not isinstance(runs.cases, tuple):
        return []
    a = solver.annotations
    untaken = untaken_lines(runs, solver)
    out: list[Finding] = []
    for line in (*a.witnesses, *a.derives, *a.stores):
        v = line.verdict
        if isinstance(v, NamedVerdict) and line.line not in untaken \
                and _verdict_case(solver, runs, v) is None:
            out.append(Finding(Kind.ANNOTATION, AtLine(line.line),
                               VerdictOutputUnknown(v)))
    return out


def _departs(runs: Runs, verdict: Verdict, named: VerdictCase,
             case: Case, entry: Entry | None
             ) -> bool | tuple[Case, RunFailure]:
    """The witness shows `case` giving an output other than the verdict's
    (solver-file.md, under "Header"): `other` every case's, `any` no case's,
    and otherwise where the verdict's case, `named`, gives another output on
    the witness. An entry whose assignment the model cannot place shows
    nothing, which `fault_findings` reports. Where a run reached a limit or
    failed, the output is not known, and the run's case and failure stand in
    its place."""
    if verdict == VerdictWord.OTHER:
        return True
    if not isinstance(named, Case) or case == named or entry is None:
        return False
    outs = [(c, runs.outcome(entry, c)) for c in (case, named)]
    if any(isinstance(o, Fault) for _, o in outs):
        return False
    for c, o in outs:
        if not isinstance(o, Fault) and not is_result(o):
            return c, o
    return all(differ(o, outs[0][1]) for _, o in outs[1:])


@quotes("principles.md", "Relational form",
        "The approximation disagrees with the rule on some such input, and "
        "that input is a divergence witness.")
@quotes("solver-file.md", "Header",
        "A witness under an `@approximated:` line is not `foreign`.")
@quotes("solver-file.md", "Header",
        "Each case that runs the approximation has a witness on which its "
        "output is not the verdict's.")
def check_approximation_witness(solver: Solver, runs: Runs
                                ) -> list[Finding]:
    """A `foreign` witness under an `@approximated:` line, and a case that
    runs the approximation with no witness on which its output is not the
    verdict's. A case whose branch carries a `@rule` line of the claim's
    slug restates the claim, and the approximation does not run on it."""
    solver_cases = runs.cases_or_none
    restated: dict[str, set[str]] = {}
    for c in solver.annotations.claims:
        if c.kind == ClaimKind.RULE and c.constructor is not None:
            restated.setdefault(c.slug, set()).add(c.constructor)
    out: list[Finding] = []
    for c in solver.annotations.claims:
        if c.constructor is not None or not c.approximated:
            continue
        witnesses = [w for a in c.approximated for w in a.witnesses]
        if not witnesses:
            out.append(Finding(Kind.ANNOTATION, AtLine(c.line),
                               ApproximatedWithoutWitness(c.kind, c.slug)))
            continue
        for w in witnesses:
            if w.plausibility == Plausibility.FOREIGN:
                out.append(Finding(Kind.ANNOTATION, AtLine(w.line),
                                   ForeignUnderApproximated(w.id, c.kind,
                                                            c.slug)))
        names = restated.get(c.slug, set())
        named = [_verdict_case(solver, runs, w.verdict)
                 for w in witnesses]
        for case in solver_cases:
            if names & set(base_constructors(case.base)) \
                    or not _shown(runs, case):
                continue
            departs = False
            failed: tuple[Case, RunFailure] | None = None
            for w, n in zip(witnesses, named):
                got = _departs(runs, w.verdict, n, case, runs.entry(w.id))
                if got is True:
                    departs = True
                    break
                if failed is None and got is not False:
                    failed = got
            if departs:
                continue
            if failed is not None:
                out.append(no_result(failed[1], RunKind.WITNESS, failed[0],
                                     AtLine(c.line)))
                continue
            out.append(Finding(Kind.ANNOTATION, AtLine(c.line),
                               ApproximationUnwitnessed(c.kind, c.slug,
                                                        case)))
    return out


@dataclass(frozen=True)
class _BranchWitness:
    """A `@witness` line of a branch other than its point's first: the
    branch's model and the model of the point's first branch
    (principles.md, under "Choice points and open parameters" and "Witnesses")."""

    line: WitnessLine
    branch: ConstructorBranch
    model: Case
    first: Case


def _branch_witnesses(solver: Solver, runs: Runs
                      ) -> tuple[list[_BranchWitness], list[Fault]]:
    """Each `@witness` line in the branch comment of a constructor other
    than its point's first, under no `@approximated:` line, whose verdict
    denotes another model than the branch's: a witness of the concept
    case stands under the branch its verdict denotes (procedure.md, under
    "Witness").
    A line whose branch or first branch has no model to build is not
    here. A line in the comment of a constructor that is at no choice
    point is a fault: the name of its branch denotes no case."""
    choice = solver.choice
    solver_cases = runs.cases_or_none
    out: list[_BranchWitness] = []
    faults: list[Fault] = []
    for w in solver.annotations.witnesses:
        if w.approximates is not None or w.constructor is None:
            continue
        if choice is None or constructor_named(choice, w.constructor) is None:
            faults.append(Fault(ProblemKind.NAME_DENOTES_NO_CASE,
                                InSolver(w.line), Named(w.constructor)))
            continue
        place = next(((p, c) for p, c in constructor_places(
            choice, w.constructor) if not is_concept_branch(p, c.name)), None)
        if place is None:
            continue
        point, ctor = place
        d_model = constructor_denoted(choice, point, ctor)
        d_first = constructor_denoted(choice, point, concept_branch(point))
        model = model_of(solver, d_model, solver_cases)
        first = model_of(solver, d_first, solver_cases)
        if model is None or first is None:
            continue
        if _verdict_case(solver, runs, w.verdict) == model:
            continue
        out.append(_BranchWitness(w, ctor, model, first))
    return out, faults


@quotes("principles.md", "Witnesses",
        "A branch's witnesses are divergence witnesses between its model and "
        "the concept branch's model.")
@quotes("style.md", "Cases",
        "**Other branches.** Every other branch has at least one `@witness` "
        "line.")
def check_branches_witnessed(solver: Solver, runs: Runs) -> list[Finding]:
    """A branch of a choice point other than its concept branch whose branch
    comment holds no `@witness` line is a finding at the line the branch
    starts on, one per branch where several start on one line. The Witness
    operation writes those lines with the witness file, so a solver with no
    witness file is not held to it, and a given file is not the task's."""
    choice = solver.choice
    if choice is None or runs.given is not None \
            or solver.witness_file is None:
        return []
    out: list[Finding] = []
    seen: set[DeclId] = set()
    for p in choice.points:
        if p.declaration in seen:
            continue
        seen.add(p.declaration)
        out += [Finding(Kind.ANNOTATION, AtLine(c.line),
                        BranchUnwitnessed(c.name))
                for c in other_branches(p)
                if not branch_witnesses(solver, c.name)]
    return out


@quotes("principles.md", "Witnesses",
        "A branch's witnesses are divergence witnesses between its model and "
        "the concept branch's model.")
@quotes("principles.md", "Equivalence and subsumption",
        "Two assignments agree when, on every input, the two models give the "
        "same output or neither is defined.")
def check_branch_witness(solver: Solver, runs: Runs) -> list[Finding]:
    """A branch's `@witness` line on whose entry the branch's model and the
    concept branch's model give the same output, or neither is defined, is a
    finding; a run with no result shows nothing. The line is judged whether
    or not the solver's `impl_choice` holds the model, so `witness
    --every-case` judges it as `witness` does. A `@witness` line in the
    comment of a constructor at no choice point is a fault
    (`_branch_witnesses`)."""
    witnesses, faults = _branch_witnesses(solver, runs)
    out = [finding_of(f) for f in faults]
    for bw in witnesses:
        entry = runs.entry(bw.line.id)
        if entry is None:
            continue
        a, b = runs.outcome(entry, bw.model), runs.outcome(entry, bw.first)
        if not is_result(a) or not is_result(b):
            continue
        if not differ(a, b):
            out.append(Finding(Kind.ANNOTATION, AtLine(bw.line.line),
                               NoDivergence(entry.id, bw.model, bw.first,
                                            bw.branch)))
    return out


@quotes("principles.md", "Witnesses",
        "A witness stands at this task's stored assignment when the model it "
        "is for is defined there and differs there from what it is separated "
        "from.")
@quotes("principles.md", "Witnesses",
        "The model a witness is for is the branch's model for a branch's "
        "witness, the concept case's model for a witness of the concept case")
def check_witness_assignment(solver: Solver, runs: Runs) -> list[Finding]:
    """The model a witness is for: a branch's model for a branch's witness,
    from the point's first branch; the concept case's otherwise, from the
    output the verdict denotes, or from the judged output for `other`. A
    witness whose `assign` changes a parameter, where that model is defined
    at the stored assignment and differs there from what the witness
    separates it from, is a finding. A witness is judged at the
    assignment its entry gives, the stored one where it gives none, and
    no other assignment is searched."""
    if runs.given is not None:
        return []
    solver_cases = runs.cases_or_none
    concept = concept_case(solver, solver_cases)
    branch = {bw.line.line: bw for bw in _branch_witnesses(solver, runs)[0]}
    out: list[Finding] = []
    for w in solver.annotations.witnesses:
        entry = runs.entry(w.id)
        if entry is None or not entry.assign \
                or isinstance(runs.assignment(entry), Fault):
            continue
        against: list[Case] = []
        judged: RejectedOutput | None = None
        if w.line in branch:
            model, against = branch[w.line].model, [branch[w.line].first]
        elif concept is None:
            continue
        else:
            model = concept
            if w.verdict == VerdictWord.OTHER:
                if not isinstance(entry.output, RejectedOutput):
                    continue
                judged = entry.output
            else:
                named = _verdict_case(solver, runs, w.verdict)
                if not isinstance(named, Case) or named == model:
                    continue
                against = [named]
        stored = replace(entry, assign=())
        outs = [runs.outcome(stored, c) for c in (model, *against)]
        if any(not is_result(o) for o in outs) or not _defined(outs[0]):
            continue
        if all(differ(o, outs[0]) for o in outs[1:]) and (
                judged is None or outs[0] != _gives(judged)):
            out.append(Finding(Kind.ANNOTATION, AtLine(w.line),
                               StandsElsewhere(
                                   w.id, tuple(k for k, _v in entry.assign))))
    return out


# The case conditions


@dataclass(frozen=True)
class _ChoiceAt:
    """A point of `Choice`, by its path."""

    path: tuple[str, ...]


@dataclass(frozen=True)
class _DeriveAt:
    """A `@derive` point, by its parameter."""

    parameter: str


@dataclass(frozen=True)
class _StoreAt:
    """A `@store` point, by the relation as its lines spell it."""

    relation: str


type _Point = _ChoiceAt | _DeriveAt | _StoreAt
"""A choice point of the solver."""


def _point_branches(solver: Solver, case: Case
                    ) -> dict[_Point, PointBranch | None]:
    """The branch `case` takes at each choice point of the solver, in the
    order of the points: None at a point of `Choice` its base does not
    reach, `<param>=stored` at a `@derive` point where it takes no
    `@derive` branch, and `<rel>=derived` at a `@store` point where it
    takes no `@store` branch."""
    out: dict[_Point, PointBranch | None] = {}
    choice = solver.choice
    if choice is not None and case.base is not None:
        for p in choice.points:
            name = constructor_at(choice, case.base, p)
            out[_ChoiceAt(p.path)] = None if name is None else next(
                c for c in p.constructors if c.name == name)
    for b in solver.branches:
        if isinstance(b, DeriveBranch):
            key: _Point = _DeriveAt(b.parameter)
            if key not in out:
                out[key] = StoredAtDerive(b.parameter)
            if b in case.branches:
                out[key] = b
        elif isinstance(b, StoreBranch):
            out[_StoreAt(b.spelled)] = b if b in case.branches \
                else DerivedAtStore(b)
    return out


def _concept_only(solver: Solver, side: Sequence[PointBranch | None]
                  ) -> bool:
    """Whether a side of a difference takes no constructor other than its
    point's concept branch."""
    choice = solver.choice
    return all(not isinstance(x, ConstructorBranch) or (
        choice is not None and is_concept_branch(point_at(choice, x), x.name))
        for x in side)


type _Difference = tuple[tuple[_Point, ...],
                         tuple[PointBranch | None, ...],
                         tuple[PointBranch | None, ...]]
"""The points at which two cases differ, and the branch each takes
there."""


def _differing(solver: Solver, runs: Runs, a: Case, b: Case) -> int:
    """How many choice points `a` and `b` take different branches at."""
    return len(_points_apart(_point_branches(solver, a),
                             _point_branches(solver, b)))


def _points_apart(pa: dict[_Point, PointBranch | None],
                  pb: dict[_Point, PointBranch | None]) -> tuple[_Point, ...]:
    """The points of `pa` at which two cases, taking the branches `pa`
    and `pb` (`_point_branches`), take different ones."""
    return tuple(k for k in pa if pa[k] != pb.get(k))


def _spanning(solver: Solver, runs: Runs,
              pairs: Sequence[tuple[Case, Case]]
              ) -> set[tuple[Case, Case]]:
    """Pairs of `pairs` that join the cases of each class of agreeing
    cases, those that differ at the fewest points first: every other pair
    agrees through them."""
    order = sorted(range(len(pairs)), key=lambda i: (
        _differing(solver, runs, *pairs[i]), i))
    parent: dict[Case, Case] = {}

    def find(c: Case) -> Case:
        while parent.setdefault(c, c) != c:
            c = parent[c]
        return c

    out: set[tuple[Case, Case]] = set()
    for i in order:
        a, b = pairs[i]
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra
            out.add(pairs[i])
    return out


def _by_difference(solver: Solver, runs: Runs,
                   pairs: Sequence[tuple[Case, Case]],
                   needed: set[tuple[Case, Case]], directed: bool,
                   kind: Kind) -> list[Finding]:
    """One finding of `kind` per branch difference among `pairs` that some
    pair of `needed` holds (history "One finding per unseparated pair of
    bases", grouped by the branches on which the two differ): the pairs
    whose two cases differ by the same branches at the same points, named
    by the fewest names that cover the branches both take elsewhere
    (`solver.names.cover`), with the count of pairs. A pair is `(a, b)`
    in the order the finding states it where `directed`, else in either
    order, stated from the side that takes a constructor other than a
    concept branch where one side alone does."""
    shown = _shown_cases(runs)
    points = {c: _point_branches(solver, c) for c in shown}
    groups: dict[_Difference, list[Case]] = {}
    wanted: set[_Difference] = set()
    for a, b in pairs:
        pa, pb = points[a], points[b]
        at = _points_apart(pa, pb)
        side_a = tuple(pa[k] for k in at)
        side_b = tuple(pb[k] for k in at)
        key, case = (at, side_a, side_b), a
        flipped = (at, side_b, side_a)
        if not directed and (flipped in groups or (
                key not in groups and _concept_only(solver, side_a)
                and not _concept_only(solver, side_b))):
            key, case = flipped, b
        groups.setdefault(key, []).append(case)
        if (a, b) in needed:
            wanted.add(key)
    out: list[Finding] = []
    for (at, side_a, side_b), chosen in groups.items():
        if (at, side_a, side_b) not in wanted:
            continue

        def rest(c: Case) -> tuple[PointBranch | None, ...]:
            return tuple(v for k, v in points[c].items() if k not in at)

        def taking(side: tuple[PointBranch | None, ...]) -> list[Case]:
            return [c for c in shown
                    if tuple(points[c][k] for k in at) == side]

        named, other = side_a, side_b
        if _concept_only(solver, side_a) \
                and not _concept_only(solver, side_b):
            twin = {rest(c): c for c in taking(side_b)}
            chosen = [twin[rest(c)] for c in chosen]
            named, other = side_b, side_a
        partners = {rest(c) for c in taking(other)}
        universe = [c for c in taking(named) if rest(c) in partners]
        names = () if set(chosen) == set(universe) \
            else cover(solver, chosen, universe)
        order = {c: i for i, c in enumerate(universe)}
        contexts = CaseSet(tuple(sorted(chosen, key=order.__getitem__)),
                           names)
        parts_a = tuple(x for x in side_a if x is not None)
        parts_b = tuple(x for x in side_b if x is not None)
        payload = UnseparatedPayload(parts_a, parts_b, contexts,
                                     len(universe)) \
            if kind is Kind.UNSEPARATED \
            else SubsumedPayload(parts_a, parts_b, contexts, len(universe))
        out.append(Finding(kind, AtFile(WholeFile.SOLVER), payload))
    return out


@quotes("principles.md", "Cases",
        "**Equivalence.** The model is not equivalent to the model of another "
        "case.")
@quotes("procedure.md", "Witness",
        "`witness` without `--file` reports a pair of cases that no witness "
        "separates.")
def check_equivalence(solver: Solver, runs: Runs) -> list[Finding]:
    """The evidence is the witness file and the task's pairs, and no input
    the tool builds: two cases of the solver that agree on every entry and
    every pair are a pair no witness separates. One finding per branch difference among those pairs
    (`_by_difference`); a pair where some run gave no result is not
    reported, and each run on a pair that gave no result is reported at its
    pair (the entries' runs are `check_entry_outputs`'s)."""
    failures = _pair_failures(runs) if _reads_inputs(runs) else []
    return failures + _unseparated_findings(solver, runs)


def _unseparated_findings(solver: Solver, runs: Runs, every: bool = False
                          ) -> list[Finding]:
    """One finding per branch difference among the pairs of shown cases
    no witness separates (`_unseparated`), each pair of the finding's
    contexts that differs at it alone (`_spanning`), every pair with
    `every`."""
    pairs = [(a, b) for a, b in _unseparated(runs, _inputs(runs))
             if _shown(runs, a) and _shown(runs, b)]
    return _by_difference(solver, runs, pairs, set(pairs) if every
                          else _spanning(solver, runs, pairs), False,
                          Kind.UNSEPARATED)


def _subsumers(solver: Solver, inputs: Inputs, a: Case,
               others: Sequence[Case]) -> list[Case]:
    """The cases of `others` that subsume `a`, less each that subsumes
    another of them; none for the concept case (principles.md, under "Cases")."""
    if is_concept_case(solver, a):
        return []
    partners = [b for b in others if b != a and _subsumes(inputs, a, b)]
    return [b for b in partners
            if not any(_subsumes(inputs, c, b) for c in partners if c != b)]


@quotes("principles.md", "Cases",
        "**Subsumption.** The model of a case other than the concept case is "
        "not subsumed by the model of another case.")
@quotes("procedure.md", "Witness",
        "`witness` without `--file` reports each case that no run shows "
        "defined and differing from another case.")
def check_subsumption(solver: Solver, runs: Runs) -> list[Finding]:
    """Over the witness file and the task's pairs, a case of the solver that
    no run shows defined and differing from another case of the solver,
    where some run shows the two apart, is subsumed by it; a pair no witness
    separates is `check_equivalence`'s alone. One finding per branch
    difference among those pairs (`_by_difference`), each pair a subsumed
    case and a case that subsumes it and subsumes no other that does."""
    if not _reads_inputs(runs):
        return []
    return _subsumed_findings(solver, runs)


def _subsumed_findings(solver: Solver, runs: Runs, every: bool = False
                       ) -> list[Finding]:
    """One finding per branch difference among the pairs of a shown case
    and a case that subsumes it (`_subsumed_pairs`), each subsumed case
    with its nearest subsumer, every pair with `every`."""
    pairs, nearest = _subsumed_pairs(solver, runs)
    return _by_difference(solver, runs, pairs, set(pairs) if every
                          else nearest, True, Kind.SUBSUMED)


def _same(runs: Runs, inputs: Inputs) -> set[frozenset[Case]]:
    """The pairs of cases no witness separates (`_unseparated`), each as
    a set."""
    return {frozenset(p) for p in _unseparated(runs, inputs)}


def _subsumed_pairs(solver: Solver, runs: Runs
                    ) -> tuple[list[tuple[Case, Case]], set[tuple[Case, Case]]]:
    """Each shown case with each case that subsumes it (`_subsumers`),
    and of those pairs, each subsumed case with the subsumer that differs
    from it at the fewest points."""
    inputs = _inputs(runs)
    same = _same(runs, inputs)
    solver_cases = _shown_cases(runs)
    pairs: list[tuple[Case, Case]] = []
    nearest: set[tuple[Case, Case]] = set()
    for a in solver_cases:
        others = [b for b in solver_cases if frozenset((a, b)) not in same]
        by = _subsumers(solver, inputs, a, others)
        pairs += [(a, b) for b in by]
        if by:
            nearest.add((a, min(by, key=lambda b: _differing(
                solver, runs, a, b))))
    return pairs, nearest


TRY_ID = "try"
"""The id of the candidate entry `witness --try` runs."""


@dataclass(frozen=True)
class Narrowed:
    """A finding of the `witness` report on the pairs of one branch
    difference, and how many of its pairs stay as they are with a
    candidate witness in the file."""

    finding: Finding
    left: int


@dataclass(frozen=True)
class TryResult:
    """What a candidate witness would change (`survey_witness_try`): the entry as
    `record` would write it, the cases its groups were built from, the
    unseparated and the subsumed branch differences of the report whose
    pairs it would reduce."""

    entry: Entry
    cases: tuple[Case, ...]
    of: int
    """How many cases the solver has."""
    unseparated: tuple[Narrowed, ...]
    subsumed: tuple[Narrowed, ...]


@quotes("procedure.md", "Witness",
        "The cases' clauses differ and some input separates them: build the "
        "witness that shows it.")
def survey_witness_try(solver: Solver, runs: Runs, entry: Entry
                       ) -> TryResult | RunFailure | Fault:
    """The `witness --try` survey: the report's unseparated and subsumed
    branch differences (`check_equivalence`, `check_subsumption`), each
    with the count of its pairs that stay with `entry` added to the
    witness file, where that is fewer than it has; the entry's groups as
    `record` builds them. It writes nothing. The first run on the entry
    that gives no result, where one does.
    It serves the Witness step that resolves a pair no witness separates or a
    subsumed case by building "the witness that shows it" (procedure.md, under
    "Witness"): it shows whether a candidate input would."""
    solver_cases = runs.cases_or_none
    groups = groups_of(solver, [(c, runs.outcome(entry, c))
                                for c in solver_cases])
    if not isinstance(groups, Groups):
        return groups
    entry = replace(entry, output=groups)
    tried = replace(solver, witness_file=WitnessFile(
        solver.task_id, (*runs.entries, entry)))
    after = runs.sharing(tried, kept=runs.kept)
    before_u = _unseparated_findings(solver, runs)
    after_u = _unseparated_findings(tried, after, every=True)
    before_s = _subsumed_findings(solver, runs)
    after_s = _subsumed_findings(tried, after, every=True)

    def narrowed(before: list[Finding], now: list[Finding]
                 ) -> tuple[Narrowed, ...]:
        left: dict[tuple[object, object], int] = {}
        for f in now:
            p = f.payload
            assert isinstance(p, UnseparatedPayload | SubsumedPayload)
            left[(p.a, p.b)] = len(p.contexts.cases)
            if f.kind is Kind.UNSEPARATED:
                left[(p.b, p.a)] = len(p.contexts.cases)
        out: list[Narrowed] = []
        for f in before:
            p = f.payload
            assert isinstance(p, UnseparatedPayload | SubsumedPayload)
            n = left.get((p.a, p.b), 0)
            if n < len(p.contexts.cases):
                out.append(Narrowed(f, n))
        return tuple(out)

    return TryResult(entry, tuple(solver_cases), runs.case_count,
                     narrowed(before_u, after_u), narrowed(before_s, after_s))


@quotes("principles.md", "Cases",
        "A case is included exactly when it meets each **case condition**")
@quotes("principles.md", "Cases",
        "Of two cases with equivalent models, the one that takes more "
        "non-concept branches fails it, and of two with equal counts, one of "
        "them.")
@quotes("procedure.md", "Reconcile",
        "each case it drops fails one in a `witness --every-case` run with "
        "that case restored.")
def check_case_conditions(solver: Solver, runs: Runs) -> list[Finding]:
    """With `impl_choice` holding every case of `Choice` (`Runs.restored`),
    per base the solver drops, the first condition the runs show it failing:
    Fit, where no run shows it defined or a pair's run gives no output the
    pair accepts; Equivalence, where no witness separates it from a case
    that takes no more non-concept branches; Subsumption, where a case
    subsumes it. A dropped case that fails none is `drop-unjustified`, with
    the cases no witness separates it from. Those come first. The check
    reads the witnessed cases of the solver with every case restored
    (`Runs.cases` of `Runs.restored`), kept on disk as the solver's own are:
    a restored case that is not witnessed gives a witnessed case's output on
    every recorded input, so its Fit is shown there, and it gets no finding
    of its own. The cases a dropped case is compared with, for Equivalence
    and Subsumption, are every case with every case restored, whose runs on
    the recorded inputs the witnessed-case computation made. A dropped base
    is judged from the run with every case restored; where that run gives it
    no output on any input, it runs again on its own, `impl_choice` holding
    it alone (`Runs.alone`), and Fit, undefined and not run are read from
    that run. One whose runs give no cell at it on any input is reported as
    not run, since no condition is judged of it. A dropped base whose run
    gave no result is reported with that failure at the case, a timeout or a
    failed run, and no condition is judged of it. One with an entry whose
    assignment the model cannot place, a fault `fault_findings` reports, is
    reported as not run on that entry, and no condition is judged of it."""
    every = runs if runs.kept is not None else runs.restored
    if every is None:
        return []
    if not isinstance(every, Runs):
        return [enumeration_failed(every)]
    ran = every
    judged = ran.cases_or_none
    every = ran.showing
    solver_cases = every.cases_or_none
    kept = every.kept or ()
    kept_bases = {k.base for k in kept}
    inputs = _inputs(every)
    same = _same(every, inputs)
    others = [c for b in every.batches(solver_cases) for c in b]
    unjustified: list[Finding] = []
    failing: list[Finding] = []
    unread = [] if ran is runs and _reads_inputs(every) \
        else _pair_failures(every)
    lone = [a for a in judged
            if not a.branches and a.base not in kept_bases and inputs
            and all(is_result(got[a]) for got in inputs)
            and all(_emits_nothing(got[a]) for got in inputs)]
    by_alone = _alone_outcomes(every, lone)
    for a in judged:
        if a.branches or a.base in kept_bases:
            continue
        where = AtCase(a)
        outs = by_alone.get(a, [got[a] for got in inputs])
        failed = next((o for o in outs
                       if not isinstance(o, Grids | Undefined | Fault)), None)
        if failed is not None:
            failing.append(no_result(failed, RunKind.DROPPED_CASE, a, where))
            continue
        if any(not is_result(o) for o in outs):
            failing.append(Finding(Kind.DROPPED, where, DroppedPayload(
                a, Condition.ENTRY_NOT_RUN, None)))
            continue
        judged = fit(_case_pairs(every.alone(a) if a in by_alone else every,
                                 a), [a])
        if outs and all(_emits_nothing(o) for o in outs):
            failing.append(Finding(Kind.DROPPED, where, DroppedPayload(
                a, Condition.NOT_RUN, None)))
        elif outs and not any(_defined(o) for o in outs):
            failing.append(Finding(Kind.DROPPED, where, DroppedPayload(
                a, Condition.UNDEFINED, None)))
        elif isinstance(judged, Misses):
            failing.append(Finding(Kind.DROPPED, where, DroppedPayload(
                a, Condition.FIT, judged.pair)))
        elif b := next((b for b in others if b != a
                        and frozenset((a, b)) in same
                        and len(taken(solver, b)) <= len(taken(solver, a))),
                       None):
            failing.append(Finding(Kind.DROPPED, where, DroppedPayload(
                a, Condition.EQUIVALENCE, b)))
        elif subsumers := _subsumers(solver, inputs, a, others):
            failing.append(Finding(Kind.DROPPED, where, DroppedPayload(
                a, Condition.SUBSUMPTION, subsumers[0])))
        else:
            unjustified.append(Finding(
                Kind.DROP_UNJUSTIFIED, where, UnjustifiedDropPayload(
                    a, _case_set(every, [b for b in others
                                         if frozenset((a, b)) in same]))))
    return unread + unjustified + failing


@quotes("solver-file.md", "Cases",
        "**`impl_choice`.** The relation that enumerates the cases is "
        "`impl_choice`, and its column is `ch`.")
@quotes("principles.md", "Choice points and open parameters",
        "The **concept branch** at a choice point is the branch taken by the "
        "claims the point stands under.")
def check_concept_enumerated(solver: Solver, runs: Runs) -> list[Finding]:
    """The concept case is one of the solver's cases: `impl_choice`
    enumerates the cases, and every check that reads the concept case reads
    it among them. A concept case `impl_choice` leaves out is a finding; the
    old tool read it from `out`'s rows with no line."""
    choice = solver.choice
    solver_cases = runs.solver_cases if runs.kept is None else runs.kept
    if choice is None or not enumerates(solver.program) \
            or not isinstance(solver_cases, tuple):
        return []
    if any(is_concept_case(solver, c) for c in solver_cases):
        return []
    concept = concept_among(solver, every_base(choice) or ())
    if concept is None:
        return []
    case = base_case(concept)
    return [Finding(Kind.CONCEPT_UNENUMERATED, AtCase(case),
                    ConceptUnenumeratedPayload(case))]


WITNESS_CHECKS = (check_concept_enumerated, check_entry_outputs, check_other_verdict,
                  check_concept_output, check_separates, check_witness_lines,
                  check_verdict_denotes, check_approximation_witness,
                  check_witness_assignment, check_branches_witnessed,
                  check_branch_witness,
                  check_equivalence, check_subsumption)
"""The checks of the `witness` report, in the order it prints them. The
`--every-case` form runs them over `Runs.restored` and adds
`check_case_conditions`."""
