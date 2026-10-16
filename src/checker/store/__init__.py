"""The `store` survey (procedure.md, under "Develop"): each program
relation between `in` and `out` whose projection onto some of its columns
is the same on every input of the task, with its witness, and the
findings on the solver's `@store` lines and on those relations. This
module runs the survey.

`checker.store.relations` holds the relations the survey reads;
`checker.store.survey` the values the survey finds and what it judges of
each; `checker.store.stored` whether a value is stored already, and
whether the concept case reads it; `checker.store.witness` the witness of
a value and the search for it; `checker.store.lines` the findings on the
`@store` lines and on the values. `relations` imports no other module of
the package, `survey` imports none at its top level, and `stored`,
`witness` and `lines` import `survey`.

The survey reads, beside the relations between `in` and `out`, each
relation a `@store` line names that the derivation of `out` reads, so
that the line is judged and its witness searched as any other; the values
the survey asks for a `@store` line are `Found.asks_line`'s."""

from collections.abc import Mapping, Sequence

from checker.branches.ignores import bare_ignored
from checker.finding import AtFile, AtPair, Finding, Kind, RunKind, WholeFile
from checker.judged import (
    NO_TASK,
    base_names,
    concept_among,
    enumeration_failed,
    no_result,
)
from checker.payloads.branches import NotCheckedPayload, RowCapPayload
from checker.runs import Runs
from checker.store.lines import line_findings
from checker.store.relations import between, store_line_relations
from checker.store.stored import (
    StoredAlready,
    concept_runs,
    concept_section,
    read_back,
    stored_already,
)
from checker.store.survey import ROW_CAP, Found, StoreSurvey, ValueKind, analyze
from checker.store.witness import find_witness
from engine import RelationName, Row
from engine.quotes import quotes
from solver.aggregate import Solver, is_concept
from solver.annotations import IgnoreForm
from solver.dependence import ParameterReads, dependence
from solver.graph import Graph
from solver.model import Base, Case, StoreBranch, bases_of, every_base
from engine.program import as_grid
from solver.pair_runs import PairId, examples
from solver.group_runs import at_once


def _bases(solver: Solver, solver_cases: Sequence[Case]
           ) -> tuple[list[Base | None], Base | None]:
    """The bases of the solver's cases, and the concept case's base, added
    where no case of the solver is the concept case."""
    bases = bases_of(solver_cases)
    concept = concept_among(solver, bases)
    if concept is None and solver.choice is not None:
        every = every_base(solver.choice) or ()
        concept = concept_among(solver, every)
        if concept is not None:
            bases.append(concept)
    elif solver.choice is None and not bases:
        bases.append(None)
    return bases, concept


@quotes("procedure.md", "Develop",
        "`uv run python scripts/run_dl.py store <task_id>` lists the derived "
        "values that are the same on every input.")
def survey_store(runs: Runs) -> StoreSurvey:
    """The `store` report (procedure.md, under "Develop"), and the findings
    the audit prints on the `@store` lines and on the values (`StoreSurvey`)."""
    solver = runs.solver
    solver_cases = runs.cases
    if not isinstance(solver_cases, tuple):
        stop = enumeration_failed(solver_cases)
        return StoreSurvey((), (), (stop,), (stop,), True)
    bases, concept = _bases(solver, solver_cases)
    rd = dependence(runs.engine, solver, bases)
    task = solver.task
    rels = tuple(sorted(set(between(solver, runs.index, rd))
                        | set(store_line_relations(solver, runs.index, rd)),
                        key=lambda r: r.text))
    if not rels:
        return StoreSurvey((), (), (), (Finding(
            Kind.NOT_CHECKED, AtFile(WholeFile.SOLVER), NotCheckedPayload()),
            *line_findings(runs, solver, rels, [], [], set(), {},
                           solver_cases)), False)
    if task is None:
        stop = NO_TASK
        return StoreSurvey((), (), (stop,), (stop,), True)
    failed: list[Finding] = []
    per_input: list[Mapping[RelationName, tuple[Row, ...]]] = []
    labels: list[PairId] = []
    exs = list(examples(task))
    values = at_once(lambda pe: runs.defined_relations(as_grid(pe[1].input),
                                                   rels, ROW_CAP), exs)
    for (pair, _ex), got in zip(exs, values, strict=True):
        if isinstance(got, Mapping):
            per_input.append(got)
            labels.append(pair)
        else:
            failed.append(no_result(got, RunKind.STORE_SEARCH, None,
                                    AtPair(pair)))
    # A value is one value on every input only where every input ran: an
    # input whose run failed or timed out leaves every relation unjudged.
    if failed:
        return StoreSurvey((), (), tuple(failed), tuple(failed), True)
    found, capped = analyze(solver, runs, rels, per_input, bases, rd)
    differs = {p: next((labels[i] for i, g in enumerate(per_input)
                        if set(g.get(p, ())) != set(per_input[0].get(p, ()))),
                       None) for p in rels}
    lines = {b.relation: b for b in solver.branches
             if isinstance(b, StoreBranch)}
    ignored = {t for t, _p in bare_ignored(solver, IgnoreForm.STORE)}
    stored = StoredAlready(solver, runs.index)
    reads = ParameterReads(solver.engine, solver)
    graph = Graph(solver.program, solver.engine)
    among = bases_of(solver_cases)
    for f in found:
        f.case_names = base_names(solver, [c.base for c in f.cases], among)
        f.line = lines.get(f.relation)
        if f.line is not None:
            f.spelled = f.line.spelled
        f.ignored = f.line is None and f.relation in ignored
        by = rd.relations.get(f.relation, ())
        f.read = concept in by or (solver.choice is None and bool(by))
        f.used_in = () if f.read else base_names(solver, [
            b for b in by if not is_concept(solver, b)], bases)
        f.stored = stored_already(solver, runs, stored, f)
        if not f.stored and f.kind is ValueKind.OWNED:
            f.reads_back = read_back(solver, reads, f)
            f.stored = bool(f.reads_back)
        if f.case_values:
            f.concept = concept in f.bases
            f.concept_stored = f.concept and stored_already(
                solver, runs, stored, f, concept, every=False)
        else:
            f.concept = concept_runs(solver, runs, rd, f.decl, concept)
            f.concept_stored = f.concept and f.stored
            f.concept_section = concept_section(solver, graph, f, concept)
        if f.reads_back:
            f.concept_stored = f.concept
    wanted = [f for f in found if f.store_branch]
    spelled: dict[str, set[RelationName]] = {}
    for f in wanted:
        spelled.setdefault(f.name.spelled, set()).add(f.relation)
    for f in wanted:
        f.homonyms = tuple(sorted(spelled[f.name.spelled] - {f.relation},
                                  key=lambda p: p.text))
    searched: list[Found] = []
    for f in wanted:
        if f.homonyms:
            continue
        if runs.branch_entry(f.name) is not None:
            f.entry = True
            continue
        searched.append(f)
    relations = list(dict.fromkeys(f.relation for f in searched))
    for stop in at_once(lambda f: find_witness(runs, solver, f, relations),
                        searched):
        if stop is not None:
            failed.append(stop)
    empty = {p for p in rels if all(not g.get(p) for g in per_input)}
    findings = [*failed, *line_findings(
        runs, solver, rels, found, capped, empty, differs, solver_cases)]
    if capped:
        findings.append(Finding(Kind.STORE_ROW_CAP, AtFile(WholeFile.SOLVER),
                                RowCapPayload(tuple(capped), ROW_CAP)))
    return StoreSurvey(tuple(found), tuple(capped), tuple(failed),
                       tuple(findings), True)


