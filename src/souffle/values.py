"""Constant terms as values, values as terms, and values as Souffle writes
them in fact files and prints them in its output."""

from engine.program import (
    AdtType,
    AdtValue,
    AliasType,
    ConstructorTerm,
    Define,
    NumberTerm,
    RecordTerm,
    RecordType,
    RecordValue,
    StringTerm,
    SubtypeType,
    Term,
    TypeDecl,
    UnionType,
    Value,
)
from engine.program import term_value
from engine.text import split_top
from souffle.index import Level, Tree


class NotConstant(Exception):
    pass


def constant(t: Term, defines: dict[str, Define]) -> Value:
    """The value a constant term states (`engine.program.term_value`), a
    defined name read through `defines`. Raises `NotConstant` for a term
    that holds a variable or a call."""

    def defined(name: str) -> Value | None:
        d = defines.get(name)
        return None if d is None or d.value is None \
            else term_value(d.value, defined)

    got = term_value(t, defined)
    if got is None:
        raise NotConstant(repr(t))
    return got


def term_of(v: Value) -> Term:
    match v:
        case bool():
            return NumberTerm(int(v))
        case int() | float():
            return NumberTerm(v)
        case str():
            return StringTerm(v)
        case RecordValue(fields):
            return RecordTerm(tuple(term_of(f) for f in fields))
        case AdtValue(name, args):
            return ConstructorTerm(name, tuple(term_of(a) for a in args))
    raise TypeError(f"not a value: {v!r}")


# Reading printed values


def _resolved(name: str, tree: Tree, place: tuple[Level, ...], start: int,
              depth: int = 0) -> tuple[TypeDecl | str, tuple[Level, ...], int]:
    """The primitive or the record or ADT declaration a type name comes to
    through aliases, subtypes and unions, with where its own names are
    read. Raises ValueError for a name nothing answers and for a union
    whose members come to different types."""
    if depth > 64:
        raise ValueError(f"type `{name}` does not end in a declaration")
    decl, inner, at = tree.resolve_type(name, place, start)
    match decl:
        case AliasType(_, _, _, target):
            return _resolved(target, tree, inner, at, depth + 1)
        case SubtypeType(_, _, _, base):
            return _resolved(base, tree, inner, at, depth + 1)
        case UnionType(_, _, _, members):
            kinds = [_resolved(m, tree, inner, at, depth + 1)[0] for m in members]
            if any(k is not kinds[0] and k != kinds[0] for k in kinds):
                raise ValueError(f"the members of union `{name}` come to different types")
            return _resolved(members[0], tree, inner, at, depth + 1)
    return decl, inner, at


def _fields(parts: list[str], types: list[str], what: str) -> list[tuple[str, str]]:
    if len(parts) != len(types):
        raise ValueError(f"{what} holds {len(parts)} values, and its type {len(types)}")
    return list(zip(parts, types, strict=True))


def printed(text: str, type_name: str, tree: Tree, place: tuple[Level, ...],
            start: int) -> Value:
    """A value as Souffle prints it in a column of type `type_name`, the
    name read at `place` in the text at `start` of the innermost chain
    (`Tree.resolve_type`). Raises ValueError where the type cannot read
    it."""
    kind, inner, at = _resolved(type_name, tree, place, start)
    if kind == "symbol":
        return text
    if kind in ("number", "unsigned"):
        return int(text)
    if kind == "float":
        return float(text)
    s = text.strip()
    if isinstance(kind, RecordType):
        if not (s.startswith("[") and s.endswith("]")):
            raise ValueError(f"`{text}` is no record of type `{type_name}`")
        return RecordValue(tuple(printed(p, t, tree, inner, at) for p, t in _fields(
            split_top(s[1:-1]), [f.type for f in kind.fields], f"`{text}`")))
    if isinstance(kind, AdtType):
        if not s.startswith("$"):
            raise ValueError(f"`{text}` is no value of type `{type_name}`")
        name, paren, rest = s[1:].partition("(")
        ctor = next((c for c in kind.constructors if c.name == name), None)
        if ctor is None or (paren and not rest.endswith(")")):
            raise ValueError(f"`{text}` is no value of type `{type_name}`")
        parts = split_top(rest[:-1]) if paren else []
        return AdtValue(name, tuple(printed(p, t, tree, inner, at) for p, t in _fields(
            parts, [f.type for f in ctor.fields], f"`{text}`")))
    raise ValueError(f"type `{type_name}` reads no printed value")
