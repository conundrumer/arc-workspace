"""The solver's cases: the bases `impl_choice` enumerates, each with the
branches of the `@derive` and `@store` points its derivation of `out` reads."""

from dataclasses import replace
from itertools import product

from engine import Engine, Limits, RelationName, RunFailure
from solver.annotations import IgnoreForm
from solver.dependence import Dependence, dependence
from solver.model import (
    Base,
    Branch,
    Case,
    DeriveBranch,
    StoreBranch,
    every_base,
)
from solver.aggregate import Solver, branch_under, enumerated, enumerates
from solver.readers import ignore_targets
from solver.columns import ident_keyed



def cases(solver: Solver, engine: Engine, limits: Limits
         ) -> tuple[Case, ...] | RunFailure:
    """The solver's cases, in enumeration order, or the failure of
    the run that enumerates them.

    The solver's cases are the bases that `impl_choice` enumerates, read from a
    run on the empty input since the enumeration is a clause, each combined
    with every choice of branch at the `@derive` and `@store` points whose
    parameter or relation the base's derivation of `out` depends on
    (`dependence`; docs/handbook/solver-file.md#params,
    docs/handbook/solver-file.md#program), minus each case that an
    `@ignore: derive` or `@ignore: store` line excludes: the bare form excludes
    every case that takes the branch in its place, every derivation of the
    parameter for the derive form; `@ignore: derive <Proposer>` every case that
    takes that one derivation; and a named form, under a `@derive` or `@store`
    line, every case that takes that line's branch and every branch its
    `<name>` contains (`solver.names.cases_of`;
    docs/handbook/solver-file.md#params, docs/handbook/solver-file.md#program;
    history "The runner holds cases the solver does not write" and 1103), and
    minus each case that takes a `@store` branch on a relation with an `Ident`
    column (`ident_keyed`); the `@store` line on such a relation is a finding
    of the store check that fails the command. The handbook does not define the
    solver's cases in one place; this docstring is where the definition stands.

    A `Choice` with no `impl_choice` relation has every combination of
    its fields as a case (docs/handbook/solver-file.md#cases)."""
    from solver.names import Denoted, cases_of, denote

    choice = solver.choice
    bases: tuple[Base | None, ...]
    if choice is None:
        bases = (None,)
    elif enumerates(solver.program):
        got = enumerated(engine, solver.program, limits)
        if not isinstance(got, tuple):
            return got
        bases = got
    else:
        every = every_base(choice)
        bases = () if every is None else every
    read = dependence(engine, solver, bases) if solver.branches \
        else Dependence({}, {}, {})
    relations = {r: set(b) for r, b in read.relations.items()}
    order = {b: i for i, b in enumerate(solver.branches)}
    cases: list[Case] = []
    for base in bases:
        points: list[list[Branch | None]] = []
        at: dict[str, int] = {}
        for b in solver.branches:
            if isinstance(b, DeriveBranch) \
                    and read.reads_parameter(base, b.parameter):
                if b.parameter not in at:
                    at[b.parameter] = len(points)
                    points.append([None])
                points[at[b.parameter]].append(b)
            elif isinstance(b, StoreBranch) \
                    and base in relations.get(b.relation, ()):
                points.append([None, b])
        cases += [Case(base, tuple(sorted((b for b in combo if b is not None),
                                          key=lambda b: order[b])))
                  for combo in product(*points)]
    excluded: list[Denoted] = []
    bare: list[tuple[IgnoreForm, RelationName, str | None]] = []
    for i in solver.annotations.ignores:
        if i.form is IgnoreForm.LINT:
            continue
        if i.name is None:
            bare += [(i.form, t, i.proposer)
                     for t in ignore_targets(solver.program, i)]
            continue
        denoted = denote(solver, i.name)
        if isinstance(denoted, Denoted):
            under = branch_under(solver, i)
            if under is not None and under not in denoted.branches:
                denoted = replace(denoted,
                                  branches=(*denoted.branches, under))
            excluded.append(denoted)

    keyed = {b.relation for b in solver.branches
             if isinstance(b, StoreBranch)
             and ident_keyed(engine, solver.program, b.relation)}

    def out(case: Case) -> bool:
        if any(isinstance(b, StoreBranch) and b.relation in keyed
               for b in case.branches):
            return True
        for form, target, proposer in bare:
            for b in case.branches:
                if form is IgnoreForm.DERIVE and isinstance(b, DeriveBranch) \
                        and RelationName((), b.parameter) == target \
                        and proposer in (None, b.proposer):
                    return True
                if form is IgnoreForm.STORE and isinstance(b, StoreBranch) \
                        and b.relation == target:
                    return True
        return False

    named = {c for d in excluded for c in cases_of(solver, d, cases)}
    return tuple(c for c in cases if not out(c) and c not in named)
