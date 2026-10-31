"""Round 3, explorer F: form-only features."""
from featlib import feature, parse

LE = ('<=', '<')
GE = ('>=', '>')


def _atoms(tree):
    """Atoms of a parsed form outside NOT."""
    if isinstance(tree, list):
        if tree and isinstance(tree[0], str) and tree[0] == 'NOT':
            return
        if tree and isinstance(tree[0], str) and tree[0] != 'OR' and not tree[0].startswith(':'):
            yield tree
            return
        for t in tree:
            yield from _atoms(t)


@feature
def f4_zero_bound(p):
    """F4: comparison atoms (outside NOT) that bound a variable by the literal 0.

    le0: atoms (<= V 0), (< V 0), (>= 0 V) or (> 0 V); on a Number that is never negative they keep only V = 0 (or nothing).
    ge0: atoms (>= V 0) or (<= 0 V); on such a Number they hold in every row.
    """
    le0 = ge0 = 0
    for a in _atoms(parse(p.form)):
        if len(a) != 3 or not all(isinstance(t, str) for t in a[1:]) or a[0] not in LE + GE + ('<=', '>='):
            continue
        op, l, r = a
        if r == '0' and l != '0':
            le0 += op in LE
            ge0 += op == '>='
        elif l == '0' and r != '0':
            le0 += op in GE
            ge0 += op == '<='
    return {'le0': le0, 'ge0': ge0}
