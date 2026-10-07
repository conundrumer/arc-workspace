"""The lint checks on what program style bans in the program's clauses:
literals, lib constant macros, arithmetic, `range`, `ord`, raw aggregates,
and an order taken over a type that has none."""

from collections.abc import Iterator

from checker.finding import (
    Finding,
    LintCounted,
    LintFragment,
    LintNamed,
    LintSentence,
)
from checker.lint.idioms import Columns
from checker.lint.view import (
    TOP,
    View,
    aggregates,
    atoms_read,
    conjunctions,
    lint,
    placed,
    subterms,
    term_vars,
    view,
)
from checker.runs import Runs
from engine import Resolved
from engine.program import (
    Aggregate,
    AggregateOperator,
    Atom,
    BinaryTerm,
    BodyLiteral,
    Comparison,
    ComparisonOperator,
    DefinedName,
    GridCall,
    Instance,
    Intrinsic,
    IntrinsicCall,
    NumberTerm,
    SubtypeType,
    Term,
    UnaryTerm,
    UnionType,
    Unit,
    UnitId,
    own,
)
from engine.text import text as code_text
from engine.quotes import quotes
from solver.annotations import TrailingWord
from solver.category import Category
from solver.aggregate import Solver
from solver.vocabulary import (
    COLOR,
    IDENT,
    PARAMS,
)

ZERO_MACROS = frozenset({"ZERO"})
"""The zero box: a box, not an orientation."""


def _clauses(units: list[Unit]) -> list[tuple[list[Unit], tuple[BodyLiteral, ...]]]:
    """The clauses of `units`, each as its units, one per head, and its
    body: the units of a clause with several heads share one span and one
    body."""
    out: list[tuple[list[Unit], tuple[BodyLiteral, ...]]] = []
    for u in units:
        if out and u.body is not None and u.span is not None \
                and out[-1][0][-1].span == u.span and out[-1][1] == u.body:
            out[-1][0].append(u)
        else:
            out.append(([u], u.body or ()))
    return out


def linted_nodes(v: View) -> Iterator[tuple[int, BodyLiteral | Atom | Term,
                                             tuple[UnitId, ...]]]:
    """Each literal and term of the clauses program style applies to, with
    its line and the units it stands in, in source order; a clause with
    several heads gives its body once, and the cells of a `GRID` call
    stand on the call's first line."""
    for heads, body in _clauses(v.style_units()):
        units = tuple(u.id for u in heads)
        for u in heads:
            yield from ((ln, n, (u.id,)) for ln, n in placed(u.head,
                                                             u.head.line))
        for lit in body:
            yield from ((ln, n, units)
                        for ln, n in placed(lit, heads[0].head.line))
    for m in v.program.macros:
        if not isinstance(m, GridCall) or m.span is None \
                or not own(m.span) or m.scope != TOP:
            continue
        for row in m.cells:
            for cell in row:
                for t in subterms(cell.term):
                    yield m.span.first, t, (m.id,)


def _bans(solver: Solver, runs: Runs, category: Category) -> list[Finding]:
    """The findings of one ban over the clauses program style applies to
    (style.md, under "Bans"); the message is the fragment that fires."""
    v = view(solver, runs)
    macros = frozenset(solver.lib.constants) - ZERO_MACROS
    out: list[Finding] = []
    for line, node, units in linted_nodes(v):
        hit: tuple[Category, str] | None = None
        match node:
            case NumberTerm(value=value) if value != 0:
                hit = (Category.NONZERO_LITERAL, code_text(node))
            case DefinedName(name=name) if name in macros:
                hit = (Category.ORIENTATION_LITERAL, name)
            case BinaryTerm(op=op) | UnaryTerm(op=op):
                hit = (Category.ARITHMETIC, op.value)
            case IntrinsicCall(functor=Intrinsic.RANGE):
                hit = (Category.RANGE, Intrinsic.RANGE.value)
            case IntrinsicCall(functor=Intrinsic.ORD):
                hit = (Category.ORD, Intrinsic.ORD.value)
            case _:
                pass
        if hit is not None and hit[0] == category:
            out.append(lint(line, LintFragment(category, hit[1]), units))
    return out


@quotes("style.md", "Bans",
        "**Literals.** Literals are banned.")
@quotes("style.md", "Bans",
        "It reads every other lib constant macro, all colors, and non-zero "
        "task-shape lengths, offsets, and gaps from Params.")
@quotes("principles.md", "Orientation",
        "When a task does not distinguish an orientation, neither does the "
        "program.")
def check_orientation_literal(solver: Solver, runs: Runs) -> list[Finding]:
    """A lib constant macro other than `ZERO` in a clause program style
    applies to. Serves the purest form."""
    return _bans(solver, runs, Category.ORIENTATION_LITERAL)


@quotes("style.md", "Bans",
        "**Literals.** Literals are banned.")
@quotes("style.md", "Bans",
        "The program may read `0` and `ZERO` directly.")
@quotes("principles.md", "The generator",
        "The program fixes no task data.")
def check_nonzero_literal(solver: Solver, runs: Runs) -> list[Finding]:
    """A number other than `0` in a clause program style applies to. Serves
    the purest form."""
    return _bans(solver, runs, Category.NONZERO_LITERAL)


@quotes("style.md", "Bans",
        "Arithmetic, raw aggregates, and `range` are banned.")
def check_arithmetic(solver: Solver, runs: Runs) -> list[Finding]:
    """An arithmetic operator in a clause program style applies to. Serves
    the purest form."""
    return _bans(solver, runs, Category.ARITHMETIC)


@quotes("style.md", "Bans",
        "Arithmetic, raw aggregates, and `range` are banned.")
def check_range(solver: Solver, runs: Runs) -> list[Finding]:
    """A `range` call in a clause program style applies to. Serves the
    purest form, as `check_arithmetic` does."""
    return _bans(solver, runs, Category.RANGE)


@quotes("style.md", "Bans",
        "**`ord`.** `ord` is banned.")
@quotes("style.md", "Bans",
        "The lib comp `IdentOf` gives a value its `Ident`.")
def check_ord(solver: Solver, runs: Runs) -> list[Finding]:
    """An `ord` call in a clause program style applies to. Serves the
    purest form, as `check_arithmetic` does."""
    return _bans(solver, runs, Category.ORD)


@quotes("style.md", "Bans",
        "Arithmetic, raw aggregates, and `range` are banned.")
def check_raw_aggregate(solver: Solver, runs: Runs) -> list[Finding]:
    """An aggregate in a clause of a program scope: read it through a lib
    component. Serves the purest form, as `check_arithmetic` does."""
    v = view(solver, runs)
    out: list[Finding] = []
    for u in v.program_units():
        for body in conjunctions(u):
            for lit in body:
                if not isinstance(lit, Comparison):
                    continue
                for side in (lit.lhs, lit.rhs):
                    if isinstance(side, Aggregate):
                        out.append(lint(lit.line, LintNamed(
                            Category.RAW_AGGREGATE,
                            LintSentence.RAW_AGGREGATE, (side.op.value,)),
                            (u.id,)))
    return out


def _singleton_axis(solver: Solver, unit: Unit) -> bool:
    """The clause ends with `// @singleton-axis: …` (solver-file.md, under
    "Params")."""
    return any(t.word == TrailingWord.SINGLETON_AXIS
               and (t.unit == unit.id
                    or (unit.span is not None and t.line == unit.span.last))
               for t in solver.annotations.trailing)


@quotes("style.md", "Params",
        "**Derived data.** A clause inside Params writes no value as a "
        "literal.")
@quotes("solver-file.md", "Params",
        "**`@singleton-axis` literal.** A structure that extends along one "
        "axis is written in a two-axis type, and the other axis takes a "
        "literal `1`.")
def check_params_data(solver: Solver, runs: Runs) -> list[Finding]:
    """A literal in a rule of `Params` other than `0`, and other than `1` in
    a clause marked `@singleton-axis`. Serves the purest form."""
    v = view(solver, runs)
    out: list[Finding] = []
    for u in v.own_units:
        if v.comp_of(u.scope) != PARAMS or len(u.scope.components) != 1 \
                or u.body is None:
            continue
        axis = _singleton_axis(solver, u)
        for lit in (u.head, *u.body):
            for line, node in placed(lit, u.head.line):
                if isinstance(node, NumberTerm) and node.value != 0 \
                        and not (axis and node.value == 1):
                    out.append(lint(line, LintFragment(
                        Category.PARAMS_DATA, code_text(node)),
                        (u.id,)))
    return out


ORDER_OPS = frozenset({ComparisonOperator.LT, ComparisonOperator.LE,
                       ComparisonOperator.GT, ComparisonOperator.GE})
ORDER_AGGREGATES = frozenset({AggregateOperator.MIN, AggregateOperator.MAX})
ORDINAL = "Ordinal"
ORDINAL_SET = "idx_set"
"""The lib component that ranks a numeric set, and the relation it
ranks."""


def _unordered_types(solver: Solver, v: View) -> frozenset[str]:
    """The types an order may not read: `Color`, `Ident`, the lib's
    orientation types, the subtypes they reach, and the unions whose every
    member is one (principles.md, under "Color"; history 1139)."""
    out = {COLOR, IDENT} | set(solver.lib.orientation_types)
    changed = True
    while changed:
        changed = False
        for t in v.program.types:
            if t.name in out:
                continue
            if isinstance(t, SubtypeType) and t.base.text in out \
                    or isinstance(t, UnionType) and all(
                        m.text in out for m in t.members):
                out.add(t.name)
                changed = True
    return frozenset(out)


@quotes("principles.md", "Color",
        "Colors have identity and no other properties.")
def check_typed_order(solver: Solver, runs: Runs) -> list[Finding]:
    """An order read off a type that has none: a comparison `<`, `<=`, `>`,
    `>=`, or a `min` or `max`, over a variable a column of such a type
    binds, or such a variable fed to `Ordinal`, on every type with identity
    and no order."""
    v = view(solver, runs)
    unordered = _unordered_types(solver, v)
    cols = Columns(v)
    out: list[Finding] = []
    for u in v.program_units():
        types: dict[str, set[str]] = {}
        for a in (u.head, *atoms_read(u)):
            for name, ts in cols.var_types(u, a).items():
                types.setdefault(name, set()).update(ts)
        seen: set[tuple[int, str]] = set()

        def flag(line: int, term: Term, sentence: LintSentence, how: str
                 ) -> None:
            for var in sorted(term_vars(term)):
                for t in sorted(types.get(var, ())):
                    if t not in unordered or (line, var) in seen:
                        continue
                    seen.add((line, var))
                    out.append(lint(line, LintNamed(
                        Category.TYPED_ORDER, sentence, (how, var, t))))

        for body in conjunctions(u):
            for lit in body:
                if not isinstance(lit, Comparison):
                    continue
                if lit.op in ORDER_OPS:
                    flag(lit.line, lit.lhs, LintSentence.TYPED_ORDER_COMPARES,
                         lit.op.value)
                    flag(lit.line, lit.rhs, LintSentence.TYPED_ORDER_COMPARES,
                         lit.op.value)
                for agg in aggregates(lit):
                    if agg.op in ORDER_AGGREGATES and agg.expr is not None:
                        flag(lit.line, agg.expr,
                             LintSentence.TYPED_ORDER_ORDERS, agg.op.value)
        for a in (u.head, *atoms_read(u)):
            if a.relation.name != ORDINAL_SET or len(a.args) != 2 \
                    or not _in_ordinal(v, u, a):
                continue
            flag(a.line, a.args[1], LintSentence.TYPED_ORDER_RANKS, ORDINAL)
    return out


def _in_ordinal(v: View, unit: Unit, atom: Atom) -> bool:
    """The atom reads its relation through an instance of `Ordinal`."""
    r = v.index.resolve(atom.relation, unit.scope)
    if not isinstance(r, Resolved):
        return False
    return any(isinstance(i := v.decls.get(d), Instance)
               and i.component == ORDINAL for d in r.through)


LINE_LIMIT = 100
"""The widest line a one-line clause takes."""


@quotes("style.md", "Layout",
        "**Single-line form.** The single-line form is fine for short clauses "
        "(≤ ~80 chars).")
def check_long_clause(solver: Solver, runs: Runs) -> list[Finding]:
    """A clause whose whole body stands on one line wider than the limit:
    the style's single-line form is for short clauses. A clause with several
    heads is one finding. Serves readability."""
    v = view(solver, runs)
    out: list[Finding] = []
    seen: set[int] = set()
    for u in v.program_units():
        span = u.span
        if u.body is None or span is None or span.width is None \
                or span.first != span.last or span.first in seen:
            continue
        seen.add(span.first)
        if span.width > LINE_LIMIT:
            out.append(lint(span.first, LintCounted(
                Category.LONG_CLAUSE, LintSentence.LONG_CLAUSE, (),
                span.width, LINE_LIMIT)))
    return out
