"""Each part of a program as Souffle text, in one canonical form."""

from engine.engine import Part
from engine.program import (
    AdtType,
    Aggregate,
    AliasType,
    Atom,
    AtomLiteral,
    BinaryOperator,
    BinaryTerm,
    BodyLiteral,
    Column,
    Component,
    FunctorDecl,
    GridCall,
    Instance,
    NumberTerm,
    Qualifier,
    RecordType,
    RelationDecl,
    RigidCall,
    SubtypeType,
    Term,
    TypeField,
    TypeName,
    UnaryTerm,
    UnionType,
    Unit,
)
from souffle.parser import BINARY, UNARY_PRECEDENCE, chart_prefix
from souffle.text import (columns, decl_line, declared, form, init_head,
                          rigid_head, unary_lead)
from souffle.text import text as layout_name

PRECEDENCE = {op: prec for prec, op in BINARY.values()}
INDENT = "    "


def term(t: Term) -> str:
    return _part(t)


def _part(p: Part) -> str:
    """`p` in the canonical form: a unary or binary term with the
    parentheses its operands need, any other part in the form the message
    rendering shares (`souffle.text.form`)."""
    match p:
        case UnaryTerm(op, arg):
            return unary_lead(op) + _operand(arg, UNARY_PRECEDENCE + 1)
        case BinaryTerm(op, lhs, rhs):
            prec = PRECEDENCE[op]
            right = op is BinaryOperator.POW
            return (f"{_operand(lhs, prec + 1 if right else prec)} {op.value} "
                    f"{_operand(rhs, prec if right else prec + 1)}")
    return form(p, _part)


def _operand(t: Term, least: int) -> str:
    """`t` as an operand that binds at least as tight as `least`."""
    text = term(t)
    if isinstance(t, BinaryTerm) and PRECEDENCE[t.op] < least:
        return f"({text})"
    if isinstance(t, UnaryTerm | Aggregate) and least > UNARY_PRECEDENCE:
        return f"({text})"
    if isinstance(t, NumberTerm) and t.value < 0 and least > UNARY_PRECEDENCE:
        return f"({text})"
    return text


def terms(ts: tuple[Term, ...]) -> str:
    return ", ".join(term(t) for t in ts)


def atom(a: Atom) -> str:
    return _part(a)


def literal(lit: BodyLiteral) -> str:
    return _part(lit)


def conj(body: tuple[BodyLiteral, ...]) -> str:
    return ", ".join(literal(b) for b in body)


def unit(u: Unit) -> str:
    plan = ""
    if u.plan is not None:
        plan = " .plan " + ", ".join(
            f"{v}:({', '.join(str(i) for i in order)})" for v, order in u.plan.orders)
    if u.body is None:
        return f"{atom(u.head)}.{plan}"
    if u.subsumptive and u.body and isinstance(u.body[0], AtomLiteral):
        rest = u.body[1:]
        return (f"{atom(u.head)} <= {atom(u.body[0].atom)}"
                + (f" :- {conj(rest)}" if rest else " :- true") + f".{plan}")
    return f"{atom(u.head)} :- {conj(u.body)}.{plan}"


def fields(fs: tuple[TypeField, ...]) -> str:
    return declared((f.name, f.type) for f in fs)


def type_args(args: tuple[str, ...]) -> str:
    return f"<{', '.join(args)}>" if args else ""


def type_arg_texts(args: tuple[TypeName, ...]) -> str:
    return type_args(tuple(a.text for a in args))


def signature(cs: tuple[Column, ...], qualifiers: tuple[Qualifier, ...],
              domain: tuple[str, ...]) -> str:
    """A relation declaration after its name."""
    quals = "".join(f" {q.value}" for q in qualifiers)
    dom = f" choice-domain {', '.join(domain)}" if domain else ""
    return f"({columns(cs)}){quals}{dom}"


def subtypes(names: tuple[str, ...], base: str) -> str:
    return f".type {', '.join(names)} <: {base}"


def declaration(d: object) -> str:
    match d:
        case SubtypeType(_, name, _, base):
            return subtypes((name,), base.text)
        case AliasType(_, name, _, target):
            return f".type {name} = {target.text}"
        case UnionType(_, name, _, members):
            return f".type {name} = {' | '.join(m.text for m in members)}"
        case RecordType(_, name, _, fs):
            return f".type {name} = [{fields(fs)}]"
        case AdtType(_, name, _, ctors):
            return f".type {name} = " + " | ".join(
                f"{c.name} {{{fields(c.fields)}}}" for c in ctors)
        case RelationDecl(_, name, _, cs, qualifiers, domain):
            return f".decl {name}{signature(cs, qualifiers, domain)}"
        case Instance(_, name, _, comp, args):
            return f"{init_head(name)} = {comp}{type_arg_texts(args)}"
        case FunctorDecl(_, name, params, result):
            stateful = " stateful" if d.stateful else ""
            return f".functor {name}({fields(params)}): {result.text}{stateful}"
        case Component(_, name, _, params, base, base_args):
            extends = f" : {base}{type_arg_texts(base_args)}" if base else ""
            return f".comp {name}{type_args(params)}{extends} {{"
    raise TypeError(f"not a declaration: {d!r}")


def grid_call(call: GridCall, indent: str) -> str:
    head = ", ".join([call.relation.text, *(term(k) for k in call.keys)])
    rows = f",\n{indent}{INDENT}".join(", ".join(("@" if c.anchor else "") + term(c.term)
                                                 for c in row)
                                       for row in call.cells)
    return f"{layout_name(call.layout)}({head},\n{indent}{INDENT}{rows})"


def rigid_call(call: RigidCall, charts: list[RelationDecl], body: list[str],
               indent: str) -> str:
    """A RIGID call, from its chart declarations and the text of each
    statement of its body, with chart names as the body writes them."""
    prefix = chart_prefix(call.block)
    inner = indent + INDENT
    lines = [rigid_head(call.block)]
    for d in charts:
        lines.append(inner + decl_line(d.name.removeprefix(prefix), d.columns))
    lines += [inner + b.replace(prefix, "") for b in body]
    lines.append(f"{indent})")
    return "\n".join(lines)
