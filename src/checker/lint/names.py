"""The lint checks on the names a solver declares and reads: the
collisions Souffle reports with a message that misleads, the lib's
private names, and the charts only a `RIGID` expansion writes."""

from checker.finding import Finding, LintFragment, LintNamed, LintSentence
from checker.lint.view import (
    TOP,
    View,
    atoms_read,
    from_lib,
    lint,
    spanned,
    view,
)
from checker.runs import Runs
from engine import Resolved
from engine.program import (
    AdtType,
    Component,
    FunctorDecl,
    Instance,
    RecordType,
    RelationDecl,
    TypeDecl,
)
from solver.category import Category
from solver.model import Solver

RESERVED_WORDS = frozenset({
    "count", "sum", "min", "max", "mean",
    "cat", "ord", "range", "strlen", "substr", "match", "contains", "autoinc",
    "to_float", "to_number", "to_string", "to_unsigned",
    "band", "bor", "bxor", "bnot", "bshl", "bshr", "bshru",
    "land", "lor", "lxor", "lnot",
    "inline", "no_inline", "magic", "no_magic", "overridable",
    "input", "output", "printsize", "eqrel", "brie", "btree", "btree_delete",
    "as", "nil", "true", "false", "stateful", "debug_delta",
    "recursive_iteration_cnt", "__FILE__", "__LINE__", "__INCL__",
})
"""The bare words the Souffle 2.5 scanner reserves in every name
position."""

"""The prefix of the names only a `RIGID` block's expansion writes."""


def _declared_names(d: RelationDecl | TypeDecl | Component | Instance
                    | FunctorDecl) -> list[str]:
    match d:
        case RelationDecl(name=name, columns=cols):
            return [name, *(c.name for c in cols)]
        case AdtType(name=name, constructors=cs):
            return [name, *(c.name for c in cs),
                    *(f.name for c in cs for f in c.fields)]
        case RecordType(name=name, fields=fs):
            return [name, *(f.name for f in fs)]
        case Instance(name=name, type_args=targs):
            return [name, *targs]
        case FunctorDecl(name=name):
            return [name]
        case Component(name=name, type_params=ps, base_type_args=bs):
            return [name, *ps, *bs]
        case _:
            return [d.name]


def check_reserved_name(solver: Solver, runs: Runs) -> list[Finding]:
    """A name the solver declares that Souffle reserves, in every position
    it reads: Souffle rejects the file with a message about the token class
    it read rather than the collision, so this finding stands in for it.
    Serves readability: the author reads the collision, not the parser's
    symptom (no style line; Souffle's grammar)."""
    v = view(solver, runs)
    decls = [*v.written_relations, *v.own_types, *v.own_components,
             *v.own_instances,
             *(f for f in v.program.functors if f.span.file is None)]
    decls.sort(key=lambda d: d.span.first)
    return [lint(d.span.first, LintNamed(Category.RESERVED_NAME,
                                         LintSentence.RESERVED_WORD, (n,)))
            for d in decls for n in _declared_names(d)
            if n in RESERVED_WORDS]


def _inner_types(v: View, comp: str, seen: frozenset[str] = frozenset()
                 ) -> set[str]:
    """The type names visible inside a component: its own, its base's, and
    those of the components it instantiates."""
    c = v.components.get(comp)
    if c is None or comp in seen:
        return set()
    seen = seen | {comp}
    inner = (*c.scope.components, comp)
    names = {t.name for t in v.program.types
             if t.scope.components == inner}
    for i in v.program.instances:
        if i.scope.components == inner:
            names |= _inner_types(v, i.component, seen)
    if c.base is not None:
        names |= _inner_types(v, c.base, seen)
    return names


def check_shadowed_type(solver: Solver, runs: Runs) -> list[Finding]:
    """A type argument that collides with a type name inside the component
    it is passed to: Souffle binds both to one name, so the instance's
    relations take the wrong key type, and its message names a variable it
    could not type. Serves readability, as `check_reserved_name` does."""
    v = view(solver, runs)
    return [lint(spanned(i.span).first, LintNamed(
                Category.SHADOWED_TYPE, LintSentence.SHADOWED_TYPE,
                (t, i.component)))
            for i in v.own_instances
            for t in i.type_args if t in _inner_types(v, i.component)]


def _top(d: RelationDecl | TypeDecl | Component | Instance | FunctorDecl
         ) -> bool:
    """A declaration at the top level; a functor always is."""
    return isinstance(d, FunctorDecl) or d.scope == TOP


def _lib_names(v: View) -> dict[str, str]:
    """The lib's top-level names, each with its kind."""
    lib = [(d, kind) for ds, kind in (
        (v.program.types, "type"), (v.program.components, "component"),
        (v.program.relations, "relation"), (v.program.functors, "functor"))
        for d in ds]
    names = {d.name: kind for d, kind in lib
             if from_lib(d.span) and _top(d)}
    names |= {n: "macro" for n in v.solver.lib.constants}
    return names


def check_lib_name(solver: Solver, runs: Runs) -> list[Finding]:
    """A solver declaration that takes a lib top-level name: Souffle keeps
    types, components, instances and relations in one top-level namespace
    and functors in another, and substitutes a macro wherever its name
    stands; its message points at the lib's line for some of these.
    Serves readability, as `check_reserved_name` does."""
    v = view(solver, runs)
    lib = _lib_names(v)
    decls = [*v.own_types, *v.written_relations, *v.own_components,
             *v.own_instances,
             *(f for f in v.program.functors if f.span.file is None)]
    out: list[Finding] = []
    for d in sorted(decls, key=lambda d: d.span.first):
        kind = lib.get(d.name)
        if kind is None:
            continue
        top = _top(d)
        if kind != "macro" and (
                not top or (kind == "functor") != isinstance(d, FunctorDecl)):
            continue
        out.append(lint(d.span.first, LintNamed(
            Category.LIB_NAME, LintSentence.LIB_NAME, (d.name, kind))))
    return out


def check_lib_internal(solver: Solver, runs: Runs) -> list[Finding]:
    """A read of a `_`-prefixed lib name: a relation or instance inside a
    lib component, or a lib component instantiated. Such a name is
    private to the lib, and a component's public relations are its
    interface; serves the concept's form, which reads the lib through its
    interface (no style line)."""
    v = view(solver, runs)
    lib = v.lib_components
    comp_of = {i.name: i.component for i in v.program.instances}
    out: list[Finding] = []
    for i in v.own_instances:
        if i.component.startswith("_") and i.component in lib:
            out.append(lint(spanned(i.span).first, LintNamed(
                Category.LIB_INTERNAL, LintSentence.LIB_INTERNAL_COMP,
                (i.component,))))
    for u in v.own_units:
        for atom in (u.head, *(a.atom for a in atoms_read(u))):
            segs = (*atom.relation.instances, atom.relation.name)
            for prev, seg in zip(segs, segs[1:]):
                comp = comp_of.get(prev)
                if seg.startswith("_") and comp is not None \
                        and comp in lib:
                    out.append(lint(atom.line, LintNamed(
                        Category.LIB_INTERNAL, LintSentence.LIB_PRIVATE,
                        (seg, comp))))
                    break
    return sorted(out, key=lambda f: getattr(f.where, "line", 0))


def check_rigid_chart(solver: Solver, runs: Runs) -> list[Finding]:
    """Each atom outside a `RIGID` block that names the chart a block
    declares, which only the block's expansion reads and writes. The
    model claims the stored pose unobservable (patterns.md:98), so a read
    of it serves no concept; serves the purest form."""
    v = view(solver, runs)
    out: list[Finding] = []
    for u in v.own_units:
        if u.span is not None and v.in_rigid(u.span.first):
            continue
        for atom in (u.head, *(a.atom for a in atoms_read(u))):
            r = v.index.resolve(atom.relation, u.scope)
            d = v.decls.get(r.declaration) if isinstance(r, Resolved) \
                else None
            if isinstance(d, RelationDecl) and d.chart_of is not None:
                out.append(lint(atom.line, LintFragment(
                    Category.RIGID_CHART, atom.relation.name)))
    return out
