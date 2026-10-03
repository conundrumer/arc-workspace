"""The `derive` survey (procedure.md, under "Develop"): the built-in derivations of
the solver's stored parameters that fit, each a branch, with its witness,
and the findings on the solver's `@derive` lines."""

import threading
from dataclasses import dataclass, replace

from arc.task import Example, Task
from checker.branches import (
    BuiltBy,
    RecordedWitness,
    SwapWitness,
    Unwitnessed,
    Witness,
    bare_ignored,
    entry_findings,
    excluded_finding,
    idle_ignores,
    model_fit,
    ordered,
    recorded_entry,
    recorded_witness,
    swap_entry,
    swap_witness,
    taking,
    with_line,
    without_named_ignores,
)
from checker.finding import (
    AtFile,
    AtLine,
    AtPair,
    AtParameter,
    Finding,
    Kind,
    RunKind,
    Where,
    WholeFile,
)
from checker.judged import (
    NO_TASK,
    Fits,
    Misses,
    NoResult,
    concept_case,
    enumeration_failed,
    no_result,
)
from checker.payloads.branches import (
    BranchPayload,
    DeriveFitPayload,
    DuplicatePayload,
    MissingLinePayload,
    Unread,
)
from checker.readable import finding_of
from checker.runs import Runs
from engine import Program, RunFailure
from solver.annotations import DeriveLine, IgnoreForm
from solver.model import (
    Case,
    DeriveBranch,
    Parameter,
    Solver,
    declaration_of,
    own,
    proposer_names,
    Graph,
    proposers_program,
)
from solver.names import branch_text
from solver.problems import (
    Fault,
    InSolver,
    ProblemKind,
    Undecided,
    UndecidedForm,
)
from solver.solve import (
    Proposals,
    at_once,
    parameter_reading,
    examples,
    probe,
    probe_failure,
)
from solver.vocabulary import COLOR, PROPOSE
from solver.witness import Entry


@dataclass(frozen=True)
class Proposer:
    """A proposer of `programs/proposers.dl`: the column types of its
    `propose` relation with every alias resolved, and the comment above
    its component, as the `derive` report states it."""

    name: str
    types: tuple[str, ...]
    comment: str


def proposers(program: Program) -> dict[str, Proposer]:
    """Each proposer of the proposers program by name
    (`solver.model.proposer_names`)."""
    out: dict[str, Proposer] = {}
    graph = Graph(program)
    for name in proposer_names(program):
        comp = next(c for c in program.components if c.name == name)
        decl = next(r for r in program.relations
                    if r.name == PROPOSE and r.scope.components[-1:] == (name,))
        lines = sorted((c.line, c.text.strip()) for c in program.comments
                       if c.above == comp.id and not c.block)
        text = " ".join(t for _l, t in lines if t).rstrip(".")
        out[name] = Proposer(
            name, tuple(graph.resolve_type(c.type, decl.scope.components)
                        for c in decl.columns),
            text[:1].lower() + text[1:])
    return out


# How a derivation's model meets Fit, where it is not judged


@dataclass(frozen=True)
class Excluded:
    """The `@ignore: derive <name>` lines under the branch's `@derive`
    line exclude every case that takes it, so no case of the solver runs."""


@dataclass(frozen=True)
class Unplaced:
    """No `.decl` of the parameter in the solver's `Params`, and no RIGID
    call whose chart it is, has a place for a `@derive` line."""


type DeriveFit = Fits | NoResult | Excluded | Unread | Unplaced
"""How a derivation's model meets Fit; `Unread`, no case of the solver
reads the parameter, so the model is the concept case's
(`Derivation.concept`)."""


@dataclass(frozen=True)
class Derivation:
    """One parameter read off the input by one proposer whose model does
    not miss Fit (procedure.md, under "Develop"): how its model meets Fit, its
    `@derive` line where one stands, the RIGID block whose chart the
    parameter is, whether a bare `@ignore: derive` line stands in its
    place, or an `@ignore: derive <Proposer>` line of its proposer,
    whether the witness file holds the entry of its name, the swap
    witness the survey sought where it holds none, and the entry built
    from that witness."""

    parameter: str
    proposer: Proposer
    fit: DeriveFit
    line: DeriveLine | None
    rigid: str | None
    ignored: bool
    entry: bool
    witness: Witness | None
    built: Entry | None
    built_by: BuiltBy | None = None
    """What `built` was built from."""
    concept: Fits | NoResult | None = None
    """Where no case of the solver reads the parameter (`Unread`), how the
    concept case's model, the derivation's model then, meets Fit; None
    where no case of the solver is the concept case."""

    @property
    def name(self) -> DeriveBranch:
        return DeriveBranch(self.parameter, self.proposer.name, self.line)


@dataclass(frozen=True)
class DeriveSurvey:
    """The `derive` report of one solver, and the findings on its lines,
    in the order the report prints them."""

    derivations: tuple[Derivation, ...]
    findings: tuple[Finding, ...]


def derivations(runs: Runs, known: dict[str, Proposer]
                ) -> tuple[list[tuple[Parameter, Proposer]], list[Finding]]:
    """Each parameter with a stored value, with each proposer of its
    column types that gives a value on every pair's input, each input
    read alone (solver-file.md, under "Params"; principles.md, under "Stored
    or derived"): Fit, not the stored value, decides which the
    survey reports. The findings are the probe runs that gave no
    result, one per pair."""
    task = runs.solver.given_task
    given: dict[str, int] = {}
    failed: list[Finding] = []
    pairs = list(examples(task))
    probes = at_once(lambda pe: probe(runs.engine, Task(train=[], test=[
        Example(input=pe[1].input, output=[])]), runs.limits), pairs)
    for (pair, _ex), got in zip(pairs, probes, strict=True):
        if not isinstance(got, Proposals):
            failed.append(no_result(got, RunKind.PROBE, None, AtPair(pair)))
            continue
        for name, rows in got.values.items():
            if rows:
                given[name] = given.get(name, 0) + 1
    out: list[tuple[Parameter, Proposer]] = []
    if failed:
        return out, failed
    for p in runs.solver.params.parameters:
        if not isinstance(p.stored, tuple) or not p.stored:
            continue
        types = parameter_reading(runs.solver, p.name).value_types
        for name in sorted(known):
            if known[name].types == types and given.get(name) == len(pairs):
                out.append((p, known[name]))
    return out, failed


def _synthetic(parameter: Parameter, proposer: str) -> DeriveBranch:
    """The branch a `@derive` line of `proposer` would hold on
    `parameter`, as the `derive` survey judges a derivation with its line
    standing: a branch no line holds yet."""
    return DeriveBranch(parameter.name, proposer, None)


def _chart(solver: Solver, p: Parameter) -> str | None:
    return declaration_of(solver.program, p).chart_of


def _placed(solver: Solver, p: Parameter) -> bool:
    decl = declaration_of(solver.program, p)
    return own(decl.span) or decl.chart_of is not None


def _one_color(solver: Solver, p: Parameter) -> int | None:
    """The one color the parameter stores: its one fact's, and for a
    parameter that stores a value per case (`per_case`), the one color
    every case stores; None where it stores other values."""
    stored = p.stored
    if not isinstance(stored, tuple):
        return None
    pc = parameter_reading(solver, p.name)
    types = pc.value_types
    if pc.case:
        stored = tuple(dict.fromkeys(pc.value(r) for r in stored))
    if len(stored) == 1 and types == (COLOR,) \
            and isinstance(stored[0][0], int):
        return stored[0][0]
    return None


def _unresulted(fit: NoResult, where: Where) -> list[Finding]:
    """The runs of a Fit that rests on no result, one finding per pair
    (`checker.judged.NoResult`)."""
    return [no_result(f, RunKind.PAIR, fit.case, where) for _p, f in fit.pairs]


@dataclass(frozen=True)
class _One:
    """One candidate's derivations and findings, whether it read the
    concept's Fit, and which of its derivations show that Fit."""

    out: list[Derivation]
    findings: list[Finding]
    reached: bool
    late: list[int]


def derive_survey(runs: Runs) -> DeriveSurvey:
    """The `derive` report (procedure.md, under "Develop"): each derivation of a
    stored parameter whose model does not miss Fit, and the findings on
    the solver's `@derive` lines and on the derivations."""
    solver = runs.solver
    solver_cases = runs.cases
    if not isinstance(solver_cases, tuple):
        return DeriveSurvey((), (enumeration_failed(solver_cases),))
    parsed = proposers_program(runs.engine)
    if not isinstance(parsed, Program):
        return DeriveSurvey((), (no_result(
            probe_failure(parsed), RunKind.PROBE, None,
            AtFile(WholeFile.SOLVER)),))
    if solver.task is None:
        return DeriveSurvey((), (NO_TASK,))
    known = proposers(parsed)
    lined = {(b.parameter, b.proposer): b for b in solver.branches
             if isinstance(b, DeriveBranch)}
    findings: list[Finding] = []
    first: dict[tuple[str, str], int] = {}
    judged: dict[tuple[str, str], Fits | NoResult | Excluded] = {}
    misfits: set[tuple[str, str]] = set()
    unwitnessed: set[tuple[str, str]] = set()
    unnamed: tuple[Case, ...] | RunFailure | None = None
    ignored = {(t.name, p) for t, p in bare_ignored(solver,
                                                    IgnoreForm.DERIVE)}
    for d in solver.annotations.derives:
        above = None if d.above is None \
            else solver.program.relation(d.above)
        if above is None:
            continue
        param = above.name
        key = (param, d.proposer)
        branch = lined.get(key)
        if branch is None or d.proposer not in known:
            continue
        if key in first:
            findings.append(Finding(
                Kind.DUPLICATE_BRANCH_LINE, AtLine(d.line),
                DuplicatePayload(branch, first[key], d.line)))
            continue
        first[key] = d.line
        if key in ignored:
            # The fault `TWO_LINES_ON_DERIVATION` stands on the pair.
            continue
        cases = taking(solver, solver_cases, branch)
        every = runs.solver_cases
        if not cases and isinstance(every, tuple) \
                and taking(solver, every, branch):
            unwitnessed.add(key)
            findings.append(finding_of(Fault(
                ProblemKind.UNDECIDED, InSolver(d.line),
                Undecided(UndecidedForm.BRANCH_UNWITNESSED, None))))
            continue
        if not cases:
            if unnamed is None:
                unnamed = without_named_ignores(runs, solver)
            if not isinstance(unnamed, tuple):
                findings.append(no_result(unnamed, RunKind.CASE, None,
                                          AtLine(d.line)))
                continue
            excluded = excluded_finding(runs, solver, branch, AtLine(d.line))
            if excluded is not None:
                findings.append(excluded)
            if taking(solver, unnamed, branch):
                judged[key] = Excluded()
            elif excluded is None:
                findings.append(Finding(Kind.DERIVE_UNREAD, AtLine(d.line),
                                        BranchPayload(branch)))
            continue
        line_fit = model_fit(runs, solver, ordered(solver, cases, branch))
        if isinstance(line_fit, Misses):
            misfits.add(key)
            findings.append(Finding(Kind.DERIVE_FIT, AtLine(d.line),
                                    DeriveFitPayload(branch, line_fit.pair)))
            continue
        if isinstance(line_fit, NoResult):
            findings += _unresulted(line_fit, AtLine(d.line))
        if line_fit is not None:
            judged[key] = line_fit
    findings += idle_ignores(runs, IgnoreForm.DERIVE)
    concept: list[Fits | Misses | NoResult | None] = []
    concept_lock = threading.Lock()
    found, failed = derivations(runs, known)
    findings += failed

    def one(param: Parameter, prop: Proposer) -> _One:
        """The derivation of `param` by `prop` and the findings on it."""
        out: list[Derivation] = []
        findings: list[Finding] = []
        reached: list[bool] = []
        late: list[int] = []
        key = (param.name, prop.name)
        if key in misfits or key in unwitnessed:
            return _One(out, findings, bool(reached), late)
        rigid = _chart(solver, param)
        is_ignored = ((param.name, None) in ignored or key in ignored) \
            and key not in judged
        branch = lined.get(key) if key in judged else None
        if branch is not None:
            line: DeriveLine | None = branch.line
            fit: DeriveFit = judged[key]
            lined_solver = solver
            every = solver_cases
        else:
            line = None
            if not _placed(solver, param):
                out.append(Derivation(param.name, prop, Unplaced(), None,
                                      rigid, is_ignored, False, None, None))
                findings.append(Finding(Kind.DERIVE_UNPLACED,
                                        AtParameter(param.name),
                                        BranchPayload(_synthetic(
                                            param, prop.name))))
                return _One(out, findings, bool(reached), late)
            branch = _synthetic(param, prop.name)
            lined_solver = with_line(solver, branch)
            got = runs.lined(lined_solver, branch)
            if not isinstance(got, tuple):
                findings.append(no_result(got, RunKind.CASE, None,
                                          AtParameter(param.name)))
                return _One(out, findings, bool(reached), late)
            every = got
            cases = taking(solver, every, branch)
            if cases:
                judged_fit = model_fit(runs, lined_solver,
                                       ordered(solver, cases, branch))
                if judged_fit is None or isinstance(judged_fit, Misses):
                    return _One(out, findings, bool(reached), late)
                if isinstance(judged_fit, NoResult):
                    findings += _unresulted(judged_fit,
                                            AtParameter(param.name))
                fit = judged_fit
            else:
                reached.append(True)
                with concept_lock:
                    if not concept:
                        concept.append(_concept_fit(runs, solver,
                                                    solver_cases))
                if isinstance(concept[0], Misses):
                    return _One(out, findings, bool(reached), late)
                fit = Unread()
        ref = branch
        name = branch_text(branch)
        if is_ignored or not isinstance(fit, Fits):
            out.append(Derivation(
                param.name, prop, fit, line, rigid, is_ignored, False, None,
                None, concept=None))
            late.append(len(out) - 1)
            return _One(out, findings, bool(reached), late)
        cases = taking(solver, every, branch)
        entry = runs.branch_entry(branch)
        witness: Witness | None = None
        built: Entry | None = None
        if entry is not None:
            findings += entry_findings(runs, lined_solver, branch, ref, name,
                                       cases, entry)
        else:
            swap = swap_witness(runs, lined_solver, cases, branch,
                                _one_color(solver, param))
            if isinstance(swap, SwapWitness):
                witness = swap
            else:
                recorded = recorded_witness(runs, lined_solver, cases, branch)
                witness = Unwitnessed(swap) if recorded is None else recorded
            if isinstance(witness, (SwapWitness, RecordedWitness)):
                if isinstance(witness, SwapWitness):
                    made: Entry | RunFailure = swap_entry(
                        runs, lined_solver, name, ref, witness.swap.index,
                        witness.swap, witness.swap.grid, every)
                else:
                    made = recorded_entry(runs, lined_solver, name, ref,
                                          witness.entry, every)
                built = made if isinstance(made, Entry) else None
        if line is None:
            findings.append(Finding(Kind.MISSING_BRANCH_LINE,
                                    AtParameter(param.name),
                                    MissingLinePayload(ref)))
        out.append(Derivation(param.name, prop, fit, line, rigid, False,
                              entry is not None, witness, built,
                              None if built is None
                              else BuiltBy(lined_solver, every)))
        return _One(out, findings, bool(reached), late)

    # The candidates run at once and are read in order: a derivation the
    # concept's Fit stands beside shows it once a candidate before it, or
    # itself, read it, as when they ran one after another.
    out: list[Derivation] = []
    read_concept = False
    for got in at_once(lambda f: one(*f), found):
        read_concept = read_concept or got.reached
        shown = concept[0] if read_concept and concept \
            and not isinstance(concept[0], Misses) else None
        out += [replace(d, concept=shown) if i in got.late else d
                for i, d in enumerate(got.out)]
        findings += got.findings
    return DeriveSurvey(tuple(out), tuple(findings))


def _concept_fit(runs: Runs, solver: Solver, solver_cases: tuple[Case, ...]
                 ) -> Fits | Misses | NoResult | None:
    """How the concept case's model meets Fit: the model of a derivation
    of a parameter no case of the solver reads. None where no case of the solver is the
    concept case."""
    concept = concept_case(solver, solver_cases)
    return model_fit(runs, solver, [] if concept is None else [concept])
