"""The lint check on recursion: each cycle among the relations a solver's
program runs, at each instance, that a clause of the solver's own text
closes, less the reads that `Take`'s contract permits."""

from dataclasses import dataclass

from checker.finding import Finding, LintNamed, LintSentence
from checker.lint.view import lint, view
from checker.runs import Runs
from engine import RelationName, UnitId
from engine.program import Atom, Unit, body_atoms, own
from engine.quotes import quotes
from solver.aggregate import Solver
from solver.category import Category
from solver.cycles import cyclic_components
from solver.graph import Graph, InstancePath
from solver.determine import run_program

RECURSIVE_INPUTS: dict[str, frozenset[str]] = {
    "Take": frozenset({"step", "skip", "take"}),
}
"""The lib components whose inputs a solver clause may define from the
instance's own relations, each with those inputs: `Take`'s doc in
`programs/lib/orders.dl` and `docs/lib-spec.md` give the contract."""


@dataclass(frozen=True)
class _Edge:
    """A read by a unit of the solver's own text, at an instance path it
    runs at: the relation its atom reads, and the relation it heads."""

    unit: Unit
    at: InstancePath
    atom: Atom
    read: RelationName
    head: RelationName


def _permitted(solver: Solver, graph: Graph, e: _Edge) -> bool:
    """Whether the read heads an input of a lib component's instance that
    `RECURSIVE_INPUTS` permits, reads a relation of that same instance,
    and the rest of its clause grounds every variable of its atom
    (`engine.Engine.grounded_without`). An atom that stands inside an
    aggregate is not permitted."""
    path = e.head.instances
    if not path or e.read.instances != path:
        return False
    comp = graph.components[graph.tree[path]]
    if own(comp.span) \
            or e.head.name not in RECURSIVE_INPUTS.get(comp.name, frozenset()):
        return False
    try:
        return solver.engine.grounded_without(graph.program, e.unit, e.atom)
    except ValueError:
        return False


@quotes("style.md", "Bans",
        "**Recursion.** Recursion is banned in every clause of the solver: "
        "a clause reads no relation of its own stratum.")
@quotes("style.md", "Bans",
        "A closure is an instance of a lib construction.")
@quotes("style.md", "Bans",
        "A clause that defines the `step`, `skip` or `take` input of a "
        "`Take` instance may read that instance's relations through an atom "
        "whose every variable another atom of the clause grounds.")
@quotes("style.md", "Components",
        "**Proposal comps.** The program-style checks skip a proposal comp.")
def check_recursion(solver: Solver, runs: Runs) -> list[Finding]:
    """One finding per set of units of the solver's own text, each in a
    program scope (`checker.lint.view.View.program_scope`), that close a
    cycle of the relations of the program its runs run
    (`solver.determine.run_program`), each relation at the instance path
    that declares it, the lib's units read at each instance they run at.
    A unit closes a cycle where it reads, at an instance it runs at, a
    relation of the cycle to head a relation of the cycle, by a read
    `_permitted` does not permit. The finding stands at the line of the
    first such unit, on each such unit, and names the cycle's relations by
    their text, in the order of that text, where a relation of the instance
    a run adds is named by its text inside that instance, as the solver's
    `.comp Determine` names it. Where cycles at several instances stand on
    one set of units, the finding is that of the cycle whose names sort
    first, since the solver's text gives those units once."""
    v = view(solver, runs)
    run = run_program(solver)
    added = run.determine.path \
        if run.determine is not None and run.determine.added else None
    graph = Graph(run.program, solver.engine)
    succ: dict[RelationName, dict[RelationName, None]] = {}
    solver_edges: list[_Edge] = []
    for u in graph.program.units:
        for at in graph.paths_of(u):
            head = graph.place(at, u.head.relation)
            if head is None:
                continue
            succ.setdefault(head, {})
            for atom, _negated in body_atoms(u.body or ()):
                read = graph.place(at, atom.relation)
                if read is None:
                    continue
                succ.setdefault(read, {})[head] = None
                if own(u.span) and v.program_scope(u.scope):
                    solver_edges.append(_Edge(u, at, atom, read, head))
    by_units: dict[frozenset[UnitId], tuple[tuple[str, ...], Finding]] = {}
    for comp in cyclic_components(succ, lambda n: succ[n]):
        members = frozenset(comp)
        closing = [e for e in solver_edges
                   if e.read in members and e.head in members
                   and not _permitted(solver, graph, e)]
        if not closing:
            continue
        units = sorted({e.unit.id: e.unit for e in closing}.values(),
                       key=lambda u: (u.span.first if u.span else 0,
                                      u.id.index))
        first = units[0].span
        assert first is not None
        names = tuple(sorted(_text(r, added) for r in comp))
        ids = frozenset(u.id for u in units)
        kept = by_units.get(ids)
        if kept is not None and kept[0] <= names:
            continue
        by_units[ids] = (names, lint(
            first.first, LintNamed(
                Category.RECURSION, LintSentence.RECURSION, names),
            tuple(u.id for u in units)))
    return [f for _names, f in by_units.values()]


def _text(r: RelationName, added: InstancePath | None) -> str:
    if added is not None and r.instances[:len(added)] == added:
        return RelationName(r.instances[len(added):], r.name).text
    return r.text
