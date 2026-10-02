"""What a run's cache key holds beyond the text of its statements: the
files a parsed program includes, with their bytes; and the declarations a
run's text holds, those its units reach."""

from collections.abc import Iterable, Iterator
from dataclasses import replace

from engine.memo import ByIdentity
from engine.program import (
    AdtType,
    Aggregate,
    AliasType,
    BodyLiteral,
    Cast,
    ConstructorTerm,
    DeclId,
    Disjunction,
    GridCall,
    Program,
    RecordType,
    RelationDecl,
    SubtypeType,
    Term,
    TypeDecl,
    UnionType,
    own,
    literal_terms,
    subterms,
)
from souffle.index import index_of
from souffle.layout import CompBlock, IncludeBlock, Layout, Segment, layout_of

_INCLUDED: ByIdentity[Layout, tuple[str, ...]] = ByIdentity()


def _included(segments: tuple[Segment, ...]) -> list[str]:
    out: list[str] = []
    for s in segments:
        if isinstance(s, IncludeBlock):
            out.append(s.path)
            out += _included(s.body)
        elif isinstance(s, CompBlock):
            out += _included(s.body)
    return out


def included_files(program: Program) -> tuple[str, ...]:
    """The path of each file the program's layout includes, in the order
    the layout holds them; read once per layout while it lives, as the
    programs an operation derives from one share its layout."""
    layout = layout_of(program)
    return _INCLUDED.compute(layout, lambda: tuple(_included(layout.segments)))


_REACHED: ByIdentity[Program, dict[frozenset[DeclId], Program]] = ByIdentity()


def reached(program: Program, named: Iterable[DeclId]) -> Program:
    """`program` with the declarations a run of it reads: without each
    relation declaration of its own text that no unit or macro call feeds
    or reads, other than those of `named` (the relations the run reads in
    or prints), and without each type declaration of its own text that no
    declaration it keeps, unit, macro call, instance, functor or `#define`
    names. An included file's declarations stay, since the run's text names
    the file whole. Computed once per program and `named` while the
    program lives, as a group's program runs on every input."""
    key = frozenset(named)
    return _REACHED.keyed(program, key, lambda: _reached(program, key))


def _reached(program: Program, named: frozenset[DeclId]) -> Program:
    index = index_of(program)
    bound = {r.id for r in program.relations
             if r.chart_of is not None
             or program.rigid_bound(r)}
    relations = tuple(
        r for r in program.relations
        if not own(r.span) or r.id in named or r.id in bound
        or index.feeding(r.id) or index.reading(r.id))
    types = program.types
    if all(d.value is not None for d in program.defines):
        types = _named_types(program, relations)
    if len(relations) == len(program.relations) and len(types) == len(program.types):
        return program
    return replace(program, relations=relations, types=types)


def _named_types(program: Program, relations: tuple[RelationDecl, ...]
                 ) -> tuple[TypeDecl, ...]:
    """The type declarations of `program` that stay with `relations`
    (`reached`): each not of its own text, and each that a name it reaches
    names, through the types it keeps. A name is matched by its last part,
    so that a qualified name keeps every type of that name."""
    names: set[str] = set()
    for r in relations:
        names.update(c.type for c in r.columns)
    for c in program.components:
        names.update(c.base_type_args)
    for i in program.instances:
        names.update(i.type_args)
    for f in program.functors:
        names.update(p.type for p in f.params)
        names.add(f.result)
    terms: list[Term] = [d.value for d in program.defines if d.value is not None]
    for u in program.units:
        terms += u.head.args
        if u.body is not None:
            terms += _body_terms(u.body)
    for m in program.macros:
        if isinstance(m, GridCall):
            terms += m.keys
            terms += [c.term for row in m.cells for c in row]
    constructors: set[str] = set()
    for t in terms:
        _term_names(t, names, constructors)
    by_ctor = {c.name.lstrip("$"): t.name for t in program.types
               if isinstance(t, AdtType) for c in t.constructors}
    names.update(by_ctor[c] for c in constructors if c in by_ctor)
    names = {n.rsplit(".", 1)[-1] for n in names}
    kept: dict[DeclId, TypeDecl] = {t.id: t for t in program.types if not own(t.span)}
    for t in kept.values():
        names.update(_type_refs(t))
    while True:
        more = [t for t in program.types
                if t.id not in kept and t.name in names]
        if not more:
            break
        for t in more:
            kept[t.id] = t
            names.update(n.rsplit(".", 1)[-1] for n in _type_refs(t))
    return tuple(t for t in program.types if t.id in kept)


def _type_refs(t: TypeDecl) -> Iterator[str]:
    """The type names a type declaration names."""
    match t:
        case AdtType():
            for c in t.constructors:
                yield from (f.type for f in c.fields)
        case RecordType():
            yield from (f.type for f in t.fields)
        case AliasType():
            yield t.target
        case SubtypeType():
            yield t.base
        case UnionType():
            yield from t.members


def _body_terms(body: tuple[BodyLiteral, ...]) -> Iterator[Term]:
    for lit in body:
        if isinstance(lit, Disjunction):
            for branch in lit.branches:
                yield from _body_terms(branch)
        else:
            yield from literal_terms(lit)


def _term_names(t: Term, types: set[str], constructors: set[str]) -> None:
    """Add the type names `t` casts to into `types`, and the constructor
    names it applies into `constructors`."""
    match t:
        case Cast(type=type_):
            types.add(type_)
        case ConstructorTerm(name=name):
            constructors.add(name.lstrip("$"))
        case Aggregate(expr=expr, body=body):
            if expr is not None:
                _term_names(expr, types, constructors)
            for b in _body_terms(body):
                _term_names(b, types, constructors)
    for a in subterms(t):
        _term_names(a, types, constructors)
