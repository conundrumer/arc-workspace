"""The relations the `store` survey reads: those between `in` and `out`,
and the clauses that feed a relation."""

from engine import (
    DeclId,
    Index,
    RelationName,
    Resolved,
    Scope,
)
from engine.program import Qualifier, Unit
from solver.aggregate import TOP, Solver
from solver.dependence import Dependence
from solver.graph import Graph
from solver.vocabulary import RUN_RELATIONS

SKIP = frozenset(r.name for r in RUN_RELATIONS)
"""The names of the run's own relations, which no survey proposes."""


def declaration(index: Index, rel: RelationName, scope: Scope
                ) -> DeclId | None:
    got = index.resolve(rel, scope)
    return got.declaration if isinstance(got, Resolved) else None


def between(solver: Solver, index: Index, rd: Dependence
            ) -> tuple[RelationName, ...]:
    """The relations between `in` and `out`: each relation a base's
    derivation of `out` depends on (`dependence`) whose rows depend on
    `in` by dataflow, relation by relation, a lib instance's relations
    each on their own (`solver.graph.Graph.reads_input`), by the name a
    top-level clause reads it by, but the run's own relations and the
    inline ones."""
    graph = Graph(solver.program, solver.engine)
    out: list[RelationName] = []
    for rel in rd.relations:
        d = declaration(index, rel, TOP)
        r = None if d is None else solver.program.relation(d)
        if r is None or not graph.reads_input(rel) \
                or rel.name in SKIP \
                or Qualifier.INLINE in r.qualifiers:
            continue
        out.append(rel)
    return tuple(sorted(out, key=lambda r: r.text))


def feeding(solver: Solver, index: Index, decl: DeclId) -> list[Unit]:
    """The clauses that put rows into a relation, through the engine's
    index; a subsumptive clause puts none in."""
    return [u for occ in index.feeding(decl)
            if (u := solver.program.unit(occ.unit)) is not None
            and not u.subsumptive]

