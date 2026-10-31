"""Group G2, comparisons on computed numbers: the candidate's form, the library interfaces and the types of the sites.

A comparison atom below NOT says the converse comparison (`<` becomes `>=`, `<=` becomes `>`, `=` becomes `!=`), and
the keys count the comparison that holds.
"""
import collections as C

from featlib import CONVERSE, feature

NEGATE = {'<': '>=', '>': '<=', '<=': '>', '>=': '<', '=': '!=', '!=': '='}
KIND = {'<': 'strict', '>': 'strict', '<=': 'nonstrict', '>=': 'nonstrict', '!=': 'neq', '=': 'eq'}
LIBRARY_KINDS = ('relation', 'macro')


def _made(body):
    """{(OR path, label)}: the labels that a starred site inside an OR makes and every other branch of that OR names."""
    named = C.defaultdict(lambda: C.defaultdict(set))
    for a in body.arguments:
        if a.label is None:
            continue
        for orp, b in a.atom.branch:
            named[orp, a.label][b].add(a.binds)
    out = set()
    for (orp, label), branches in named.items():
        starred = [b for b, flags in branches.items() if True in flags]
        siblings = {b for (o, _), by in named.items() if o == orp for b in by}
        if starred and set(branches) >= siblings:
            out.add((orp, label))
    return out


def _makes(a, made):
    return a.label is not None and (a.binds or any((orp, a.label) in made for orp, _ in a.atom.branch))


@feature
def g2_comparisons(p):
    """G2 comparisons on computed numbers. Against the literal 0 at a Number: `le0`, comparisons that keep only 0 or
    nothing of a Number that is never negative (`V <= 0`, `V < 0`); `ge0`, those that hold of every such Number
    (`V >= 0`). Between the numbers that two atoms of one library relation or macro make (a macro column is a number
    column when the body variable it stands for is made at one): `strict` (`<`, `>`), `nonstrict` (`<=`, `>=`), `neq`
    and `eq`. A comparison below NOT counts as its converse.

    Needs: form. Monotone: yes.
    """
    body = p.clause.body
    out = {'le0': 0, 'ge0': 0, 'strict': 0, 'nonstrict': 0, 'neq': 0, 'eq': 0}
    if body is None:
        return out
    made = _made(body)
    owner = C.defaultdict(set)      # label -> {(relation, id of the making atom)}
    for a in body.arguments:
        at = a.atom
        if at.kind in LIBRARY_KINDS and a.column_type == 'Number' and _makes(a, made):
            owner[a.label].add((at.relation, id(at)))
    for at in body.comparisons:
        u, v = at.first, at.second
        op = NEGATE.get(at.operator) if at.negated else at.operator
        if op is None or u is None or v is None:
            continue
        if u.is_zero != v.is_zero:
            x, zero_first = (v, True) if u.is_zero else (u, False)
            if x.label is None or x.resolved_type != 'Number':
                continue
            if zero_first:
                op = CONVERSE.get(op, op)
            out['le0'] += op in ('<=', '<')
            out['ge0'] += op == '>='
        elif u.label is not None and v.label is not None:
            if any(ru == rv and iu != iv for ru, iu in owner[u.label] for rv, iv in owner[v.label]):
                out[KIND[op]] += 1
    return out
