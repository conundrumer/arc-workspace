"""The lint check on a lib component's defining rule, or a lib relation,
written out by hand (`comp-idiom`)."""

from dataclasses import replace

from checker.finding import (
    Code,
    Finding,
    LintCode,
    LintSentence,
)
from checker.lint.constants import EXAMPLE_SOURCES
from checker.lint.view import (
    TOP,
    View,
    bare,
    flatten,
    lint,
    literal_vars,
    view,
)
from checker.runs import Runs
from engine.program import (
    Atom,
    AtomLiteral,
    Comparison,
    ComparisonOperator,
    DefinedName,
    RelationName,
    Unit,
    Variable,
    own,
)
from engine.quotes import quotes
from solver.aggregate import Solver
from solver.category import Category
from solver.vocabulary import (
    COMPOSE,
)

IMAGE_COMPS = {"apply": "D4Map.conflict",
               COMPOSE: "OffsetInvariance.mismatch"}
"""The lib component whose defining rule reads one valued cell set at a
cell and at its image, by the lib relation that takes the cell onto the
image."""


def _other_member(solver: Solver, v: View) -> dict[str, str]:
    """Each two-member orientation type with the lib relation that states
    the other member: the first relation, in the lib's order, of two
    columns of the type whose clauses are the facts pairing each member
    with the other."""
    pairs = {t: m for t, m in solver.lib.orientation_types.items()
             if len(m) == 2}
    facts: dict[str, set[tuple[str, ...]]] = {}
    other: set[str] = set()
    for u in v.program.units:
        if u.span is None or own(u.span) or u.scope != TOP \
                or u.head.relation.instances:
            continue
        if u.body is None and all(isinstance(a, DefinedName)
                                  for a in u.head.args):
            facts.setdefault(u.head.relation.name, set()).add(
                tuple(a.name for a in u.head.args
                      if isinstance(a, DefinedName)))
        else:
            other.add(u.head.relation.name)
    out: dict[str, str] = {}
    for d in v.program.relations:
        if own(d.span) or d.scope != TOP or d.name in other \
                or len(d.columns) != 2:
            continue
        t = d.columns[0].type.text
        if t != d.columns[1].type.text or t not in pairs or t in out:
            continue
        a, b = pairs[t]
        if facts.get(d.name) == {(a, b), (b, a)}:
            out[t] = d.name
    return out


@quotes("procedure.md", "Simplify",
        "Reimplements what the lib provides.")
def check_comp_idiom(solver: Solver, runs: Runs) -> list[Finding]:
    """A lib component's defining rule, or a lib relation, written out by
    hand: one relation read twice with a `!=` between the two reads, a hint.
    Serves the purest form: the lib names the idiom."""
    v = view(solver, runs)
    members = _other_member(solver, v)
    out: list[Finding] = []
    for u in v.program_units():
        if u.body is None:
            continue
        head_vars = literal_vars(u.head)
        seen: set[tuple[int, int]] = set()
        for flat in flatten(u.body):
            neq = [x for x in flat if isinstance(x, Comparison)
                   and x.op == ComparisonOperator.NE
                   and isinstance(x.lhs, Variable)
                   and isinstance(x.rhs, Variable)]
            if not neq:
                continue
            atoms = [x.atom for x in flat
                     if isinstance(x, AtomLiteral) and not x.negated]
            local = [a for a in atoms if not v.is_lib(v.relation(u, a))]
            sets = [a for a in atoms if any(a is x for x in local)
                    or a.relation.instances
                    or a.relation.name in EXAMPLE_SOURCES]
            for i, a in enumerate(sets):
                for b in sets[i + 1:]:
                    if (id(a), id(b)) in seen:
                        continue
                    f = _comp_idiom(v, members, u, a, b, atoms, neq,
                                    head_vars)
                    if f is not None:
                        seen.add((id(a), id(b)))
                        out.append(f)
    return out


def _comp_idiom(v: View, members: dict[str, str], unit: Unit, a: Atom,
                b: Atom, atoms: list[Atom], neq: list[Comparison],
                head_vars: set[str]) -> Finding | None:
    if a.relation != b.relation or len(a.args) != len(b.args) \
            or len(a.args) < 2:
        return None
    if sum(1 for x in atoms if x.relation == a.relation) > 2:
        return None
    diff = [i for i, (x, y) in enumerate(zip(a.args, b.args))
            if bare(x) != bare(y)]

    def compared(i: int) -> Comparison | None:
        x, y = a.args[i], b.args[i]
        if not (isinstance(x, Variable) and isinstance(y, Variable)):
            return None
        return next((c for c in neq
                     if {c.lhs, c.rhs} == {x, y}), None)

    hits = [(i, c) for i in diff if (c := compared(i)) is not None]
    if len(hits) != 1:
        return None
    k, cmp = hits[0]
    x, y = a.args[k], b.args[k]
    assert isinstance(x, Variable) and isinstance(y, Variable)
    if x.name in head_vars or y.name in head_vars:
        return None
    if any(z is not a and z is not b
           and {x.name, y.name} <= literal_vars(z) for z in atoms):
        return None
    code: tuple[Code, ...] = (a, b, replace(cmp, lhs=x, rhs=y))
    if len(diff) == 1:
        cols = v.column_types(unit, a)
        if cols is None:
            return None
        rel = members.get(cols[k])
        if rel is None:
            return None
        return lint(a.line, LintCode(
            Category.COMP_IDIOM, LintSentence.COMP_IDIOM_MEMBER, code,
            (Atom(RelationName((), rel), (x, y), a.line),)))
    if len(diff) != 2:
        return None
    (p,) = [i for i in diff if i != k]
    ap, bp = a.args[p], b.args[p]
    if not (isinstance(ap, Variable) and isinstance(bp, Variable)):
        return None
    link = _image_link(ap.name, bp.name, atoms)
    if link is None:
        return None
    return lint(a.line, LintCode(
        Category.COMP_IDIOM, LintSentence.COMP_IDIOM_IMAGE, code, (),
        (link, IMAGE_COMPS[link])))


def _image_link(p: str, q: str, atoms: list[Atom]) -> str | None:
    """The lib relation carrying `p` onto `q`, `apply` for a D4 image and
    `compose` for a shift, where one stands in the body."""
    for atom in atoms:
        name = atom.relation.name
        if atom.relation.instances or name not in IMAGE_COMPS \
                or len(atom.args) != 3:
            continue
        names = [x.name if isinstance(x, Variable) else None
                 for x in atom.args]
        src = names[:2] if name == COMPOSE else names[1:2]
        if names[2] in (p, q) and ({p, q} - {names[2]}) & set(src):
            return name
    return None
