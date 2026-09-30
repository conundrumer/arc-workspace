"""Constant terms as values, values as terms, and values as Souffle writes
them in fact files and prints them in its output."""

from engine.program import (
    AdtType,
    AdtValue,
    AliasType,
    BinaryOperator,
    BinaryTerm,
    Cast,
    ConstructorTerm,
    Define,
    DefinedName,
    NumberTerm,
    RecordTerm,
    RecordType,
    RecordValue,
    StringTerm,
    SubtypeType,
    Term,
    TypeDecl,
    UnaryOperator,
    UnaryTerm,
    UnionType,
    Value,
)
from souffle.index import Level, Tree


class NotConstant(Exception):
    pass


def constant(t: Term, defines: dict[str, Define]) -> Value:
    """The value a constant term states. Raises `NotConstant` for a term
    that holds a variable or a call."""
    match t:
        case NumberTerm(v):
            return v
        case StringTerm(v):
            return v
        case RecordTerm(args):
            return RecordValue(tuple(constant(a, defines) for a in args))
        case ConstructorTerm(name, args):
            return AdtValue(name, tuple(constant(a, defines) for a in args))
        case DefinedName(name) if name in defines and defines[name].value is not None:
            value = defines[name].value
            assert value is not None
            return constant(value, defines)
        case Cast(arg, _):
            return constant(arg, defines)
        case UnaryTerm(UnaryOperator.NEGATE, arg):
            v = constant(arg, defines)
            if isinstance(v, int | float):
                return -v
        case BinaryTerm(op, lhs, rhs):
            a, b = constant(lhs, defines), constant(rhs, defines)
            if isinstance(a, int) and isinstance(b, int):
                folded = _fold(op, a, b)
                if folded is not None:
                    return folded
    raise NotConstant(repr(t))


def _fold(op: BinaryOperator, a: int, b: int) -> int | None:
    match op:
        case BinaryOperator.ADD:
            return a + b
        case BinaryOperator.SUB:
            return a - b
        case BinaryOperator.MUL:
            return a * b
    return None


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


def _split(text: str) -> list[str]:
    """`text` split at the commas outside brackets and parentheses."""
    parts: list[str] = []
    depth, start = 0, 0
    for i, ch in enumerate(text):
        if ch in "([":
            depth += 1
        elif ch in ")]":
            depth -= 1
        elif ch == "," and depth == 0:
            parts.append(text[start:i].strip())
            start = i + 1
    parts.append(text[start:].strip())
    return [] if parts == [""] else parts


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
            _split(s[1:-1]), [f.type for f in kind.fields], f"`{text}`")))
    if isinstance(kind, AdtType):
        if not s.startswith("$"):
            raise ValueError(f"`{text}` is no value of type `{type_name}`")
        name, paren, rest = s[1:].partition("(")
        ctor = next((c for c in kind.constructors if c.name == name), None)
        if ctor is None or (paren and not rest.endswith(")")):
            raise ValueError(f"`{text}` is no value of type `{type_name}`")
        parts = _split(rest[:-1]) if paren else []
        return AdtValue(name, tuple(printed(p, t, tree, inner, at) for p, t in _fields(
            parts, [f.type for f in ctor.fields], f"`{text}`")))
    raise ValueError(f"type `{type_name}` reads no printed value")
