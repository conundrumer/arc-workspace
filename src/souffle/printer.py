"""Each part of a program as Souffle text, in one canonical form."""

from engine.program import (
    AdtType,
    Aggregate,
    AliasType,
    Atom,
    AtomLiteral,
    BinaryOperator,
    BinaryTerm,
    BodyLiteral,
    BoolLiteral,
    Cast,
    Comparison,
    Component,
    ConstructorTerm,
    DefinedName,
    Disjunction,
    FunctorCall,
    FunctorDecl,
    GridCall,
    Instance,
    IntrinsicCall,
    NumberTerm,
    RecordTerm,
    RecordType,
    RelationDecl,
    RigidCall,
    StringTerm,
    SubtypeType,
    Term,
    TypeField,
    UnaryTerm,
    UnionType,
    Unit,
    Variable,
    Wildcard,
)
from engine.text import text as layout_name
from souffle.parser import BINARY, UNARY_PRECEDENCE, chart_prefix

PRECEDENCE = {op: prec for prec, op in BINARY.values()}
INDENT = "    "


def term(t: Term) -> str:
    match t:
        case Variable(name):
            return name
        case Wildcard():
            return "_"
        case NumberTerm(value):
            return repr(value) if isinstance(value, float) else str(value)
        case StringTerm(value):
            return f'"{value}"'
        case DefinedName(name):
            return name
        case ConstructorTerm(name, args):
            return f"${name}({terms(args)})"
        case RecordTerm(args):
            return f"[{terms(args)}]"
        case IntrinsicCall(functor, args):
            return f"{functor.value}({terms(args)})"
        case Cast(inner, type_name):
            return f"as({term(inner)}, {type_name})"
        case FunctorCall(name, args):
            return f"@{name}({terms(args)})"
        case UnaryTerm(op, arg):
            word = op.value if op.value == "-" else op.value + " "
            return word + _operand(arg, UNARY_PRECEDENCE + 1)
        case BinaryTerm(op, lhs, rhs):
            prec = PRECEDENCE[op]
            right = op is BinaryOperator.POW
            return (f"{_operand(lhs, prec + 1 if right else prec)} {op.value} "
                    f"{_operand(rhs, prec if right else prec + 1)}")
        case Aggregate(op, expr, body):
            lead = op.value if expr is None else f"{op.value} {term(expr)}"
            return f"{lead} : {{ {conj(body)} }}"
    raise TypeError(f"not a term: {t!r}")


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
    return f"{a.relation.text}({terms(a.args)})"


def literal(lit: BodyLiteral) -> str:
    match lit:
        case AtomLiteral(a, negated):
            return ("!" if negated else "") + atom(a)
        case Comparison(op, lhs, rhs):
            return f"{term(lhs)} {op.value} {term(rhs)}"
        case Disjunction(branches):
            return "(" + " ; ".join(conj(b) for b in branches) + ")"
        case BoolLiteral(value):
            return "true" if value else "false"
    raise TypeError(f"not a literal: {lit!r}")


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
    return ", ".join(f"{f.name}: {f.type}" if f.name else f.type for f in fs)


def type_args(args: tuple[str, ...]) -> str:
    return f"<{', '.join(args)}>" if args else ""


def declaration(d: object) -> str:
    match d:
        case SubtypeType(_, name, _, base):
            return f".type {name} <: {base}"
        case AliasType(_, name, _, target):
            return f".type {name} = {target}"
        case UnionType(_, name, _, members):
            return f".type {name} = {' | '.join(members)}"
        case RecordType(_, name, _, fs):
            return f".type {name} = [{fields(fs)}]"
        case AdtType(_, name, _, ctors):
            return f".type {name} = " + " | ".join(
                f"{c.name} {{{fields(c.fields)}}}" for c in ctors)
        case RelationDecl(_, name, _, columns, qualifiers, domain):
            cols = ", ".join(f"{c.name}: {c.type}" for c in columns)
            quals = "".join(f" {q.value}" for q in qualifiers)
            dom = f" choice-domain {', '.join(domain)}" if domain else ""
            return f".decl {name}({cols}){quals}{dom}"
        case Instance(_, name, _, comp, args):
            return f".init {name} = {comp}{type_args(args)}"
        case FunctorDecl(_, name, params, result):
            stateful = " stateful" if d.stateful else ""
            return f".functor {name}({fields(params)}): {result}{stateful}"
        case Component(_, name, _, params, base, base_args):
            extends = f" : {base}{type_args(base_args)}" if base else ""
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
    lines = [f"RIGID({call.block},"]
    for d in charts:
        cols = ", ".join(f"{c.name}: {c.type}" for c in d.columns)
        lines.append(f"{inner}.decl {d.name.removeprefix(prefix)}({cols})")
    lines += [inner + b.replace(prefix, "") for b in body]
    lines.append(f"{indent})")
    return "\n".join(lines)
