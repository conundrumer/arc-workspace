"""The `@open` parameters whose open values are orders, and the retyping
that drops their key column.

An order parameter is an `@open` Params relation of three columns whose
`OpenValue` field's record names one column, the key, and whose stored
rows, grouped by the key, are each bijection between the values of its
two other columns, and no other rows. Its key column, and each column of
a derived relation that a variable bound at the key reaches, takes that
record type, so the converter drops each of them as it drops a column of
an open type. The parameter's `DET` gives a row for each pair of a value
of one value column and a value of the other, from the `Determine`
relation of those pairs (`solver.vocabulary.order_pairs`), and ends in a
`ONE` mark on each value column, so that each order is one model.
"""

from dataclasses import dataclass, replace as dc_replace
from math import factorial

from engine.program import (
    Atom,
    AtomLiteral,
    Disjunction,
    Program,
    RecordType,
    TypeName,
    Variable,
)

type RelKey = tuple[tuple[str, ...], str]


@dataclass(frozen=True)
class Order:
    """An order parameter: its key column's index, the record type its key
    takes, and the indices of its two value columns."""

    key: int
    record: str
    values: tuple[int, int]


def is_orders(rows: list[tuple], key: int, values: tuple[int, int]) -> bool:
    """`rows`, grouped by column `key`, are each bijection between the
    values column `values[0]` holds and those column `values[1]` holds, and
    no other rows."""
    a, b = values
    left = {r[a] for r in rows}
    right = {r[b] for r in rows}
    if len(left) != len(right):
        return False
    groups: dict[object, set[tuple]] = {}
    for r in rows:
        groups.setdefault(r[key], set()).add((r[a], r[b]))
    for pairs in groups.values():
        if len(pairs) != len(left) or {x for x, _ in pairs} != left or {y for _, y in pairs} != right:
            return False
    return len({frozenset(p) for p in groups.values()}) == len(groups) == factorial(len(left))


def orders(prog: Program, open_params: set[str], types: dict[RelKey, object]) -> dict[str, Order]:
    """The order parameters among `open_params`, by name, from the solver's
    `OpenValue` record among `types`."""
    open_value = types.get(((), "OpenValue"))
    if not isinstance(open_value, RecordType):
        return {}
    facts: dict[str, list[tuple]] = {}
    for u in prog.units:
        if u.scope.components == ("Params",) and u.body is None and not u.head.relation.instances:
            facts.setdefault(u.head.relation.name, []).append(u.head.args)
    out = {}
    for r in prog.relations:
        if r.scope.components != ("Params",) or r.name not in open_params or len(r.columns) != 3:
            continue
        field = next((f for f in open_value.fields if f.name == r.name), None)
        record = types.get(((), field.type.name)) if field is not None else None
        if not isinstance(record, RecordType) or len(record.fields) != 1:
            continue
        names = [c.name for c in r.columns]
        if record.fields[0].name not in names:
            continue
        key = names.index(record.fields[0].name)
        a, b = (i for i in range(3) if i != key)
        if is_orders(facts.get(r.name, []), key, (a, b)):
            out[r.name] = Order(key, record.name, (a, b))
    return out


def keys_retyped(prog: Program, found: dict[str, Order]) -> Program:
    """`prog` with the key column of each order parameter, and each column
    of a relation that a clause's head fills with a variable bound at such
    a column, of that order's record type."""
    if not found:
        return prog
    rels: dict[RelKey, object] = {(r.scope.components, r.name): r for r in prog.relations}
    typed: dict[tuple[RelKey, int], str] = {
        ((("Params",), n), o.key): o.record for n, o in found.items()}

    def resolve(a: Atom, scope: tuple[str, ...]) -> RelKey | None:
        if a.relation.instances == ("params",):
            return ("Params",), a.relation.name
        if a.relation.instances:
            return None
        for k in range(len(scope), -1, -1):
            if (scope[:k], a.relation.name) in rels:
                return scope[:k], a.relation.name
        return None

    def bound(lits, scope, out: dict[str, str]) -> None:
        for l in lits:
            if isinstance(l, AtomLiteral) and not l.negated:
                k = resolve(l.atom, scope)
                for i, t in enumerate(l.atom.args):
                    if isinstance(t, Variable) and (k, i) in typed:
                        out[t.name] = typed[(k, i)]
            elif isinstance(l, Disjunction):
                for br in l.branches:
                    bound(br, scope, out)

    changed = True
    while changed:
        changed = False
        for u in prog.units:
            if u.body is None:
                continue
            vs: dict[str, str] = {}
            bound(u.body, u.scope.components, vs)
            k = resolve(u.head, u.scope.components)
            if k is None:
                continue
            for i, t in enumerate(u.head.args):
                if isinstance(t, Variable) and t.name in vs and (k, i) not in typed:
                    typed[(k, i)] = vs[t.name]
                    changed = True

    def retyped(r):
        k = (r.scope.components, r.name)
        cols = tuple(dc_replace(c, type=TypeName((), typed[(k, i)])) if (k, i) in typed else c
                     for i, c in enumerate(r.columns))
        return r if cols == r.columns else dc_replace(r, columns=cols)
    return dc_replace(prog, relations=tuple(retyped(r) for r in prog.relations))

