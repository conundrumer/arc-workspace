"""The checks over the witness file and the cases: the witness rules
(principles.md:126-128, :150-153, :185) and the case conditions the
witness file is the evidence for (principles.md:271-287), with what
`record` computes for an entry."""

import re
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, replace

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
    WitnessFileRole,
)
from checker.judged import (
    base_constructors,
    fit,
    no_result,
    verdict_case,
    VerdictCase,
    Misses,
)
from checker.payloads.witness import (
    ApproximatedWithoutWitness,
    ApproximationUnwitnessed,
    BranchUnwitnessed,
    AssignPayload,
    CaseSet,
    ConceptPayload,
    ConceptUnenumeratedPayload,
    Condition,
    DerivedAt,
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
    UnheldPayload,
    UnjustifiedDropPayload,
    UnlistedPayload,
    UnseparatedPayload,
    VerdictOutputUnknown,
    WitnessEntryMissing,
)
from checker.readable import finding_of
from checker.runs import Runs
from checker.variants import parallel
from engine import (
    AdtValue,
    CpuLimit,
    Grid,
    Resolved,
    RunFailure,
    Scope,
    WallLimit,
)
from engine.program import DeclId
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
    ConstructorBranch,
    DeriveBranch,
    Solver,
    StoreBranch,
    StoredAtDerive,
    concept_branch,
    enumerates,
    every_base,
    is_concept,
    load,
    other_branches,
    value_at,
)
from solver.names import (
    Denoted,
    cover,
    denote,
    denoted_cases,
    model_of,
    name,
)
from solver.problems import (
    InSolver,
    InWitnessFile,
    Named,
    ProblemKind,
    Fault,
)
from solver.solve import (
    Assignment,
    group_grid,
    as_grid,
    candidates,
    Candidate,
    CaseOnPair,
    Grids,
    Outcome,
    PairId,
    PairRuns,
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
    grouped,
)

# What the checks read


def _role(runs: Runs) -> WitnessFileRole:
    return WitnessFileRole.GIVEN if runs.given is not None \
        else WitnessFileRole.TASK


def _at(runs: Runs, entry: Entry) -> AtEntry:
    return AtEntry(entry.id, _role(runs))


def _solver_cases(runs: Runs) -> tuple[Case, ...]:
    """The solver's cases. Where the run that enumerates them fails, a
    check reads none, and `check_entry_outputs` reports that failure."""
    solver_cases = runs.cases
    return solver_cases if isinstance(solver_cases, tuple) else ()


def _shown(runs: Runs, case: Case) -> bool:
    """A case whose findings the runs show: every case of the solver, and under the
    `witness --every-case` form a case whose base the solver's own
    `impl_choice` holds."""
    return runs.kept is None or any(k.base == case.base for k in runs.kept)


def _no_result(o: object) -> bool:
    """A run that gave no result, or an entry whose assignment the model
    cannot place."""
    return not isinstance(o, Grids | Undefined)


def _emits_nothing(o: object) -> bool:
    """A run that gives no cell at the case."""
    return isinstance(o, Undefined) and isinstance(o.reason, NoOutput)


def _limited(o: object) -> bool:
    return isinstance(o, CpuLimit | WallLimit)


def _defined(o: object) -> bool:
    return isinstance(o, Grids)


def _same(a: Outcome, b: Outcome) -> bool:
    """Two outcomes agree: the same grids, or neither is defined
    (principles.md:159)."""
    return a == b


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


def _nonconcept(solver: Solver, case: Case) -> int:
    """How many non-concept branches a case takes: the constructors of its
    base that are not first at their point, and its `@derive` and
    `@store` branches (principles.md:286)."""
    firsts = set() if solver.choice is None else {
        concept_branch(p).name for p in solver.choice.points
        if p.constructors}
    return len([n for n in base_constructors(case.base) if n not in firsts]) \
        + len(case.branches)


def _concept(solver: Solver, solver_cases: Sequence[Case]) -> Case | None:
    """The concept case: the concept base, with no `@derive` or `@store`
    branch (`solver.model.is_concept`)."""
    return next((c for c in solver_cases
                 if not c.branches and is_concept(solver, c.base)), None)


type Inputs = list[dict[Case, Outcome]]
"""The inputs a pair of cases is compared on, each as the outcome of every
case of the solver there."""


def _inputs(runs: Runs) -> Inputs:
    """What every case of the solver gives on each input the witness file and the
    task hold: each entry at its assignment, and each train and test pair
    at the stored assignment. An entry whose assignment the model cannot
    place gives none."""
    solver_cases = _solver_cases(runs)
    out: Inputs = []
    for e in runs.entries:
        at = runs.assignment(e)
        if isinstance(at, Fault):
            continue
        out.append({c: runs.grid_outcome(e.input, at, c)
                    for c in solver_cases})
    for _pair, grid, _cands in _pairs(runs):
        out.append({c: runs.grid_outcome(grid, Assignment(()), c)
                    for c in solver_cases})
    return out


def _outcomes_of(runs: Runs, case: Case) -> list[Outcome]:
    """What `case` gives on each input `_inputs` reads, in its order."""
    out: list[Outcome] = []
    for e in runs.entries:
        at = runs.assignment(e)
        if not isinstance(at, Fault):
            out.append(runs.grid_outcome(e.input, at, case))
    out += [runs.grid_outcome(grid, Assignment(()), case)
            for _pair, grid, _cands in _pairs(runs)]
    return out


def _alone_outcomes(runs: Runs, cases: Sequence[Case]
                    ) -> dict[Case, list[Outcome]]:
    """`_outcomes_of` each case on its own (`Runs.alone`), the runs of
    every case on every input made at once."""
    alone = [runs.alone(a) for a in cases]
    parallel(lambda r: r.cases, alone)
    items: list[tuple[Runs, Case, Grid, Assignment]] = []
    for a, r in zip(cases, alone, strict=True):
        for e in r.entries:
            at = r.assignment(e)
            if not isinstance(at, Fault):
                items.append((r, a, e.input, at))
        items += [(r, a, grid, Assignment(()))
                  for _pair, grid, _cands in _pairs(r)]
    parallel(lambda i: i[0].grid_outcome(i[2], i[3], i[1]), items)
    return {a: _outcomes_of(r, a) for a, r in zip(cases, alone, strict=True)}


def _reads_inputs(runs: Runs) -> bool:
    """The equivalence and subsumption checks compare cases over the
    inputs: a solver with no witness file compares none."""
    return runs.given is not None or runs.solver.witness_file is not None


def _failures(got: Sequence[tuple[Case, Outcome | Fault]], run: RunKind,
              where: Where) -> list[Finding]:
    """The runs on one input that gave no result: a timeout per case whose
    run reached a limit, and the first failure of another kind, once per
    input."""
    out: list[Finding] = []
    failed = False
    for c, o in got:
        if _limited(o):
            assert isinstance(o, CpuLimit | WallLimit)
            out.append(no_result(o, run, c, where))
        elif not isinstance(o, Grids | Undefined | Fault) and not failed:
            failed = True
            out.append(no_result(o, run, None, where))
    return out


def _pair_failures(runs: Runs) -> list[Finding]:
    """The runs of the solver's cases on the task's pairs, at the stored
    assignment, that gave no result, each at its pair."""
    solver_cases = _solver_cases(runs)
    return [f for pair, grid, _cands in _pairs(runs)
            for f in _failures([(c, runs.grid_outcome(grid, Assignment(()), c))
                                for c in solver_cases],
                               RunKind.PAIR, AtPair(pair))]


def _pairs(runs: Runs
           ) -> list[tuple[PairId, Grid, tuple[tuple[Candidate,
                                                    frozenset[Grid]], ...]]]:
    """The task's train and test pairs: each by its id, with its input and
    its candidates (`solver.solve.pairs`)."""
    task = runs.solver.task
    if task is None:
        return []
    return [*((PairId("train", i), as_grid(ex.input), candidates(ex))
              for i, ex in enumerate(task.train)),
            *((PairId("test", i), as_grid(ex.input), candidates(ex))
              for i, ex in enumerate(task.test))]


def _case_pairs(runs: Runs, case: Case) -> tuple[PairRuns, ...]:
    """`case` on every train and test pair at the stored assignment, as
    `solver.solve.pairs` judges it."""
    out: list[PairRuns] = []
    for pair, grid, cands in _pairs(runs):
        got = runs.grid_outcome(grid, Assignment(()), case)
        matches = () if not isinstance(got, Grids) else tuple(
            c for c, accepted in cands if frozenset(got.grids) == accepted)
        out.append(PairRuns(pair, (CaseOnPair(case, got, matches),)))
    return tuple(out)


def _agree(inputs: Inputs, a: Case, b: Case) -> bool | None:
    """Whether `a` and `b` agree on every input; None where a run of either
    gave no result on an input where they do not already differ, so no
    input is known to separate them."""
    unknown = False
    for got in inputs:
        x, y = got[a], got[b]
        if _no_result(x) or _no_result(y):
            unknown = True
            continue
        if not _same(x, y):
            return False
    return None if unknown else True


def _subsumes(inputs: Inputs, a: Case, b: Case) -> bool:
    """No input shows `a` defined and differing from `b`, and some input
    shows `a` undefined where `b` is defined, so the two are not
    equivalent there (principles.md:176, :179). An input with no result
    for either shows nothing, and then no subsumption is found."""
    apart = False
    for got in inputs:
        x, y = got[a], got[b]
        if _no_result(x) or _no_result(y):
            return False
        if _defined(x) and not _same(x, y):
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
    solver_cases = _solver_cases(runs)
    return [(a, b) for i, a in enumerate(solver_cases) for b in solver_cases[i + 1:]
            if _agree(inputs, a, b) is True]


# The entries


def check_entry_outputs(solver: Solver, runs: Runs) -> list[Finding]:
    """The witness file records what each case of the solver gives on each entry
    (solver-file.md:181-186): the file is the evidence that Equivalence
    and Subsumption read (principles.md:285-287), and a verdict denotes an
    output the file records (principles.md:150-152). Per entry: the cases
    a group names whose output is not the group's grid (`drift`), the
    solver's cases no group names (`unlisted`), the group names that
    denote none of the solver's cases (`unheld`), an `assign` whose rows do not have the
    columns of the parameter or `@store` relation it names (`assign`;
    history "`assign` may name a stored relation"), and the runs that give
    no result. An entry whose id names a case of the solver need not list
    it. A given file is an Analyze file, which lists no case of the
    solver, and it has no `unlisted` finding; an entry of it whose `assign`
    names what the model cannot place runs at the `assign` of the task's
    own entry of its id (`task-assign`). Where the run that enumerates the
    solver's cases fails, that failure is the one finding, since no check
    of the report has cases to read."""
    solver_cases = runs.cases
    if not isinstance(solver_cases, tuple):
        return [no_result(solver_cases, RunKind.CASE, None,
                          AtFile(WholeFile.SOLVER))]
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
        task_entry = None if runs.given is None or task is None else next(
            (e for e in task.entries if e.id == entry.id), None)
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
    for key, value in entry.assign:
        columns = _columns(runs, key)
        if columns is None or not isinstance(value, AssignRows):
            continue
        arities = tuple(sorted({len(r) for r in value.rows}))
        if arities != (columns,):
            return None, [Finding(Kind.ASSIGN, _at(runs, entry),
                                  AssignPayload(key, arities, columns))]
    return entry, []


def _columns(runs: Runs, key: str) -> int | None:
    """How many columns the parameter or `@store` relation an `assign` key
    names has; None where the key names neither, which
    `solver.solve.assignment` reports."""
    solver = runs.solver
    param = next((p for p in solver.params.parameters if p.name == key),
                 None)
    if param is not None:
        return len(param.columns)
    branch = next((b for b in solver.branches
                   if isinstance(b, StoreBranch) and b.spelled == key), None)
    if branch is None:
        return None
    got = runs.index.resolve(branch.relation, Scope(()))
    if not isinstance(got, Resolved):
        raise ValueError(f"the `@store` relation {branch.relation.text} "
                         "resolves to no declaration")
    return next(len(r.columns) for r in solver.program.relations
                if r.id == got.declaration)


def _unknown_constants(solver: Solver, entry: Entry
                       ) -> tuple[tuple[str, str], ...] | None:
    """Each string of the entry's `assign` that is no lib constant, with its
    key; None where a key names no parameter or stored relation, or every
    string is a constant."""
    params = {p.name for p in solver.params.parameters}
    stored = {b.spelled for b in solver.branches
              if isinstance(b, StoreBranch)}

    def strings(args: object) -> Iterator[str]:
        if isinstance(args, str):
            yield args
        elif isinstance(args, tuple):
            for a in args:
                yield from strings(a)

    out: list[tuple[str, str]] = []
    for key, value in entry.assign:
        if key not in params and key not in stored:
            return None
        if isinstance(value, AssignRows):
            out += [(key, s) for s in strings(value.rows)
                    if s not in solver.lib.constants]
    return tuple(out) or None


def _case_set(runs: Runs, cases: Sequence[Case]) -> CaseSet:
    """`cases` with the names that print them: a lone case's name, else
    the fewest names that denote exactly them among the solver's cases
    (`solver.names.cover`)."""
    solver = runs.solver
    names = (name(solver, cases[0]),) if len(cases) == 1 \
        else cover(solver, cases, _solver_cases(runs))
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
    (solver-file.md:185). A case a name denotes whose output is not its
    group's grid is `drift`: the name reaches into another group. A case
    no group names is `unlisted`, and a name that denotes none of the
    solver's cases `unheld`. Under the `witness --every-case` form the
    names denote the solver's cases still, those the solver's own
    `impl_choice` holds (`_shown`): a dropped case is judged by
    `check_case_conditions` alone (solver-file.md:185). A given file's
    name is read as the model of the branches it names (`_model_set`):
    the file gives each branch's output, and no other case is compared
    with it (procedure.md:84, :171)."""
    assert isinstance(entry.output, Groups)
    solver_cases = [c for c in solver_cases if _shown(runs, c)]
    where = _at(runs, entry)
    drift: list[tuple[Case, object, Outcome]] = []
    problems: list[Finding] = []
    unheld: list[str] = []
    named: set[Case] = set()
    for group in entry.output.groups:
        in_group: set[Case] = set()
        for n in group.cases:
            cases = denoted_cases(solver, n, solver_cases) \
                if runs.given is None else _model_set(solver, n, solver_cases)
            if isinstance(cases, Fault):
                # The task's file's names are read with the model; a given
                # file's are read here.
                if runs.given is not None:
                    problems.append(finding_of(Fault(
                        cases.kind, InWitnessFile(entry.id), cases.detail)))
            elif not cases:
                unheld.append(n)
            in_group |= set() if isinstance(cases, Fault) else cases
        named |= in_group
        for case in solver_cases:
            if case not in in_group:
                continue
            got = runs.outcome(entry, case)
            if _no_result(got):
                continue
            assert not isinstance(got, Fault)
            if not _records(group.grid, got):
                drift.append((case, group.grid, got))
    out: list[Finding] = []
    for cases, want, got in _merged(drift):
        assert isinstance(want, (tuple, Resolutions, Undefined))
        out.append(Finding(Kind.DRIFT, where, DriftPayload(
            _case_set(runs, cases), want, got)))
    out += problems
    if unheld:
        out.append(Finding(Kind.UNHELD, where, UnheldPayload(tuple(unheld))))
    if runs.given is not None or _unread_names(solver, entry):
        return out
    own = _own(solver, entry, solver_cases)
    rows: list[tuple[Case, object, Outcome]] = []
    for c in solver_cases:
        if c in named or c in own:
            continue
        got = runs.outcome(entry, c)
        if _no_result(got):
            continue
        assert not isinstance(got, Fault)
        rows.append((c, None, got))
    out += [Finding(Kind.UNLISTED, where,
                    UnlistedPayload(_case_set(runs, cases), got))
            for cases, _w, got in _merged(rows)]
    return out


def _model_set(solver: Solver, text: str, solver_cases: Sequence[Case]
               ) -> frozenset[Case] | Fault:
    """A given file's group name read as a branch's model
    (procedure.md:84, :171): the one case `model_of` gives for it among
    the solver's cases, none where that model is no case of the solver;
    the problem where the name denotes nothing."""
    d = denote(solver, text)
    if isinstance(d, Fault):
        return d
    model = model_of(solver, d, solver_cases)
    return frozenset() if model is None or model not in solver_cases \
        else frozenset({model})


def _own(solver: Solver, entry: Entry, solver_cases: Sequence[Case]
         ) -> frozenset[Case]:
    """The cases the entry's id denotes, which its groups need not name;
    none where the id is no name."""
    got = denoted_cases(solver, entry.id, solver_cases)
    return frozenset() if isinstance(got, Fault) else got


def _unread_names(solver: Solver, entry: Entry) -> bool:
    """A group of the entry holds a name that denotes no model: which cases
    the entry lists is then not known, so no case is found unlisted and no
    `separates` name found missing."""
    return isinstance(entry.output, Groups) and any(
        isinstance(denote(solver, n), Fault)
        for g in entry.output.groups for n in g.cases)


def check_other_verdict(solver: Solver, runs: Runs) -> list[Finding]:
    """principles.md:153: "`other`: an output that no case produces." An
    entry of a judged output (solver-file.md:182) on which cases of the solver give
    that output is a finding, one per entry with the cases that give it."""
    solver_cases = _solver_cases(runs)
    out: list[Finding] = []
    for entry in runs.entries:
        if not isinstance(entry.output, RejectedOutput) \
                or isinstance(runs.assignment(entry), Fault):
            continue
        judged = entry.output.grid
        cases = tuple(c for c in solver_cases if _shown(runs, c)
                      and runs.outcome(entry, c) == Grids((judged,)))
        if cases:
            out.append(Finding(Kind.DRIFT, _at(runs, entry), DriftPayload(
                _case_set(runs, cases), entry.output, Grids((judged,)))))
    return out


def check_concept_output(solver: Solver, runs: Runs) -> list[Finding]:
    """On an entry of a given file with a judged output, the concept case
    gives that output; an entry where it gives another is a finding. Only
    a given file is read. No principle states this: procedure.md:170-172
    asks for the run against the Analyze file, and leaves to the agent
    whether the solver or the Analyze file erred. Its kind, `concept`, is
    a hint outside `FAILING`."""
    if runs.given is None:
        return []
    concept = _concept(solver, _solver_cases(runs))
    out: list[Finding] = []
    for entry in runs.entries:
        if concept is None or not isinstance(entry.output, RejectedOutput) \
                or isinstance(runs.assignment(entry), Fault):
            continue
        got = runs.outcome(entry, concept)
        if _no_result(got) or isinstance(got, Fault):
            continue
        if got != Grids((entry.output.grid,)):
            out.append(Finding(Kind.CONCEPT, _at(runs, entry),
                               ConceptPayload(entry.output.grid, got)))
    return out


_SEPARATES_WORD = r"[\w.]+=\w+|\$?[A-Za-z]\w*"


def _separates_names(text: str) -> list[str]:
    """The runs of words joined by ` & ` in a `separates` text that may be
    names in the one form: a run of more than one word, a word with `=`,
    a constructor with its `$`, or `concept`. A bare word is prose."""
    pattern = re.compile(rf"(?:{_SEPARATES_WORD})"
                         rf"(?:\s*&\s*(?:{_SEPARATES_WORD}))*")
    out: list[str] = []
    for m in pattern.finditer(text):
        n = m.group(0)
        if ("&" in n or "=" in n or n.startswith("$")
                or n == VerdictWord.CONCEPT) and n not in out:
            out.append(n)
    return out


def check_separates(solver: Solver, runs: Runs) -> list[Finding]:
    """An entry's `separates` text names the models its input separates
    (solver-file.md:178), and each group lists the cases it records
    (solver-file.md:185): a name in the text denotes a model, the named
    branches with every other point at its concept branch
    (principles.md:116), and where that model is a case of the solver no
    group names, the name is a finding. An entry of a judged output has no
    groups, and an entry need not name the cases its id names; a group's
    names denote sets of cases (`solver.names.denoted_cases`). No
    principle states this: the text is prose for the reader of the file.
    Its kind, `separates`, is a hint outside `FAILING`."""
    solver_cases = _solver_cases(runs)
    out: list[Finding] = []
    for entry in runs.entries:
        if not isinstance(entry.output, Groups) \
                or _unread_names(solver, entry):
            continue
        written = {n for g in entry.output.groups for n in g.cases}
        named = set(_own(solver, entry, solver_cases))
        for n in written:
            got = denoted_cases(solver, n, solver_cases)
            if not isinstance(got, Fault):
                named |= got
        for n in _separates_names(entry.separates):
            if n in written:
                continue
            d = denote(solver, n)
            case = None if isinstance(d, Fault) \
                else model_of(solver, d, solver_cases)
            if case is None or case not in solver_cases or case in named \
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
    (solver-file.md:86-90); the model's fault where the representative
    has no solver file, since its claims are then unknown."""
    own = tuple(c for c in solver.annotations.claims if c.constructor is None)
    rep = solver.annotations.representative
    if rep is None or rep.task_id == solver.stem:
        return own
    missing = next((p for p in solver.problems
                    if p.kind == ProblemKind.REPRESENTATIVE_MISSING), None)
    if missing is not None:
        return missing
    other = load(rep.task_id, runs.engine)
    return own + tuple(c for c in other.annotations.claims
                       if c.constructor is None)


def check_witness_lines(solver: Solver, runs: Runs) -> list[Finding]:
    """The `@witness` lines and the witness file agree, in the form of
    solver-file.md:28-33, :176. A witness is an input
    (principles.md:123), so each line's id is an entry of the file; a
    witness stands at an assignment (principles.md:127), so the
    `@reassigned` lines of a witness name the parameters its `assign`
    changes; plausibility turns on the scene claims a witness breaks
    (principles.md:129, :136), so each `@relaxed` line of a `@witness`,
    `@derive` or `@store` line names a scene claim of the header
    (procedure.md:150).
    A given file is not the task's, and its entries are not read here;
    with no witness file, there is nothing to compare. Where the header's
    claims are unknown (`_header_claims`), no `@relaxed` line is checked,
    and the fault that says so is `check_faults`'s."""
    if runs.given is not None or solver.witness_file is None:
        return []
    entries = {e.id: e for e in runs.entries}
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
        entry = entries.get(w.id)
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
    return verdict_case(solver, verdict, _solver_cases(runs), None)


def check_verdict_denotes(solver: Solver, runs: Runs) -> list[Finding]:
    """principles.md:149-152: a verdict denotes the output of the concept
    case, of a branch's model (principles.md:116: the named branches, with
    every other point at its concept branch), or of any case defined on
    the witness. A verdict of a `@witness`, `@derive` or `@store` line
    whose name denotes a model that neither the runner holds nor
    `model_of` can build denotes an output no run gives, and is a
    finding. A name that denotes no model is a fault, which `check_faults`
    reports."""
    solver_cases = _solver_cases(runs)
    if not isinstance(runs.cases, tuple):
        return []
    a = solver.annotations
    out: list[Finding] = []
    for line in (*a.witnesses, *a.derives, *a.stores):
        v = line.verdict
        if isinstance(v, NamedVerdict) \
                and _verdict_case(solver, runs, v) is None:
            out.append(Finding(Kind.ANNOTATION, AtLine(line.line),
                               VerdictOutputUnknown(v)))
    return out


def _departs(runs: Runs, verdict: Verdict,
             named: VerdictCase, case: Case, entry: Entry | None) -> bool:
    """The witness shows `case` giving an output other than the verdict's
    (solver-file.md:95): `other` every case's, `any` no case's, and
    otherwise where the verdict's case, `named`, gives another output on
    the witness. A run that reached a limit leaves the output unknown, and
    the case departs; a run that failed shows nothing."""
    if verdict == VerdictWord.OTHER:
        return True
    if not isinstance(named, Case) or case == named or entry is None:
        return False
    outs = [runs.outcome(entry, c) for c in (case, named)]
    if any(isinstance(o, Fault) for o in outs):
        return False
    if any(_no_result(o) and not _limited(o) for o in outs):
        return False
    if any(_limited(o) for o in outs):
        return True
    return all(o != outs[0] for o in outs[1:])


def check_approximation_witness(solver: Solver, runs: Runs
                                ) -> list[Finding]:
    """principles.md:185: "The approximation disagrees with the rule on
    some such input, and that input is a divergence witness."; with
    solver-file.md:92-93: a witness under an `@approximated:` line is not
    `foreign`, and each case that runs the approximation has a witness on
    which its output is not the verdict's. A case whose branch carries a
    `@rule` line of the claim's slug restates the claim, and the
    approximation does not run on it."""
    solver_cases = _solver_cases(runs)
    entries = {e.id: e for e in runs.entries}
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
            if not any(_departs(runs, w.verdict, n, case, entries.get(w.id))
                       for w, n in zip(witnesses, named)):
                out.append(Finding(Kind.ANNOTATION, AtLine(c.line),
                                   ApproximationUnwitnessed(c.kind, c.slug,
                                                            case)))
    return out


@dataclass(frozen=True)
class _BranchWitness:
    """A `@witness` line of a branch other than its point's first: the
    branch's model and the model of the point's first branch
    (principles.md:116, :126)."""

    line: WitnessLine
    branch: ConstructorBranch
    model: Case
    first: Case


def _branch_witnesses(solver: Solver, runs: Runs
                      ) -> tuple[list[_BranchWitness], list[Fault]]:
    """Each `@witness` line in the branch comment of a constructor other
    than its point's first, under no `@approximated:` line, whose verdict
    denotes another model than the branch's: a witness of the concept
    case stands under the branch its verdict denotes (procedure.md:152).
    A line whose branch or first branch has no model to build is not
    here. A line in the comment of a constructor that is at no choice
    point is a fault: the name of its branch denotes no case."""
    choice = solver.choice
    points = () if choice is None else choice.points
    solver_cases = _solver_cases(runs)
    out: list[_BranchWitness] = []
    faults: list[Fault] = []
    for w in solver.annotations.witnesses:
        if w.approximates is not None or w.constructor is None:
            continue
        if not any(c.name == w.constructor
                   for p in points for c in p.constructors):
            faults.append(Fault(ProblemKind.NAME_DENOTES_NO_CASE,
                                InSolver(w.line), Named(w.constructor)))
            continue
        point = next((p for p in points
                      for c in other_branches(p) if c.name == w.constructor),
                     None)
        if choice is None or point is None:
            continue
        ctor = next(c for c in point.constructors if c.name == w.constructor)
        steps = point.path[1:] if choice.record is not None else point.path
        parents = tuple(next(c for p in choice.points for c in p.constructors
                             if c.name == s) for s in steps[0::2])
        d_model = Denoted((*parents, ctor), ())
        d_first = Denoted((*parents, concept_branch(point)), ())
        model = model_of(solver, d_model, solver_cases)
        first = model_of(solver, d_first, solver_cases)
        if model is None or first is None:
            continue
        if _verdict_case(solver, runs, w.verdict) == model:
            continue
        out.append(_BranchWitness(w, ctor, model, first))
    return out, faults


def check_branches_witnessed(solver: Solver, runs: Runs) -> list[Finding]:
    """principles.md:126: "A branch's witnesses are divergence witnesses
    between its model and the concept branch's model"; style.md:50:
    "Every other branch has at least one `@witness` line." A branch of a
    choice point other than its concept branch whose branch comment holds
    no `@witness` line is a finding at the line the branch starts on, one
    per branch where several start on one line. The Witness operation
    writes those lines with the witness file (procedure.md "Witness"), so
    a solver with no witness file is not held to it, and a given file is
    not the task's."""
    choice = solver.choice
    if choice is None or runs.given is not None \
            or solver.witness_file is None:
        return []
    witnessed = {w.constructor for w in solver.annotations.witnesses}
    out: list[Finding] = []
    seen: set[DeclId] = set()
    for p in choice.points:
        if p.declaration in seen:
            continue
        seen.add(p.declaration)
        out += [Finding(Kind.ANNOTATION, AtLine(c.line),
                        BranchUnwitnessed(c.name))
                for c in other_branches(p) if c.name not in witnessed]
    return out


def check_branch_witness(solver: Solver, runs: Runs) -> list[Finding]:
    """principles.md:126: "A branch's witnesses are divergence witnesses
    between its model and the concept branch's model." A branch's
    `@witness` line on whose entry the two models give the same output, or
    neither is defined (principles.md:159), is a finding; a run with no
    result shows nothing. The line is judged whether or not the solver's
    `impl_choice` holds the model, so `witness --every-case` judges it as
    `witness` does. A `@witness` line in the comment of a constructor at
    no choice point is a fault (`_branch_witnesses`)."""
    entries = {e.id: e for e in runs.entries}
    witnesses, faults = _branch_witnesses(solver, runs)
    out = [finding_of(f) for f in faults]
    for bw in witnesses:
        entry = entries.get(bw.line.id)
        if entry is None:
            continue
        a, b = runs.outcome(entry, bw.model), runs.outcome(entry, bw.first)
        if _no_result(a) or _no_result(b):
            continue
        if a == b:
            out.append(Finding(Kind.ANNOTATION, AtLine(bw.line.line),
                               NoDivergence(entry.id, bw.model, bw.first,
                                            bw.branch)))
    return out


def check_witness_assignment(solver: Solver, runs: Runs) -> list[Finding]:
    """principles.md:127: "A witness stands at this task's stored
    assignment when the model it is for is defined there and differs
    there from what it is separated from." The model a witness is for
    (principles.md:128): a branch's model for a branch's witness, from the
    point's first branch; the concept case's otherwise, from the output
    the verdict denotes, or from the judged output for `other`. A witness
    whose `assign` changes a parameter and at which that holds at the
    stored assignment is a finding. The search for the assignment that
    changes the fewest parameters is not made here."""
    if runs.given is not None:
        return []
    solver_cases = _solver_cases(runs)
    entries = {e.id: e for e in runs.entries}
    concept = _concept(solver, solver_cases)
    branch = {bw.line.line: bw for bw in _branch_witnesses(solver, runs)[0]}
    out: list[Finding] = []
    for w in solver.annotations.witnesses:
        entry = entries.get(w.id)
        if entry is None or not entry.assign \
                or isinstance(runs.assignment(entry), Fault):
            continue
        against: list[Case] = []
        judged: Grid | None = None
        if w.line in branch:
            model, against = branch[w.line].model, [branch[w.line].first]
        elif concept is None:
            continue
        else:
            model = concept
            if w.verdict == VerdictWord.OTHER:
                if not isinstance(entry.output, RejectedOutput):
                    continue
                judged = entry.output.grid
            else:
                named = _verdict_case(solver, runs, w.verdict)
                if not isinstance(named, Case) or named == model:
                    continue
                against = [named]
        stored = replace(entry, assign=())
        outs = [runs.outcome(stored, c) for c in (model, *against)]
        if any(_no_result(o) for o in outs) or not _defined(outs[0]):
            continue
        if all(o != outs[0] for o in outs[1:]) and (
                judged is None or outs[0] != Grids((judged,))):
            out.append(Finding(Kind.ANNOTATION, AtLine(w.line),
                               StandsElsewhere(
                                   w.id, tuple(k for k, _v in entry.assign))))
    return out


# The case conditions


type _Point = tuple[str, ...]
"""A choice point: `("choice", *path)` for a point of `Choice`,
`("derive", param)` and `("store", rel)` for a `@derive` and a `@store`
point."""


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
            at = value_at(choice, case.base, p.path)
            out[("choice", *p.path)] = next(
                (c for c in p.constructors if isinstance(at, AdtValue)
                 and c.name == at.constructor), None)
    for b in solver.branches:
        if isinstance(b, DeriveBranch):
            key = ("derive", b.parameter)
            if key not in out:
                out[key] = StoredAtDerive(b.parameter)
            if b in case.branches:
                out[key] = b
        elif isinstance(b, StoreBranch):
            out[("store", b.spelled)] = b if b in case.branches \
                else DerivedAt(b)
    return out


def _concept_only(solver: Solver, side: Sequence[PointBranch | None]
                  ) -> bool:
    """Whether a side of a difference takes no constructor other than its
    point's concept branch."""
    firsts = set() if solver.choice is None else {
        concept_branch(p).name for p in solver.choice.points
        if p.constructors}
    return all(not isinstance(x, ConstructorBranch) or x.name in firsts
               for x in side)


type _Difference = tuple[tuple[_Point, ...],
                         tuple[PointBranch | None, ...],
                         tuple[PointBranch | None, ...]]
"""The points at which two cases differ, and the branch each takes
there."""


def _differing(solver: Solver, runs: Runs, a: Case, b: Case) -> int:
    """How many choice points `a` and `b` take different branches at."""
    pa, pb = _point_branches(solver, a), _point_branches(solver, b)
    return len([k for k in pa if pa[k] != pb.get(k)])


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
    shown = [c for c in _solver_cases(runs) if _shown(runs, c)]
    points = {c: _point_branches(solver, c) for c in shown}
    groups: dict[_Difference, list[Case]] = {}
    wanted: set[_Difference] = set()
    for a, b in pairs:
        pa, pb = points[a], points[b]
        at = tuple(k for k in pa if pa[k] != pb.get(k))
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
        out.append(Finding(kind, AtCase(Case(None, ())), payload))
    return out


def check_equivalence(solver: Solver, runs: Runs) -> list[Finding]:
    """principles.md:285: "**Equivalence.** The model is not equivalent to
    the model of another case." The evidence is the witness file and the
    task's pairs: two cases of the solver that agree on every entry and
    every pair are a pair no witness separates (procedure.md:174). One
    finding per branch difference among those pairs (`_by_difference`);
    a pair where some run gave no result is not reported, and each run on
    a pair that gave no result is reported at its pair (the entries' runs
    are `check_entry_outputs`'s)."""
    failures = _pair_failures(runs) if _reads_inputs(runs) else []
    pairs = _unseparated_pairs(runs)
    return failures + _by_difference(
        solver, runs, pairs, _spanning(solver, runs, pairs), False,
        Kind.UNSEPARATED)


def _unseparated_pairs(runs: Runs) -> list[tuple[Case, Case]]:
    """The pairs of shown cases no witness separates (`_unseparated`)."""
    return [(a, b) for a, b in _unseparated(runs, _inputs(runs))
            if _shown(runs, a) and _shown(runs, b)]


def _subsumers(solver: Solver, inputs: Inputs, a: Case,
               others: Sequence[Case]) -> list[Case]:
    """The cases of `others` that subsume `a`, less each that subsumes
    another of them; none for the concept case (principles.md:287)."""
    if not a.branches and is_concept(solver, a.base):
        return []
    partners = [b for b in others if b != a and _subsumes(inputs, a, b)]
    return [b for b in partners
            if not any(_subsumes(inputs, c, b) for c in partners if c != b)]


def check_subsumption(solver: Solver, runs: Runs) -> list[Finding]:
    """principles.md:287: "**Subsumption.** The model of a case other than
    the concept case is not subsumed by the model of another case." Over
    the witness file and the task's pairs, a case of the solver that no
    run shows defined and differing from another case of the solver,
    where some run shows the two apart, is subsumed by it
    (procedure.md:178); a pair no witness separates is
    `check_equivalence`'s alone. One finding per branch difference among
    those pairs (`_by_difference`), each pair a subsumed case and a case
    that subsumes it and subsumes no other that does."""
    if not _reads_inputs(runs):
        return []
    pairs, nearest = _subsumed_pairs(solver, runs)
    return _by_difference(solver, runs, pairs, nearest, True, Kind.SUBSUMED)


def _subsumed_pairs(solver: Solver, runs: Runs
                    ) -> tuple[list[tuple[Case, Case]], set[tuple[Case, Case]]]:
    """Each shown case with each case that subsumes it (`_subsumers`),
    and of those pairs, each subsumed case with the subsumer that differs
    from it at the fewest points."""
    inputs = _inputs(runs)
    same = {frozenset(p) for p in _unseparated(runs, inputs)}
    solver_cases = [c for c in _solver_cases(runs) if _shown(runs, c)]
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
    """What a candidate witness would change (`try_witness`): the entry as
    `record` would write it, the cases its groups were built from, the
    unseparated and the subsumed branch differences of the report whose
    pairs it would reduce."""

    entry: Entry
    cases: tuple[Case, ...]
    unseparated: tuple[Narrowed, ...]
    subsumed: tuple[Narrowed, ...]


def try_witness(solver: Solver, runs: Runs, entry: Entry
                ) -> TryResult | RunFailure | Fault:
    """The `witness --try` survey: the report's unseparated and subsumed
    branch differences (`check_equivalence`, `check_subsumption`), each
    with the count of its pairs that stay with `entry` added to the
    witness file, where that is fewer than it has; the entry's groups as
    `record` builds them. It writes nothing. The first run on the entry
    that gives no result, where one does."""
    solver_cases = _solver_cases(runs)
    got = [(c, runs.outcome(entry, c)) for c in solver_cases]
    failed = next((o for _c, o in got if not isinstance(o, Grids | Undefined)),
                  None)
    if failed is not None:
        assert not isinstance(failed, Grids | Undefined)
        return failed
    given = [(c, group_grid(o)) for c, o in got
             if isinstance(o, Grids | Undefined)]
    entry = replace(entry, output=grouped(solver, given))
    file = solver.witness_file
    entries = (() if file is None else file.entries) + (entry,)
    tried = replace(solver, witness_file=WitnessFile(solver.task_id,
                                                     entries))
    after = Runs(runs.engine, tried, runs.limits, kept=runs.kept)
    pairs = _unseparated_pairs(runs)
    before_u = _by_difference(solver, runs, pairs,
                              _spanning(solver, runs, pairs), False,
                              Kind.UNSEPARATED)
    pairs = _unseparated_pairs(after)
    after_u = _by_difference(tried, after, pairs, set(pairs), False,
                             Kind.UNSEPARATED)
    pairs, nearest = _subsumed_pairs(solver, runs)
    before_s = _by_difference(solver, runs, pairs, nearest, True,
                              Kind.SUBSUMED)
    pairs, _nearest = _subsumed_pairs(tried, after)
    after_s = _by_difference(tried, after, pairs, set(pairs), True,
                             Kind.SUBSUMED)

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

    return TryResult(entry, tuple(c for c, _g in given),
                     narrowed(before_u, after_u), narrowed(before_s, after_s))


def check_case_conditions(solver: Solver, runs: Runs) -> list[Finding]:
    """principles.md:271: "A case is included exactly when it meets each
    **case condition**"; procedure.md:210: each case a solver drops fails
    one "in a `witness --every-case` run with that case restored". With
    `impl_choice` holding every case of `Choice` (`Runs.restored`), per
    base the solver drops, the first condition the runs show it failing:
    Fit, where no run shows it defined or a pair's run gives no output the
    pair accepts; Equivalence, where no witness separates it from a case
    that takes no more non-concept branches (principles.md:286);
    Subsumption, where a case subsumes it. A dropped case that fails none
    is `drop-unjustified`, with the cases no witness separates it from.
    Those come first. A dropped base is judged from the run with every
    case restored; where that run gives it no output on any input, it
    runs again on its own, `impl_choice` holding it alone (`Runs.alone`),
    and Fit, undefined and not run are read from that run. One whose
    runs give no cell at it on any input is reported as not run, since no
    condition is judged of it. A dropped base whose run gave
    no result is reported with that failure at the case, a timeout or a
    failed run, and no condition is judged of it. One with an entry whose
    assignment the model cannot place, a fault `check_faults` reports, is
    reported as not run on that entry, and no condition is judged of it."""
    every = runs if runs.kept is not None else runs.restored
    if every is None:
        return []
    if not isinstance(every, Runs):
        return [no_result(every, RunKind.CASE, None, AtFile(WholeFile.SOLVER))]
    solver_cases = _solver_cases(every)
    kept = every.kept or ()
    kept_bases = {k.base for k in kept}
    inputs = _inputs(every)
    same = {frozenset(p) for p in _unseparated(every, inputs)}
    others = ([c for c in solver_cases if c.base in kept_bases]
              + [c for c in solver_cases if c.base not in kept_bases])
    unjustified: list[Finding] = []
    failing: list[Finding] = []
    unread = [] if every is runs and _reads_inputs(every) \
        else _pair_failures(every)
    lone = [a for a in solver_cases
            if not a.branches and a.base not in kept_bases and inputs
            and not any(_no_result(got[a]) for got in inputs)
            and all(_emits_nothing(got[a]) for got in inputs)]
    by_alone = _alone_outcomes(every, lone)
    for a in solver_cases:
        if a.branches or a.base in kept_bases:
            continue
        where = AtCase(a)
        outs = by_alone.get(a, [got[a] for got in inputs])
        failed = next((o for o in outs
                       if not isinstance(o, Grids | Undefined | Fault)), None)
        if failed is not None:
            failing.append(no_result(failed, RunKind.DROPPED_CASE, a, where))
            continue
        if any(_no_result(o) for o in outs):
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
                        and _nonconcept(solver, b) <= _nonconcept(solver, a)),
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


def check_concept_enumerated(solver: Solver, runs: Runs) -> list[Finding]:
    """The concept case is one of the solver's cases: `impl_choice`
    enumerates the cases (solver-file.md:109), and every check that reads
    the concept case reads it among them (principles.md:110, "the
    concept branch"). A concept case `impl_choice` leaves out is a finding;
    the old tool read it from `out`'s rows with no line."""
    choice = solver.choice
    solver_cases = runs.cases if runs.kept is None else runs.kept
    if choice is None or not enumerates(solver.program) \
            or not isinstance(solver_cases, tuple):
        return []
    if any(not c.branches and is_concept(solver, c.base)
           for c in solver_cases):
        return []
    concept = next((b for b in every_base(choice) or ()
                    if is_concept(solver, b)), None)
    if concept is None:
        return []
    case = Case(concept, ())
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
