"""The checks of the witness rules (principles.md, under "Witnesses" and
"Relational form"), and the checks of the `witness` report in the order
it prints them."""

from collections.abc import Sequence
from dataclasses import dataclass, replace

from checker.branches.cases import untaken_lines
from checker.case_conditions import check_equivalence, check_subsumption
from checker.finding import (
    AtCase,
    AtLine,
    Finding,
    Kind,
    RunKind,
    Where,
)
from checker.judged import (
    VerdictCase,
    base_constructors,
    concept_among,
    concept_case,
    differ,
    enumeration_failed,
    model_named,
    no_result,
    representative,
    verdict_case,
)
from checker.payloads.witness import (
    ApproximatedWithoutWitness,
    ApproximationUnwitnessed,
    BranchUnwitnessed,
    ConceptPayload,
    ConceptUnenumeratedPayload,
    DriftPayload,
    ForeignUnderApproximated,
    ListsNoCasePayload,
    NoDivergence,
    ReassignedMismatch,
    RelaxedNoClaim,
    RelaxedNotScene,
    SeparatesPayload,
    StandsElsewhere,
    TaskAssignPayload,
    UnlistedPayload,
    VerdictOutputUnknown,
    WitnessEntryMissing,
    WitnessTextDiffers,
)
from checker.readable import finding_of
from checker.runs import Runs
from checker.witness_reads import (
    case_set,
    defined,
    entry_at,
    gives,
    is_shown,
    judged_entries,
    no_result_findings,
    records,
    shown_cases,
)
from engine import (
    RunFailure,
)
from engine.program import DeclId
from engine.quotes import guard, quotes
from solver.aggregate import (
    Solver,
    assignable,
    branch_witnesses,
    enumerates,
    is_concept_case,
)
from solver.annotations import (
    Claim,
    ClaimKind,
    NamedVerdict,
    Plausibility,
    Verdict,
    VerdictWord,
    WitnessLine,
)
from solver.columns import unknown_strings
from solver.model import (
    Case,
    ConstructorBranch,
    base_case,
    concept_branch,
    constructor_named,
    constructor_places,
    every_base,
    is_concept_branch,
    other_branches,
)
from solver.names import (
    LinesDiffer,
    cases_of,
    denote,
    denoted_cases,
    model_of,
    names_in,
    witness_verdict,
)
from solver.outcome import Outcome, is_result
from solver.problems import (
    Fault,
    InSolver,
    InWitnessFile,
    Named,
    NameFault,
    ProblemKind,
    WitnessFileRole,
)
from solver.witnessed_cases import constructor_denoted
from solver.witness import (
    AssignRows,
    Entry,
    Group,
    Groups,
    RejectedOutput,
)


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
    (`lists-no-case`), a given file's group names whose model is no case of
    the solver (`model-not-case`), an `assign` whose rows do not have the columns of the
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
        out += no_result_findings([(c, runs.outcome(entry, c)) for c in solver_cases],
                         RunKind.WITNESS, entry_at(runs, entry))
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
                Kind.TASK_ASSIGN, entry_at(runs, entry),
                TaskAssignPayload(values, task_entry.id, task_entry.assign))]
        known = any(p.kind == at.kind and p.place == at.place
                    for p in solver.problems)
        return None, [] if known and runs.given is None \
            else [finding_of(at)]
    return entry, []


def _unknown_constants(solver: Solver, entry: Entry
                       ) -> tuple[tuple[str, str], ...] | None:
    """Each string of the entry's `assign` that names nothing
    (`solver.columns.unknown_strings`), with its key; None where a key names
    no parameter or stored relation, or every string names something."""
    out: list[tuple[str, str]] = []
    for key, value in entry.assign:
        if not assignable(solver, key):
            return None
        if isinstance(value, AssignRows):
            out += [(key, s) for s in unknown_strings(solver, value.rows)]
    return tuple(out) or None


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
    `impl_choice` holds (`is_shown`): a dropped case is judged by
    `check_case_conditions` alone (solver-file.md, under "Witness file"). A
    given file's name is read as the model of the branches it names, where
    that model is one of `solver_cases` (`_model_set`), and a name whose
    model is not one of them, while some case takes its branches, is
    compared with no case, names none, and is reported `model-not-case`:
    the file gives each branch's
    output, the output of its model alone, and no other case is compared
    with it (procedure.md, under "Analyze after the concept" and "Witness";
    solver-file.md, under "Witness file").
    The names denote cases of the solver, and the `drift` and `unlisted`
    findings are on `solver_cases`, the witnessed cases, alone."""
    assert isinstance(entry.output, Groups)
    witnessed = frozenset(solver_cases)
    every = runs.solver_cases
    solver_cases = shown_cases(runs, every if isinstance(every, tuple)
                                else solver_cases)
    where = entry_at(runs, entry)
    drift: list[tuple[Case, object, Outcome]] = []
    problems: list[Finding] = []
    listing_none: list[str] = []
    unchecked: list[str] = []
    named: set[Case] = set()
    for group in entry.output.groups:
        in_group: set[Case] = set()
        for n in group.cases:
            task_file = runs.file_role is WitnessFileRole.TASK
            cases = denoted_cases(solver, n, solver_cases) \
                if task_file else _model_set(solver, n, solver_cases)
            if cases is None:
                unchecked.append(n)
                continue
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
            if not records(group.grid, got):
                drift.append((case, group, got))
    out: list[Finding] = []
    for cases, want, got in _merged(drift):
        assert isinstance(want, Group)
        out.append(Finding(Kind.DRIFT, where, DriftPayload(
            case_set(runs, cases), want, got)))
    out += problems
    if listing_none:
        out.append(Finding(Kind.LISTS_NO_CASE, where,
                           ListsNoCasePayload(tuple(listing_none))))
    if unchecked:
        out.append(Finding(Kind.MODEL_NOT_CASE, where,
                           ListsNoCasePayload(tuple(unchecked))))
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
                    UnlistedPayload(case_set(runs, cases), got))
            for cases, _w, got in _merged(rows)]
    return out


def _model_set(solver: Solver, text: str, solver_cases: Sequence[Case]
               ) -> frozenset[Case] | NameFault | None:
    """A given file's group name read as a branch's model
    (procedure.md, under "Analyze after the concept" and "Witness"): that
    model where it is one of `solver_cases` (`solver.names.model_of`;
    solver-file.md, under "Witness file"); None, nothing to compare, where
    it is not and some case of `solver_cases` takes the branch; none where
    no case takes the branch; the problem where the name denotes nothing."""
    d = denote(solver, text)
    if isinstance(d, NameFault):
        return d
    model = model_of(solver, d, solver_cases)
    if model is not None and model in solver_cases:
        return frozenset({model})
    return None if cases_of(solver, d, solver_cases) else frozenset()


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
    solver_cases = shown_cases(runs)
    out: list[Finding] = []
    for entry, judged in judged_entries(runs):
        cases = tuple(c for c in solver_cases
                      if runs.outcome(entry, c) == gives(judged))
        if cases:
            out.append(Finding(Kind.DRIFT, entry_at(runs, entry), DriftPayload(
                case_set(runs, cases), judged, gives(judged))))
    return out


@quotes("procedure.md", "Witness",
        "Run the solver against `witnesses.json`: `uv run python "
        "scripts/run_dl.py witness <task_id> --file "
        "work/task/<task_id>/witnesses.json`.")
@quotes("procedure.md", "Witness",
        "A branch whose model's output differs from the one `witnesses.json` "
        "gives the branch is an error in the solver to fix, unless "
        "`witnesses.json` erred; then it goes in the review as a departure, "
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
    for entry, judged in judged_entries(runs):
        got = runs.outcome(entry, concept)
        if not is_result(got):
            continue
        if got != gives(judged):
            out.append(Finding(Kind.CONCEPT, entry_at(runs, entry),
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
        for n in names_in(solver.engine, entry.separates):
            if n in written:
                continue
            case = model_named(solver, n, solver_cases)
            if case is None or isinstance(case, NameFault) \
                    or case not in solver_cases or case in named \
                    or not is_shown(runs, case):
                continue
            out.append(Finding(Kind.SEPARATES, entry_at(runs, entry),
                               SeparatesPayload(n)))
    return out


# The `@witness` lines


def _lines_by_id(solver: Solver) -> list[list[WitnessLine]]:
    """The `@witness` lines of each id, in the order the annotations hold
    them."""
    out: dict[str, list[WitnessLine]] = {}
    for w in solver.annotations.witnesses:
        out.setdefault(w.id, []).append(w)
    return list(out.values())


def _merged_witnesses(solver: Solver) -> list[WitnessLine]:
    """The `@witness` lines, one per id, the first line's, with the
    `@reassigned` and `@relaxed` lines of every line of the id."""
    out: list[WitnessLine] = []
    for first, *rest in _lines_by_id(solver):
        for w in rest:
            first = replace(
                first,
                relaxed=first.relaxed + tuple(
                    s for s in w.relaxed if s not in first.relaxed),
                reassigned=first.reassigned + tuple(
                    s for s in w.reassigned if s not in first.reassigned))
        out.append(first)
    return out


def text_differs(first: WitnessLine, line: WitnessLine) -> Finding:
    """The finding at the `@witness` line `line` whose plausibility or
    verdict differs from those of `first`, the first line of its id."""
    return Finding(Kind.ANNOTATION, AtLine(line.line),
                   WitnessTextDiffers(line.id, first.line, first.plausibility,
                                      first.verdict))


def _differing_witness_text(solver: Solver) -> list[Finding]:
    """A finding at each `@witness` line whose plausibility or verdict
    differs from those of the first line of its id
    (`solver.names.witness_verdict`). Where the id is an entry of the task's
    witness file, a line of the same plausibility where one of the two
    verdicts is `other` is no finding: `load` gives the fault
    `VERDICTS_DISAGREE` for that id."""
    file = solver.witness_file
    out: list[Finding] = []
    for id in dict.fromkeys(w.id for w in solver.annotations.witnesses):
        got = witness_verdict(solver, id)
        if not isinstance(got, LinesDiffer):
            continue
        first = got.first
        faulted = file is not None and file.entry(id) is not None
        out += [text_differs(first, w) for w in got.differing
                if not (faulted and w.plausibility == first.plausibility
                        and VerdictWord.OTHER in (w.verdict, first.verdict))]
    return out


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
@quotes("principles.md", "Witnesses",
        "**verdict**: the annotator's judgment of the output that the "
        "generator would pair with the witness.")
def check_witness_lines(solver: Solver, runs: Runs) -> list[Finding]:
    """Each `@witness` line gives a plausibility and a verdict that agree
    with those of the first line of its id (`_differing_witness_text`),
    which `_merged_witnesses` keeps.
    The `@witness` lines and the witness file agree: each line's id is an
    entry of the file; the `@reassigned` lines of a witness name the
    parameters its `assign` changes; each `@relaxed` line of a `@witness`,
    `@derive` or `@store` line names a scene claim of the header.
    A given file is not the task's, and its entries are not read here; with no
    witness file, there is nothing to compare. Where the header's claims are
    unknown (`_header_claims`), no `@relaxed` line is checked, and the fault
    that says so is `fault_findings`'s."""
    out: list[Finding] = _differing_witness_text(solver)
    if runs.given is not None or solver.witness_file is None:
        return out
    claims = _header_claims(solver, runs)
    kinds = None if isinstance(claims, Fault) \
        else {c.slug: c.kind for c in claims}

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
                out.append(Finding(Kind.ANNOTATION, entry_at(runs, entry),
                                   ReassignedMismatch(w.id, w.reassigned,
                                                      assigned)))
        relaxed(entry_at(runs, entry) if entry is not None else AtLine(w.line),
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
    verdict's. A case whose branch has a `@rule` line of the claim's
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
                    or not is_shown(runs, case):
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
        if any(not is_result(o) for o in outs) or not defined(outs[0]):
            continue
        if all(differ(o, outs[0]) for o in outs[1:]) and (
                judged is None or outs[0] != gives(judged)):
            out.append(Finding(Kind.ANNOTATION, AtLine(w.line),
                               StandsElsewhere(
                                   w.id, tuple(k for k, _v in entry.assign))))
    return out


@quotes("solver-file.md", "Cases",
        "**`impl_choice`.** The relation that enumerates the cases is "
        "`impl_choice`, and its column is `ch`.")
@quotes("principles.md", "Choice points and open parameters",
        "The **concept branch** at a choice point is the branch taken by the "
        "claims the point stands under.")
def check_concept_enumerated(solver: Solver, runs: Runs) -> list[Finding]:
    """The concept case is one of the solver's cases: `impl_choice`
    enumerates the cases, and every check that reads the concept case reads
    it among them. A concept case `impl_choice` leaves out is a finding."""
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
