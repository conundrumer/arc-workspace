"""The one rendering of a part of a program for a message: a term, an
atom, a body literal, a value or a relation's declaration, as the solver
writes it (`text`); a value as a fact file holds it; a line comment; and
the readings of a constructor's prefix and of a list at its top-level
commas. Each form the message rendering shares with the printer's
canonical form is written once here (`form`, `declared`, `decl_line`,
`init_head`, `rigid_head`, `unary_lead`). The packages outside `souffle` reach this module through
`engine.Engine`, whose text methods `TextMethods` gives."""

from collections.abc import Callable, Iterable

from engine.engine import Part
from engine.program import (
    AdtValue,
    Aggregate,
    Atom,
    AtomLiteral,
    BinaryTerm,
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
    NilTerm,
    NilValue,
    NumberTerm,
    RecordTerm,
    RecordValue,
    RelationDecl,
    StringTerm,
    TypeName,
    UnaryOperator,
    UnaryTerm,
    Value,
    Variable,
    Wildcard,
)

NIL_WORD = "nil"
"""How Souffle writes and prints its record constant
(`engine.program.NilTerm`)."""

PREFIX = "$"
"""What a constructor's name carries in a value, in a term, in a name and
in an `assign` string, as Souffle reads and prints a constructor."""


def prefixed(text: str) -> str | None:
    """What follows the constructor prefix (`PREFIX`) that `text` starts
    with; None where it starts with none."""
    return text.removeprefix(PREFIX) if text.startswith(PREFIX) else None


GRID_FORM_SEGMENT: dict[GridForm, str] = {
    GridForm.DENSE: "", GridForm.MASK: "MASK_", GridForm.SPARSE: "SPARSE_"}
"""The segment a GRID macro's name gives each form, after `STAMP_` and
before the size."""


def declared(pairs: Iterable[tuple[str, TypeName]]) -> str:
    """Columns or fields as a declaration writes them: each `<name>:
    <type>`, a field with no name as its type alone, joined by `, `."""
    return ", ".join(f"{name}: {t.text}" if name else t.text
                     for name, t in pairs)


def columns(cs: Iterable[Column]) -> str:
    """A relation's columns as its `.decl` line writes them between the
    parentheses."""
    return declared((c.name, c.type) for c in cs)


def decl_line(name: str, cs: Iterable[Column]) -> str:
    """A relation's `.decl` line with no qualifier: its name and its
    columns."""
    return f".decl {name}({columns(cs)})"


def init_head(instance: str) -> str:
    """An `.init` line up to its instance's name."""
    return f".init {instance}"


def rigid_head(block: str) -> str:
    """A RIGID call up to the comma after its block's name."""
    return f"RIGID({block},"


def rigid_elided(block: str) -> str:
    """A RIGID call with its body elided, as a message names it."""
    return f"{rigid_head(block)} …)"


def unary_lead(op: UnaryOperator) -> str:
    """A unary operator as it stands before its operand."""
    return op.value if op == UnaryOperator.NEGATE else op.value + " "


def form(part: Part, of: Callable[[Part], str]) -> str:
    """`part` in the form the message rendering and the printer share,
    each part inside it as `of` writes it. Raises `TypeError` for a unary
    or binary term, whose parentheses each renderer writes its own way,
    and for a value, a declaration and a GRID layout."""
    def joined(parts: "tuple[Part, ...]") -> str:
        return ", ".join(of(p) for p in parts)

    match part:
        case Atom(relation=relation, args=args):
            return f"{relation.text}({joined(args)})"
        case AtomLiteral(atom=atom, negated=negated):
            return ("!" if negated else "") + of(atom)
        case Comparison(op=op, lhs=lhs, rhs=rhs):
            return f"{of(lhs)} {op.value} {of(rhs)}"
        case BoolLiteral(value=value):
            return "true" if value else "false"
        case Disjunction(branches=branches):
            return "(" + " ; ".join(joined(b) for b in branches) + ")"
        case Variable(name=name) | DefinedName(name=name):
            return name
        case Wildcard():
            return "_"
        case NilTerm():
            return NIL_WORD
        case NumberTerm(value=value):
            return str(value)
        case StringTerm(value=value):
            return f'"{value}"'
        case ConstructorTerm(name=name, args=args):
            return f"{PREFIX}{name}({joined(args)})"
        case RecordTerm(args=args):
            return f"[{joined(args)}]"
        case IntrinsicCall(functor=functor, args=args):
            return f"{functor.value}({joined(args)})"
        case FunctorCall(name=name, args=args):
            return f"@{name}({joined(args)})"
        case Aggregate(op=op, expr=expr, body=body):
            lead = op.value if expr is None else f"{op.value} {of(expr)}"
            return f"{lead} : {{ {joined(body)} }}"
        case Cast(term=inner, type=type_name):
            return f"as({of(inner)}, {type_name.text})"
    raise TypeError(f"no shared form for {part!r}")


def text(part: Part) -> str:
    """`part` as the solver writes it: a term with the parentheses it was
    written with and a constructor with its argument list, `$X()`, the
    form Souffle reads; a constructor value with its argument list and one
    with no fields as `$X`, the form Souffle prints; a symbol in quotes;
    a declaration as its `.decl` line; and a GRID layout as the name of
    its macro."""
    match part:
        case bool() | int() | float() | str() | AdtValue() | RecordValue() \
                | NilValue():
            return _value(part, quoted=True)
        case RelationDecl(name=name, columns=cs):
            return decl_line(name, cs)
        case UnaryTerm(op=op, arg=arg):
            return unary_lead(op) + text(arg)
        case BinaryTerm(op=op, lhs=lhs, rhs=rhs, parens=parens):
            inner = f"{text(lhs)} {op.value} {text(rhs)}"
            return f"({inner})" if parens else inner
        case GridLayout(form=grid_form, stamp=stamp, height=h, width=w):
            return (f"GRID_{'STAMP_' if stamp else ''}"
                    f"{GRID_FORM_SEGMENT[grid_form]}{h}x{w}")
    return form(part, text)


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
        case NilValue():
            return NIL_WORD


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


class TextMethods:
    """The methods of `engine.Engine` that render or read Souffle text,
    each one function of this module, for each engine over Souffle text to
    take."""

    def text(self, part: Part) -> str:
        return text(part)

    def prefixed(self, text: str) -> str | None:
        return prefixed(text)

    def line_comment(self, content: str) -> str:
        return line_comment(content)

    def split_top(self, text: str) -> list[str]:
        return split_top(text)

    def constructor_prefix(self) -> str:
        return PREFIX

    def init_text(self, instance: str) -> str:
        return init_head(instance)

    def rigid_text(self, block: str) -> str:
        return rigid_elided(block)
