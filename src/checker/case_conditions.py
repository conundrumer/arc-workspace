"""The checks of the case conditions the witness file is the evidence for
(principles.md, under "Cases")."""

from collections.abc import Sequence
from dataclasses import dataclass

from checker.finding import (
    AtCase,
    AtFile,
    Finding,
    Kind,
    RunKind,
    WholeFile,
)
from checker.judged import (
    Misses,
    enumeration_failed,
    fit,
    no_result,
)
from checker.payloads.witness import (
    CaseSet,
    Condition,
    DroppedPayload,
    PointBranch,
    SubsumedPayload,
    UnjustifiedDropPayload,
    UnseparatedPayload,
)
from checker.runs import Runs
from checker.witness_reads import (
    Inputs,
    alone_outcomes,
    case_pairs,
    case_set,
    defined,
    emits_nothing,
    is_shown,
    pair_failures,
    reads_inputs,
    recorded_outcomes,
    shown_cases,
    subsumes,
    unseparated_pairs,
)
from engine.quotes import quotes
from solver.aggregate import (
    Solver,
    is_concept_case,
)
from solver.model import (
    Case,
    ConstructorBranch,
    DeriveBranch,
    DerivedAtStore,
    StoreBranch,
    StoredAtDerive,
    constructor_at,
    is_concept_branch,
    point_at,
)
from solver.names import (
    cover,
)
from solver.outcome import Grids, is_result
from solver.witnessed_cases import taken
from solver.problems import (
    Fault,
)
from solver.witness import (
    Undefined,
)


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
    shown = shown_cases(runs)
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
    failures = pair_failures(runs) if reads_inputs(runs) else []
    return failures + unseparated_findings(solver, runs)


def unseparated_findings(solver: Solver, runs: Runs, every: bool = False
                         ) -> list[Finding]:
    """One finding per branch difference among the pairs of shown cases
    no witness separates (`unseparated_pairs`), each pair of the finding's
    contexts that differs at it alone (`_spanning`), every pair with
    `every`."""
    pairs = [(a, b) for a, b in unseparated_pairs(runs, recorded_outcomes(runs))
             if is_shown(runs, a) and is_shown(runs, b)]
    return _by_difference(solver, runs, pairs, set(pairs) if every
                          else _spanning(solver, runs, pairs), False,
                          Kind.UNSEPARATED)


def _subsumers(solver: Solver, inputs: Inputs, a: Case,
               others: Sequence[Case]) -> list[Case]:
    """The cases of `others` that subsume `a`, less each that subsumes
    another of them; none for the concept case (principles.md, under "Cases")."""
    if is_concept_case(solver, a):
        return []
    partners = [b for b in others if b != a and subsumes(inputs, a, b)]
    return [b for b in partners
            if not any(subsumes(inputs, c, b) for c in partners if c != b)]


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
    if not reads_inputs(runs):
        return []
    return subsumed_findings(solver, runs)


def subsumed_findings(solver: Solver, runs: Runs, every: bool = False
                      ) -> list[Finding]:
    """One finding per branch difference among the pairs of a shown case
    and a case that subsumes it (`_subsumed_pairs`), each subsumed case
    with its nearest subsumer, every pair with `every`."""
    pairs, nearest = _subsumed_pairs(solver, runs)
    return _by_difference(solver, runs, pairs, set(pairs) if every
                          else nearest, True, Kind.SUBSUMED)


def _same(runs: Runs, inputs: Inputs) -> set[frozenset[Case]]:
    """The pairs of cases no witness separates (`unseparated_pairs`), each as
    a set."""
    return {frozenset(p) for p in unseparated_pairs(runs, inputs)}


def _subsumed_pairs(solver: Solver, runs: Runs
                    ) -> tuple[list[tuple[Case, Case]], set[tuple[Case, Case]]]:
    """Each shown case with each case that subsumes it (`_subsumers`),
    and of those pairs, each subsumed case with the subsumer that differs
    from it at the fewest points."""
    inputs = recorded_outcomes(runs)
    same = _same(runs, inputs)
    solver_cases = shown_cases(runs)
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
    inputs = recorded_outcomes(every)
    same = _same(every, inputs)
    others = [c for b in every.batches(solver_cases) for c in b]
    unjustified: list[Finding] = []
    failing: list[Finding] = []
    unread = [] if ran is runs and reads_inputs(every) \
        else pair_failures(every)
    lone = [a for a in judged
            if not a.branches and a.base not in kept_bases and inputs
            and all(is_result(got[a]) for got in inputs)
            and all(emits_nothing(got[a]) for got in inputs)]
    by_alone = alone_outcomes(every, lone)
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
        judged = fit(case_pairs(every.alone(a) if a in by_alone else every,
                                 a), [a])
        if outs and all(emits_nothing(o) for o in outs):
            failing.append(Finding(Kind.DROPPED, where, DroppedPayload(
                a, Condition.NOT_RUN, None)))
        elif outs and not any(defined(o) for o in outs):
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
                    a, case_set(every, [b for b in others
                                         if frozenset((a, b)) in same]))))
    return unread + unjustified + failing
