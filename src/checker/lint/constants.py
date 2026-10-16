"""The lint check on a join that derives a task constant
(`check_const_join`), and where an atom's value comes from (`Target`), the
reading it rests on."""

from dataclasses import dataclass

from checker.finding import Finding, LintNamed, LintSentence
from checker.lint.view import View, atoms_read, flatten, lint, literal_vars, view
from checker.runs import Runs
from engine import Resolved
from engine.program import Atom, AtomLiteral, DeclId, Instance, RelationDecl, Unit
from engine.quotes import quotes
from solver.aggregate import Solver
from solver.category import Category
from solver.vocabulary import EX_IN, EX_OUT, INPUT, PARAMS

EXAMPLE_SOURCES = frozenset({INPUT.name, EX_IN.name, EX_OUT.name})
"""The relations the runner fills per example."""


@dataclass(frozen=True)
class Const:
    """Params data, or a lib relation that reads no grid."""


@dataclass(frozen=True)
class Example:
    """The runner's per-example fills."""


@dataclass(frozen=True)
class RelNode:
    """A relation the program declares."""

    decl: DeclId


@dataclass(frozen=True)
class InstanceNode:
    """An instance of a lib component, read as opaque."""

    decl: DeclId


type Target = Const | Example | RelNode | InstanceNode
"""Where an atom's value comes from."""

CONST = Const()
EXAMPLE = Example()


def _target(v: View, unit: Unit, atom: Atom) -> Target:
    """Where an atom's value comes from: `CONST` for Params data and lib
    relations that read no grid, `EXAMPLE` for the runner's per-example
    fills, else the relation or instance the taint runs through."""
    r = v.index.resolve(atom.relation, unit.scope)
    if atom.relation.instances:
        if not isinstance(r, Resolved) or not r.through:
            return EXAMPLE
        inst = v.decls.get(r.through[0])
        if isinstance(inst, Instance) and inst.component == PARAMS:
            return CONST
        return InstanceNode(r.through[0])
    if not isinstance(r, Resolved):
        return EXAMPLE if atom.relation.name in EXAMPLE_SOURCES else CONST
    d = v.decls.get(r.declaration)
    if not isinstance(d, RelationDecl) or v.is_lib(d):
        return EXAMPLE if atom.relation.name in EXAMPLE_SOURCES else CONST
    if v.comp_of(d.scope) == PARAMS:
        return CONST
    return RelNode(d.id)


def _const_targets(v: View) -> set[Target]:
    """The relations and instances whose derivations reach no per-example
    source: named task constants."""
    heads: dict[Target, list[Unit]] = {}
    for u in v.program.units:
        t = _target(v, u, u.head)
        if isinstance(t, RelNode | InstanceNode):
            heads.setdefault(t, []).append(u)
    tainted: set[Target] = set()
    changed = True
    while changed:
        changed = False
        for t, units in heads.items():
            if t in tainted:
                continue
            if any((b := _target(v, u, a)) == EXAMPLE
                   or b in tainted
                   for u in units for a in atoms_read(u)):
                tainted.add(t)
                changed = True
    return set(heads) - tainted


@quotes("solver-file.md", "Params",
        "Params contains the parameterization and what derives from it.")
@quotes("principles.md", "Stored or derived",
        "A value that follows from another parameter in every variant task "
        "is derived data rather than a second parameter.")
def check_const_join(solver: Solver, runs: Runs) -> list[Finding]:
    """A variable internal to a clause's Params reads, a hint: the join
    derives a task constant, which the corpus names in its own relation;
    reads that share no variable form a product one stored relation
    replaces. Quiet inside Params and under a head that is itself a task
    constant. Serves the purest form."""
    v = view(solver, runs)
    consts = _const_targets(v)
    out: list[Finding] = []
    for u in v.program_units():
        if u.body is None or v.comp_of(u.scope) == PARAMS:
            continue
        if _target(v, u, u.head) in consts:
            continue
        seen: set[tuple[LintSentence, tuple[str, ...], tuple[str, ...]]] = set()
        for body in flatten(u.body):
            creads = [x for x in body if isinstance(x, AtomLiteral)
                      and x.atom.relation.instances
                      and _target(v, u, x.atom) == CONST]
            if len(creads) < 2:
                continue
            cvars = set().union(*(literal_vars(x) for x in creads))
            others = literal_vars(u.head)
            for x in body:
                if not any(x is c for c in creads):
                    others |= literal_vars(x)
            internal = cvars - others
            if not internal:
                continue
            rels: list[str] = []
            for x in creads:
                s = x.atom.relation.text
                if s not in rels:
                    rels.append(s)
            sets = [literal_vars(x) for x in creads]
            disjoint = all(not (a & b) for i, a in enumerate(sets)
                           for b in sets[i + 1:])
            if len(rels) > 1 and disjoint:
                key = (LintSentence.CONST_PRODUCT, tuple(rels), ())
            else:
                key = (LintSentence.CONST_JOIN, tuple(rels),
                       tuple(sorted(internal)))
            if key in seen:
                continue
            seen.add(key)
            out.append(lint(creads[0].atom.line, LintNamed(
                Category.CONST_JOIN, key[0], key[1], key[2])))
    return out
