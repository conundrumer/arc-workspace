"""The rule-level lint checks on shapes that the corpus's edits rewrite
away, each mirroring an edit family observed across the solvers."""

from collections.abc import Sequence
from dataclasses import replace

from checker.finding import (
    Finding,
    LintCode,
    LintNamed,
    LintSentence,
)
from checker.lint.relations import has_wild, lib_inline
from checker.lint.view import (
    bare,
    choice_tags,
    conjunctions,
    disjunctions,
    flatten,
    lint,
    literal_terms,
    literal_vars,
    positive_atoms,
    subterms,
    term_vars,
    unit_line,
    unit_section,
    view,
)
from checker.runs import Runs
from engine.program import (
    Atom,
    AtomLiteral,
    BodyLiteral,
    Comparison,
    ComparisonOperator,
    ConstructorTerm,
    DeclId,
    DefinedName,
    NumberTerm,
    Term,
    Variable,
    Wildcard,
)
from engine.quotes import quotes
from solver.aggregate import Solver
from solver.category import Category


def _tag(name: str, fields: int) -> ConstructorTerm:
    return ConstructorTerm(name, (Wildcard(),) * fields)


def _key(lits: Sequence[BodyLiteral]) -> tuple[BodyLiteral, ...]:
    return bare(tuple(lits))


@quotes("style.md", "Disjunction",
        "Clauses that share a head and a frame belong in one clause.")
def check_choice_tag(solver: Solver, runs: Runs) -> list[Finding]:
    """Clauses identical but for a distinct nullary constructor in one head
    argument, where some relation's facts already enumerate both tags: one
    clause ranges over the tags. Serves the purest form."""
    v = view(solver, runs)
    units = v.program_units()
    facts: list[set[str]] = []
    have: dict[DeclId | str, set[str]] = {}
    for u in v.program.units:
        if u.body is not None:
            continue
        d = v.head(u)
        key: DeclId | str = d.id if d is not None else u.head.relation.name
        for a in u.head.args:
            if isinstance(a, ConstructorTerm) and not a.args:
                have.setdefault(key, set()).add(a.name)
    facts = list(have.values())
    out: list[Finding] = []
    for i, u in enumerate(units):
        if u.body is None or u.span is None:
            continue
        for o in units[:i]:
            if o.body is None or o.scope != u.scope or o.span is None \
                    or unit_section(v, o) != unit_section(v, u):
                continue
            if o.head.relation != u.head.relation \
                    or len(o.head.args) != len(u.head.args):
                continue
            if _key(o.body) != _key(u.body):
                continue
            diff = [j for j, (a, b) in enumerate(zip(u.head.args, o.head.args))
                    if bare(a) != bare(b)]
            if len(diff) != 1:
                continue
            tags = [x.head.args[diff[0]] for x in (u, o)]
            names = [t.name for t in tags
                     if isinstance(t, ConstructorTerm) and not t.args]
            if len(names) == 2 and any(set(names) <= s for s in facts):
                out.append(lint(u.span.first, LintCode(
                    Category.CHOICE_TAG, LintSentence.CHOICE_TAG,
                    (tags[1], tags[0]), ())))
                break
    return out


@quotes("style.md", "Disjunction",
        "A clause does not range over choice tags through a disjunction.")
def check_cross_choice(solver: Solver, runs: Runs) -> list[Finding]:
    """A disjunction whose branches bind different choice tags: choices stay
    separate rules. Serves the concept's form."""
    v = view(solver, runs)
    tags = choice_tags(solver, v)
    out: list[Finding] = []
    for u in v.program_units():
        for disj in disjunctions(u):
            binds = [{t.name for lit in b for top in literal_terms(lit, True)
                      for t in subterms(top)
                      if isinstance(t, ConstructorTerm)} & set(tags)
                     for b in disj.branches]
            named = [b for b in binds if b]
            if len(named) >= 2 and any(b != named[0] for b in named):
                found = sorted(set().union(*named))
                out.append(lint(disj.line, LintCode(
                    Category.CROSS_CHOICE, LintSentence.CROSS_CHOICE,
                    tuple(_tag(t, tags[t]) for t in found), ())))
    return out


@quotes("procedure.md", "Simplify",
        "Express what the code claims with less code.")
@quotes("procedure.md", "Simplify",
        "Has repetition where a principled form exists.")
def check_subsumed_atom(solver: Solver, runs: Runs) -> list[Finding]:
    """`R(X, _)` beside `R(X, Y)` in one body, or one atom twice: the
    wildcard atom adds nothing. Serves the purest form."""
    v = view(solver, runs)
    out: list[Finding] = []
    for u in v.program_units():
        for body in conjunctions(u):
            atoms = [x.atom for x in body
                     if isinstance(x, AtomLiteral) and not x.negated]
            for i, a in enumerate(atoms):
                for j, b in enumerate(atoms):
                    if i == j or a.relation != b.relation \
                            or len(a.args) != len(b.args):
                        continue
                    pairs = list(zip(a.args, b.args))
                    if all(bare(x) == bare(y) for x, y in pairs):
                        if i < j:
                            out.append(lint(b.line, LintCode(
                                Category.SUBSUMED_ATOM,
                                LintSentence.ATOM_TWICE, (b,), ())))
                    elif all(isinstance(x, Wildcard)
                             or bare(x) == bare(y)
                             for x, y in pairs):
                        out.append(lint(a.line, LintCode(
                            Category.SUBSUMED_ATOM,
                            LintSentence.ATOM_ADDS_NOTHING, (a, b), ())))
    return out


def _holds(flat: list[BodyLiteral], atom: Atom) -> bool:
    return any(isinstance(x, AtomLiteral) and x.atom is atom for x in flat)


def _other_side(cmp: Comparison, name: str) -> Term | None:
    if isinstance(cmp.lhs, Variable) and cmp.lhs.name == name:
        return cmp.rhs
    if isinstance(cmp.rhs, Variable) and cmp.rhs.name == name:
        return cmp.lhs
    return None


@quotes("style.md", "Idioms",
        "**Complement tests.** The test negates the relation of the values it "
        "excludes: `!params.bg(Col)` for non-bg.")
def check_named_complement(solver: Solver, runs: Runs) -> list[Finding]:
    """`R(V), X != V` against a relation of one fact: `!R(X)` says it
    directly. Serves the purest form."""
    v = view(solver, runs)
    out: list[Finding] = []
    for u in v.program_units():
        if u.body is None:
            continue
        flats = list(flatten(u.body))
        for atom in positive_atoms(flats):
            if len(atom.args) != 1 or not isinstance(atom.args[0], Variable):
                continue
            d = v.relation(u, atom)
            if d is None or v.is_lib(d):
                continue
            defs = v.defs(d)
            if len(defs) != 1 or defs[0].body is not None:
                continue
            name = atom.args[0].name
            if name in literal_vars(u.head):
                continue
            found: tuple[Comparison, Term] | None = None
            ok = True
            for flat in flats:
                if not _holds(flat, atom):
                    continue
                others = [x for x in flat
                          if not (isinstance(x, AtomLiteral) and x.atom is atom)
                          and name in literal_vars(x)]
                if len(others) != 1 or not isinstance(others[0], Comparison) \
                        or others[0].op != ComparisonOperator.NE:
                    ok = False
                    break
                cmp = others[0]
                other = _other_side(cmp, name)
                if other is None:
                    ok = False
                    break
                bound = {n for x in flat
                         if isinstance(x, AtomLiteral) and not x.negated
                         and x.atom is not atom for n in literal_vars(x)}
                if term_vars(other) - bound:
                    ok = False
                    break
                if found is None:
                    found = (cmp, other)
                elif found[0] is not cmp:
                    ok = False
                    break
            if not ok or found is None:
                continue
            cmp, other = found
            out.append(lint(atom.line, LintCode(
                Category.NAMED_COMPLEMENT, LintSentence.NAMED_COMPLEMENT,
                (atom, cmp),
                (AtomLiteral(replace(atom, args=(other,)), True),))))
    return out


@quotes("style.md", "Idioms",
        "**Complement tests.** The test negates the relation of the values it "
        "excludes: `!params.bg(Col)` for non-bg.")
def check_negated_value(solver: Solver, runs: Runs) -> list[Finding]:
    """`prim(..., K), K != c`, with `K` read nowhere else, at a lib inline
    relation Souffle negates: `!prim(..., c)` says it directly. Serves the
    purest form."""
    v = view(solver, runs)
    _inline, negatable = v.held(lib_inline)
    out: list[Finding] = []
    for u in v.program_units():
        if u.body is None:
            continue
        head_vars = literal_vars(u.head)
        flats = list(flatten(u.body))
        for atom in positive_atoms(flats):
            if atom.relation.instances \
                    or atom.relation.name not in negatable \
                    or not v.is_lib(v.relation(u, atom)) \
                    or any(has_wild(a) for a in atom.args):
                continue
            for i, arg in enumerate(atom.args):
                if not isinstance(arg, Variable) or arg.name in head_vars:
                    continue
                name = arg.name
                if sum(1 for a in atom.args if name in term_vars(a)) != 1:
                    continue
                const = _sole_complement(atom, name, flats)
                if const is None:
                    continue
                rest = [a for j, a in enumerate(atom.args) if j != i]
                if not all(_bound_elsewhere(atom, w, flats)
                           for a in rest for w in term_vars(a)):
                    continue
                cmp = next(x for f in flats if _holds(f, atom) for x in f
                           if isinstance(x, Comparison)
                           and name in literal_vars(x))
                new = replace(atom, args=tuple(
                    const if j == i else a for j, a in enumerate(atom.args)))
                out.append(lint(atom.line, LintCode(
                    Category.NEGATED_VALUE, LintSentence.NEGATED_VALUE,
                    (atom, cmp), (AtomLiteral(new, True),))))
                break
    return out


def _sole_complement(atom: Atom, name: str, flats: list[list[BodyLiteral]]
                     ) -> Term | None:
    const: Term | None = None
    for flat in flats:
        if not _holds(flat, atom):
            continue
        others = [x for x in flat
                  if not (isinstance(x, AtomLiteral) and x.atom is atom)
                  and name in literal_vars(x)]
        if len(others) != 1 or not isinstance(others[0], Comparison) \
                or others[0].op != ComparisonOperator.NE:
            return None
        t = _other_side(others[0], name)
        if not isinstance(t, NumberTerm | DefinedName) \
                or (const is not None and const != t):
            return None
        const = t
    return const


def _bound_elsewhere(atom: Atom, name: str, flats: list[list[BodyLiteral]]
                     ) -> bool:
    return all(any(isinstance(x, AtomLiteral) and not x.negated
                   and x.atom is not atom and name in literal_vars(x)
                   for x in flat)
               for flat in flats if _holds(flat, atom))


@quotes("style.md", "Bans",
        "Arithmetic, raw aggregates, and `range` are banned.")
def check_argmax(solver: Solver, runs: Runs) -> list[Finding]:
    """`beaten(X) :- score(X, N), score(_, N2), N2 > N`, read only under
    negation, a hint: an aggregate in disguise; read it through a lib
    component. Serves the purest form."""
    v = view(solver, runs)
    out: list[Finding] = []
    for u in v.program_units():
        if u.body is None:
            continue
        shaped = True
        for body in flatten(u.body):
            atoms = [x.atom for x in body
                     if isinstance(x, AtomLiteral) and not x.negated]
            cmps = [x for x in body if isinstance(x, Comparison)]
            if len(body) != 3 or len(atoms) != 2 or len(cmps) != 1 \
                    or cmps[0].op not in (ComparisonOperator.LT,
                                          ComparisonOperator.GT) \
                    or atoms[0].relation != atoms[1].relation:
                shaped = False
                break
            cvars = literal_vars(cmps[0])
            v0, v1 = literal_vars(atoms[0]), literal_vars(atoms[1])
            if not (cvars & v0) or not (cvars & v1):
                shaped = False
                break
            head = literal_vars(u.head)
            if (v0 - v1) & head and (v1 - v0) & head:
                shaped = False
                break
        if not shaped:
            continue
        d = v.head(u)
        if d is None:
            continue
        uses = v.uses(d)
        if uses and all(n for _u, _a, n in uses):
            out.append(lint(unit_line(u),
                            LintNamed(Category.ARGMAX, LintSentence.ARGMAX,
                                      (u.head.relation.name,))))
    return out
