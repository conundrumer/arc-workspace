"""The lint checks on the names a solver declares and reads: the
collisions Souffle reports with a message that misleads, the lib's
private names, the charts only a `RIGID` expansion writes, and the names
of a record `Choice`'s enumerators."""

from enum import StrEnum

from checker.finding import (
    Finding,
    LintFragment,
    LintNamed,
    LintSentence,
    line_of,
)
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
    own,
)
from engine.quotes import guard, quotes
from solver.category import Category
from solver.aggregate import Solver
from solver.names import camel_words
from solver.vocabulary import CHOICE, ENUMERATOR

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


@quotes("style.md", "Identifiers",
        "Variables use a single letter with an optional digit suffix, or "
        "leading-capital snake_case. Macros: SCREAMING. Types: PascalCase. "
        "Relations: snake_case.")
def check_reserved_name(solver: Solver, runs: Runs) -> list[Finding]:
    """A name the solver declares that Souffle reserves, in every position
    it reads: Souffle rejects the file with a message about the token class
    it read rather than the collision, so this finding stands in for it.
    Serves readability: the author reads the collision, not the parser's
    symptom."""
    v = view(solver, runs)
    decls = [*v.written_relations, *v.own_types, *v.own_components,
             *v.own_instances,
             *(f for f in v.program.functors if own(f.span))]
    decls.sort(key=lambda d: d.span.first)
    return [lint(d.span.first, LintNamed(Category.RESERVED_NAME,
                                         LintSentence.RESERVED_WORD, (n,)))
            for d in decls for n in _declared_names(d)
            if n in RESERVED_WORDS]


def _inner_types(v: View, comp: Component | None,
                 seen: frozenset[Component] = frozenset()) -> set[str]:
    """The type names visible inside a component: its own, its bases'
    (`Index.chain`), and those of the components it instantiates."""
    if comp is None:
        return set()
    names: set[str] = set()
    for c in v.index.chain(comp):
        if c in seen:
            continue
        seen = seen | {c}
        inner = (*c.scope.components, c.name)
        names |= {t.name for t in v.program.types
                  if t.scope.components == inner}
        for i in v.program.instances:
            if i.scope.components == inner:
                names |= _inner_types(
                    v, v.index.component(i.component, i.scope), seen)
    return names


@quotes("style.md", "Identifiers",
        "Variables use a single letter with an optional digit suffix, or "
        "leading-capital snake_case. Macros: SCREAMING. Types: PascalCase. "
        "Relations: snake_case.")
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
            for t in i.type_args
            if t in _inner_types(v, v.index.component(i.component, i.scope))]


def _top(d: RelationDecl | TypeDecl | Component | Instance | FunctorDecl
         ) -> bool:
    """A declaration at the top level; a functor always is."""
    return isinstance(d, FunctorDecl) or d.scope == TOP


class LibKind(StrEnum):
    """The kind of a lib top-level name, as the `lib name` lint names
    it."""

    TYPE = "type"
    COMPONENT = "component"
    RELATION = "relation"
    FUNCTOR = "functor"
    MACRO = "macro"


def _lib_names(v: View) -> dict[str, LibKind]:
    """The lib's top-level names, each with its kind."""
    lib = [(d, kind) for ds, kind in (
        (v.program.types, LibKind.TYPE),
        (v.program.components, LibKind.COMPONENT),
        (v.program.relations, LibKind.RELATION),
        (v.program.functors, LibKind.FUNCTOR))
        for d in ds]
    names = {d.name: kind for d, kind in lib
             if from_lib(d.span) and _top(d)}
    names |= {n: LibKind.MACRO for n in v.solver.lib.constants}
    return names


@quotes("style.md", "Identifiers",
        "Variables use a single letter with an optional digit suffix, or "
        "leading-capital snake_case. Macros: SCREAMING. Types: PascalCase. "
        "Relations: snake_case.")
def check_lib_name(solver: Solver, runs: Runs) -> list[Finding]:
    """A solver declaration that takes a lib top-level name: Souffle keeps
    types, components, instances and relations in one top-level namespace
    and functors in another, and substitutes a macro wherever its name
    stands; its message points at the lib's line for some of these. Serves
    readability, as `check_reserved_name` does."""
    v = view(solver, runs)
    lib = _lib_names(v)
    decls = [*v.own_types, *v.written_relations, *v.own_components,
             *v.own_instances,
             *(f for f in v.program.functors if own(f.span))]
    out: list[Finding] = []
    for d in sorted(decls, key=lambda d: d.span.first):
        kind = lib.get(d.name)
        if kind is None:
            continue
        top = _top(d)
        if kind != LibKind.MACRO and (
                not top
                or (kind == LibKind.FUNCTOR) != isinstance(d, FunctorDecl)):
            continue
        out.append(lint(d.span.first, LintNamed(
            Category.LIB_NAME, LintSentence.LIB_NAME, (d.name, kind))))
    return out


@guard("A read of a `_`-prefixed lib name, which is private to the lib; "
       "the solver reads a lib component through its public relations, "
       "its interface.")
def check_lib_internal(solver: Solver, runs: Runs) -> list[Finding]:
    """A read of a `_`-prefixed lib name: a relation or instance inside a
    lib component, or a lib component instantiated. Such a name is
    private to the lib, and a component's public relations are its
    interface; serves the concept's form, which reads the lib through its
    interface (no style line)."""
    v = view(solver, runs)
    lib = v.lib_components
    out: list[Finding] = []
    for i in v.own_instances:
        if i.component.startswith("_") and i.component in lib:
            out.append(lint(spanned(i.span).first, LintNamed(
                Category.LIB_INTERNAL, LintSentence.LIB_INTERNAL_COMP,
                (i.component,))))
    for u in v.own_units:
        for atom in (u.head, *atoms_read(u)):
            r = v.index.resolve(atom.relation, u.scope)
            if not isinstance(r, Resolved):
                # A name nothing declares reads no lib name; the program
                # does not compile, which `run` reports.
                continue
            segs = (*atom.relation.instances, atom.relation.name)
            for through, seg in zip(r.through, segs[1:]):
                inst = v.program.declared(through)
                if not isinstance(inst, Instance):
                    raise ValueError(f"{through} is no instance")
                # None for an instance of a component no file declares,
                # the model's fault `INSTANCE_OF_NOTHING`.
                of = v.index.component(inst.component, inst.scope)
                if seg.startswith("_") and of is not None \
                        and from_lib(of.span):
                    out.append(lint(atom.line, LintNamed(
                        Category.LIB_INTERNAL, LintSentence.LIB_PRIVATE,
                        (seg, of.name))))
                    break
    return sorted(out, key=line_of)


@quotes("patterns.md", "`RIGID` — parameter relations coupled as a rigid assembly",
        "The block's generated names are unreadable outside the expansion "
        "(lint category 'rigid chart').")
@quotes("patterns.md", "`RIGID` — parameter relations coupled as a rigid assembly",
        "exposes them only as D4 placements that transform them together, so "
        "the stored pose is unobservable.")
def check_rigid_chart(solver: Solver, runs: Runs) -> list[Finding]:
    """Each atom outside a `RIGID` block that names the chart a block
    declares, which only the block's expansion reads and writes. A read of
    it serves no concept; serves the purest form."""
    v = view(solver, runs)
    out: list[Finding] = []
    for u in v.own_units:
        if v.program.in_rigid_body(u.id):
            continue
        for atom in (u.head, *atoms_read(u)):
            r = v.index.resolve(atom.relation, u.scope)
            d = v.decls.get(r.declaration) if isinstance(r, Resolved) \
                else None
            if isinstance(d, RelationDecl) and d.chart_of is not None:
                out.append(lint(atom.line, LintFragment(
                    Category.RIGID_CHART, atom.relation.name)))
    return out


ENUMERATOR_SUFFIX = "_choice"
"""What an enumerator's name appends to its field type's name, unless that
name ends in `Choice` already (`enumerator_name`)."""


def enumerator_name(type_name: str) -> str:
    """The name solver-file.md gives the enumerator of a record `Choice`'s
    field of type `type_name`: the type's name in snake_case, with
    `ENUMERATOR_SUFFIX` appended unless the type's name ends in
    `Choice` (`dec_choice(dc: DecChoice)`)."""
    snake = "_".join(camel_words(type_name))
    return snake if type_name.endswith(CHOICE) else snake + ENUMERATOR_SUFFIX


@quotes("solver-file.md", "Cases",
        "A record-typed `Choice` gets one enumerator per field a clause "
        "enumerates, named for the field's type.")
def check_enumerator_name(solver: Solver, runs: Runs) -> list[Finding]:
    """An enumerator of a record `Choice`'s field whose name is not the one
    the field's type gives it (`enumerator_name`). An enumerator is a
    top-level relation of the solver, other than `impl_choice`, whose every
    clause is a fact of one argument (`View.enumerators`), and it is a
    field's where its one column's type is a field's type. Serves
    readability: the enumerator's name says which field it ranges over."""
    choice = solver.choice
    if choice is None or choice.record is None:
        return []
    v = view(solver, runs)
    fields = {f.type for f in choice.record}
    enums = v.enumerators - {ENUMERATOR}
    return [lint(d.span.first, LintNamed(
                Category.ENUMERATOR_NAME, LintSentence.ENUMERATOR_NAME,
                (d.name, t, enumerator_name(t))))
            for d in sorted(v.written_relations, key=lambda d: d.span.first)
            if d.scope == TOP and d.name in enums and len(d.columns) == 1
            and (t := d.columns[0].type) in fields
            and d.name != enumerator_name(t)]
