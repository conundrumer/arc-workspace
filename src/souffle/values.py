"""Constant terms as values, and values as Souffle writes
them in fact files and prints them in its output."""

from engine.program import (
    AdtValue,
    Define,
    Primitive,
    RecordValue,
    Term,
    TypeDecl,
    TypeName,
    TypeReading,
    Value,
    ValueReading,
)
from engine.program import term_value, typed_value
from souffle.index import Level, Tree
from souffle.text import prefixed, split_top


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


# Reading printed values


type _Place = tuple[tuple[Level, ...], int]
"""Where a type name is read: the levels and the start in the text of the
innermost chain (`Tree.resolve_type`)."""


def _types(tree: Tree) -> TypeReading[_Place]:
    """The reading of a type name at a place in `tree`."""

    def read(name: TypeName, at: _Place) -> tuple[TypeDecl | Primitive, _Place]:
        decl, inner, start = tree.resolve_type(name, *at)
        return decl, (inner, start)

    return read


def _number(text: str) -> int | None:
    try:
        return int(text)
    except ValueError:
        return None


def _float(text: str) -> float | None:
    try:
        return float(text)
    except ValueError:
        return None


def _record(text: str) -> list[str] | None:
    s = text.strip()
    return split_top(s[1:-1]) if s.startswith("[") and s.endswith("]") \
        else None


def _constructor(text: str) -> tuple[str, list[str]] | None:
    written = prefixed(text.strip())
    if written is None:
        return None
    name, paren, rest = written.partition("(")
    if paren and not rest.endswith(")"):
        return None
    return name, split_top(rest[:-1]) if paren else []


def _primitive(text: str, kind: Primitive) -> Value | None:
    """A primitive's value as Souffle prints it: a symbol bare, a number
    or an unsigned as an integer, a float as a float; None where the text
    gives no value of the kind."""
    match kind:
        case Primitive.SYMBOL:
            return text
        case Primitive.FLOAT:
            return _float(text)
        case Primitive.NUMBER:
            return _number(text)
        case Primitive.UNSIGNED:
            got = _number(text)
            return None if got is None or got < 0 else got


_PRINTED = ValueReading[str](
    primitive=_primitive,
    record=_record,
    constructor=_constructor)
"""A value as Souffle prints it: a symbol bare, a record in brackets, a
constructor with its prefix and, where it has fields, its argument
list."""


def printed(text: str, type_name: TypeName, tree: Tree, place: tuple[Level, ...],
            start: int) -> Value:
    """A value as Souffle prints it in a column of type `type_name`, the
    name read at `place` in the text at `start` of the innermost chain
    (`Tree.resolve_type`), read as a value of that type
    (`engine.program.typed_value`). Raises ValueError where the type
    cannot read it."""
    got = typed_value(text, type_name, (place, start), _types(tree), _PRINTED)
    if got is None:
        raise ValueError(f"`{text}` is no value of type `{type_name.text}`")
    return got
