"""The one rendering of a part of a program for a message: a term, an
atom, a body literal, a value or a relation's declaration, as the solver
writes it."""

from collections.abc import Iterable

from engine.program import (
    AdtValue,
    Aggregate,
    Atom,
    AtomLiteral,
    BinaryTerm,
    BodyLiteral,
    BoolLiteral,
    Cast,
    Column,
    Comparison,
    ConstructorTerm,
    DefinedName,
    Disjunction,
    FunctorCall,
    GridForm,
    GridLayout,
    IntrinsicCall,
    NumberTerm,
    RecordTerm,
    RecordValue,
    RelationDecl,
    StringTerm,
    Term,
    UnaryOperator,
    UnaryTerm,
    Value,
    Variable,
    Wildcard,
)

PREFIX = "$"
"""What a constructor's name carries in a value, in a term, in a name and
in an `assign` string, as Souffle reads and prints a constructor."""


def prefixed(text: str) -> str | None:
    """What follows the constructor prefix (`PREFIX`) that `text` starts
    with; None where it starts with none."""
    return text.removeprefix(PREFIX) if text.startswith(PREFIX) else None

type Part = Term | Atom | BodyLiteral | Value | RelationDecl | GridLayout
"""What `text` renders."""


GRID_FORM_SEGMENT: dict[GridForm, str] = {
    GridForm.DENSE: "", GridForm.MASK: "MASK_", GridForm.SPARSE: "SPARSE_"}
"""The segment a GRID macro's name gives each form, after `STAMP_` and
before the size."""


def columns(cs: Iterable[Column]) -> str:
    """A relation's columns as its `.decl` line writes them between the
    parentheses."""
    return ", ".join(f"{c.name}: {c.type}" for c in cs)


def text(part: Part) -> str:
    """`part` as the solver writes it: a term with the parentheses it was
    written with and a constructor with its argument list, `$X()`, the
    form Souffle reads; a constructor value with its argument list and one
    with no fields as `$X`, the form Souffle prints; a symbol in quotes;
    a declaration as its `.decl` line; and a GRID layout as the name of
    its macro."""
    match part:
        case bool() | int() | float() | str() | AdtValue() | RecordValue():
            return _value(part, quoted=True)
        case Atom(relation=relation, args=args):
            return f"{relation.text}({_joined(args)})"
        case RelationDecl(name=name, columns=cs):
            return f".decl {name}({columns(cs)})"
        case AtomLiteral(atom=atom, negated=negated):
            return ("!" if negated else "") + text(atom)
        case Comparison(op=op, lhs=lhs, rhs=rhs):
            return f"{text(lhs)} {op.value} {text(rhs)}"
        case BoolLiteral(value=value):
            return "true" if value else "false"
        case Disjunction(branches=branches):
            return "(" + " ; ".join(_joined(b) for b in branches) + ")"
        case Variable(name=name) | DefinedName(name=name):
            return name
        case Wildcard():
            return "_"
        case NumberTerm(value=value):
            return str(value)
        case StringTerm(value=value):
            return f'"{value}"'
        case ConstructorTerm(name=name, args=args):
            return f"{PREFIX}{name}({_joined(args)})"
        case RecordTerm(args=args):
            return f"[{_joined(args)}]"
        case IntrinsicCall(functor=functor, args=args):
            return f"{functor.value}({_joined(args)})"
        case FunctorCall(name=name, args=args):
            return f"@{name}({_joined(args)})"
        case UnaryTerm(op=op, arg=arg):
            space = "" if op == UnaryOperator.NEGATE else " "
            return f"{op.value}{space}{text(arg)}"
        case BinaryTerm(op=op, lhs=lhs, rhs=rhs, parens=parens):
            inner = f"{text(lhs)} {op.value} {text(rhs)}"
            return f"({inner})" if parens else inner
        case Aggregate(op=op, expr=expr, body=body):
            e = "" if expr is None else f" {text(expr)}"
            return f"{op.value}{e} : {{ {_joined(body)} }}"
        case Cast(term=inner, type=type_name):
            return f"as({text(inner)}, {type_name})"
        case GridLayout(form=form, stamp=stamp, height=h, width=w):
            return (f"GRID_{'STAMP_' if stamp else ''}"
                    f"{GRID_FORM_SEGMENT[form]}{h}x{w}")
    raise TypeError(f"no text for {part!r}")


def line_comment(content: str) -> str:
    """A line comment of `content` as the solver writes it."""
    return f"// {content}"


def fact_text(value: Value) -> str:
    """`value` as a fact file holds it: as `text` writes it, with a symbol
    bare."""
    return _value(value, quoted=False)


def _value(value: Value, quoted: bool) -> str:
    """`value` as `text` writes it, a symbol in quotes where `quoted`."""
    match value:
        case bool():
            return str(int(value))
        case int() | float():
            return str(value)
        case str():
            return f'"{value}"' if quoted else value
        case AdtValue(constructor=name, args=()):
            return f"{PREFIX}{name}"
        case AdtValue(constructor=name, args=args):
            return f"{PREFIX}{name}(" + ", ".join(_value(a, quoted) for a in args) + ")"
        case RecordValue(fields=fields):
            return "[" + ", ".join(_value(f, quoted) for f in fields) + "]"


def _joined(parts: "tuple[Part, ...]") -> str:
    return ", ".join(text(p) for p in parts)


def split_top(text: str) -> list[str]:
    """`text` split at the commas outside brackets and parentheses, each
    part stripped; none for a text of spaces alone."""
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
