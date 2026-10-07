"""The lint checks on the types a solver declares and reads: a type a
solver may not declare, and a field of the case type that no unit
reads; with the literals of a unit and the solver's top-level
`DemonstratedChoice`, which other checks of the form read."""

from collections.abc import Mapping

from checker.finding import (
    Finding,
    LintNamed,
    LintSentence,
)
from checker.lint.view import (
    TOP,
    from_lib,
    lint,
    literal_terms,
    subterms,
    view,
)
from checker.runs import Runs
from engine.program import (
    AdtType,
    AtomLiteral,
    BodyLiteral,
    ConstructorTerm,
    DeclId,
    Disjunction,
    RecordTerm,
    RecordType,
    Scope,
    Term,
    TypeDecl,
    Unit,
    Variable,
    TypeName,
    Wildcard,
    type_refs,
)
from engine.quotes import quotes
from solver.category import Category
from solver.aggregate import (
    Solver,
)
from solver.vocabulary import (
    CHOICE,
    DEMONSTRATED,
    DEMONSTRATED_CHOICE,
    DEMONSTRATION_CONSISTENCY,
    DETERMINE,
    PARSE,
    TIEBREAK_RESOLUTION,
)
from checker.lint.form.case_type import choice_adts


@quotes("style.md", "Types",
        "lists the types a solver may define, and any other type is banned.")
@quotes("solver-file.md", "Types",
        "a record used as a type argument of a generic comp")
@quotes("solver-file.md", "Types",
        "`DemonstratedChoice`, per [Demonstrated choice]")
@quotes("solver-file.md", "Demonstrated choice",
        "`DemonstratedChoice` is the `Demonstrated` type argument of a "
        "`DemonstrationConsistency` instance.")
def check_banned_type(solver: Solver, runs: Runs) -> list[Finding]:
    """A type the solver declares that is none of the types a solver may
    define: the types `Choice` and `TiebreakResolution` reach, the types
    `DemonstratedChoice` reaches where an instance of the lib's
    `DemonstrationConsistency` takes it as its `Demonstrated` type
    argument, and the records an instance takes as a type argument with
    the records their fields reach. Only the types at the top level and
    in `Determine` and `Parse` are flagged. Serves the purest form."""
    v = view(solver, runs)
    scoped = [(t, t.scope == TOP or t.scope.components[:1] in
               ((DETERMINE,), (PARSE,))) for t in v.own_types]

    def resolved(name: TypeName, scope: Scope) -> TypeDecl | None:
        return _type_among(runs, name, scope, v.own_types_by_id)

    def refs(t: TypeDecl) -> list[TypeDecl]:
        return [d for r in type_refs(t)
                if (d := resolved(r, t.scope)) is not None and d.id != t.id]

    def sanction(stack: list[TypeDecl], admits: type) -> None:
        while stack:
            t = stack.pop()
            if t.id in sanctioned:
                continue
            sanctioned.add(t.id)
            stack.extend(r for r in refs(t)
                         if isinstance(r, admits) and r.id not in sanctioned)

    sanctioned: set[DeclId] = set()
    sanction([d for n in (CHOICE, TIEBREAK_RESOLUTION)
              if (d := resolved(TypeName((), n), TOP)) is not None], object)
    demonstrated = demonstrated_choice(solver, runs)
    if demonstrated is not None and demonstrated.id in {
            d.id for i in v.own_instances
            if (of := v.index.component(i.component, i.scope)) is not None
            and of.name == DEMONSTRATION_CONSISTENCY and from_lib(of.span)
            for p, a in zip(of.type_params, i.type_args) if p == DEMONSTRATED
            if (d := resolved(a, i.scope)) is not None}:
        sanction([demonstrated], object)
    sanction([d for i in v.own_instances for a in i.type_args
              if isinstance(d := resolved(a, i.scope), RecordType)],
             RecordType)
    return [lint(t.span.first, LintNamed(
                Category.BANNED_TYPE, LintSentence.BANNED_TYPE, (t.name,)))
            for t, linted in scoped if linted and t.id not in sanctioned]


def demonstrated_choice(solver: Solver, runs: Runs) -> TypeDecl | None:
    """The `DemonstratedChoice` the solver declares at the top level; None
    where it declares none there."""
    return _type_among(runs, TypeName((), DEMONSTRATED_CHOICE), TOP,
                       view(solver, runs).own_types_by_id)


def _type_among[T](runs: Runs, name: TypeName, scope: Scope,
                   among: Mapping[DeclId, T]) -> T | None:
    """The declaration among `among` that the type `name` denotes in
    `scope` (`engine.Index.type_decl`); None where it denotes a
    primitive type, a type parameter or a declaration not among them."""
    d = runs.index.type_decl(name, scope)
    return None if d is None else among.get(d.id)


# Unread fields


def all_literals(unit: Unit) -> list[BodyLiteral | None]:
    """The head (as None) and every body literal, disjunction branches
    included."""
    out: list[BodyLiteral | None] = [None]
    stack = list(unit.body or ())
    while stack:
        lit = stack.pop(0)
        out.append(lit)
        if isinstance(lit, Disjunction):
            for b in lit.branches:
                stack.extend(b)
    return out


def _terms_of(unit: Unit, lit: BodyLiteral | None) -> tuple[Term, ...]:
    return unit.head.args if lit is None else literal_terms(lit)


def _var_uses(unit: Unit, enums: set[str]) -> dict[str, int]:
    """How often each variable stands in a clause; a variable that is the
    one argument of an enumerator atom does not count there."""
    uses: dict[str, int] = {}
    for lit in all_literals(unit):
        if isinstance(lit, AtomLiteral) and len(lit.atom.args) == 1 \
                and lit.atom.relation.name in enums \
                and not lit.atom.relation.instances:
            continue
        for t in _terms_of(unit, lit):
            for s in subterms(t):
                if isinstance(s, Variable):
                    uses[s.name] = uses.get(s.name, 0) + 1
    return uses


def _reads(term: Term, uses: dict[str, int]) -> bool:
    """A field written as `term` is read: it is no `_`, and no variable
    the clause uses nowhere else."""
    if isinstance(term, Wildcard):
        return False
    return not (isinstance(term, Variable) and uses.get(term.name, 0) <= 1)


@quotes("procedure.md", "Witness",
        "A case never reads a `Choice` field: the choice point that field "
        "encodes stands under the other branches")
@quotes("principles.md", "Choice points and open parameters",
        "A choice point stands at the concept, or under a branch when its "
        "property exists only with that branch.")
@quotes("style.md", "Cases",
        "**Concept branch.** The concept branch is declared first in "
        "`Choice`, and in each field's type of a record-typed `Choice`.")
def check_unread_field(solver: Solver, runs: Runs) -> list[Finding]:
    """A case, a constructor at its parent, whose clauses never read a field
    that encodes a choice point, a hint. A clause reads a field where it
    writes the constructor and puts at the field anything but `_` or a
    variable it uses nowhere else.
    Serves the concept's form."""
    choice = solver.choice
    if choice is None:
        return []
    v = view(solver, runs)
    adts = {td.id: td for _, _p, td in choice_adts(solver, v)}

    def adt_of(name: TypeName, scope: Scope) -> AdtType | None:
        return _type_among(runs, name, scope, adts)

    points: dict[str, list[tuple[int, str]]] = {}
    owner: dict[str, AdtType] = {}
    for td in adts.values():
        for c in td.constructors:
            owner[c.name] = td
            chosen = [(j, f.name) for j, f in enumerate(c.fields)
                      if adt_of(f.type, td.scope) is not None]
            if chosen:
                points[c.name] = chosen
    choice_decl = solver.program.declared(choice.declaration)
    if not isinstance(choice_decl, AdtType | RecordType):
        raise ValueError("`Choice` names no type declaration")
    roots: list[tuple[str, AdtType | None]] = [
        (f.name, adt_of(f.type, choice_decl.scope))
        for f in choice.record or ()]
    if not points and len(roots) < 2:
        return []
    enums = v.enumerators
    written: set[tuple[str, int]] = set()
    read: set[tuple[str, int]] = set()
    rec_written: set[tuple[str, int]] = set()
    rec_read: set[tuple[str, int, int]] = set()
    open_read: set[tuple[int, int]] = set()

    def root_ctor(t: Term, i: int) -> str | None:
        td = roots[i][1]
        if isinstance(t, ConstructorTerm) and td is not None \
                and t.name in {c.name for c in td.constructors}:
            return t.name
        return None

    def choice_record(t: RecordTerm) -> bool:
        return len(t.args) == len(roots) and all(
            isinstance(a, Variable | Wildcard) or root_ctor(a, i) is not None
            for i, a in enumerate(t.args))

    for u in v.own_units:
        if u.scope == TOP and not u.head.relation.instances \
                and u.head.relation.name in enums:
            continue
        uses = _var_uses(u, enums)
        for lit in all_literals(u):
            for top in _terms_of(u, lit):
                for t in subterms(top):
                    if isinstance(t, ConstructorTerm) and t.name in points:
                        for j, _name in points[t.name]:
                            if j >= len(t.args):
                                continue
                            written.add((t.name, j))
                            if _reads(t.args[j], uses):
                                read.add((t.name, j))
                    elif isinstance(t, RecordTerm) and len(roots) > 1 \
                            and choice_record(t):
                        for i, a in enumerate(t.args):
                            ctor = root_ctor(a, i)
                            if ctor is not None:
                                rec_written.add((ctor, i))
                            for j, b in enumerate(t.args):
                                if j == i or not _reads(b, uses):
                                    continue
                                if ctor is None:
                                    open_read.add((i, j))
                                else:
                                    rec_read.add((ctor, i, j))
    out: list[Finding] = []

    def hint(ctor: str, field: str) -> None:
        td = owner[ctor]
        c = next(c for c in td.constructors if c.name == ctor)
        at = c.span.first if c.own_line else td.span.first
        out.append(lint(at, LintNamed(Category.UNREAD_FIELD,
                                      LintSentence.UNREAD_FIELD,
                                      (ctor, field))))

    for ctor, chosen in points.items():
        for j, name in chosen:
            if (ctor, j) in written and (ctor, j) not in read:
                hint(ctor, name)
    for ctor, i in sorted(rec_written, key=lambda k: (k[1], k[0])):
        for j, (name, _td) in enumerate(roots):
            if j != i and (ctor, i, j) not in rec_read \
                    and (i, j) not in open_read:
                hint(ctor, name)
    return out
