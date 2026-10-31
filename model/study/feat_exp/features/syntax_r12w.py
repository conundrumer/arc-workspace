"""Round 12, explorer w: form-only features, from the worst gold points."""
from featlib import feature, ORIENTATION_TYPES


def _positive_reads(p):
    return [a for a in p.clause.body.atoms
            if a.operator is None and not a.negated and a.interface is not None and a.arguments]


@feature
def w1_implied_atoms(p):
    """W1: the number of body atoms that an earlier atom already implies. An atom is implied when it is a positive read
    of a relation with at least one site, every site is a joining label (no `*` or `^`, no literal), and an earlier atom
    of the same relation, in the same conjunction and the same OR branches, has a site at every one of its columns with
    the same label (`(input (:P *P) (:Col *Col)) (input (:Col Col))`). The earlier atom already makes the later one
    true, so it restricts nothing and binds nothing.

    Needs: form. Monotone: no."""
    seen = []
    n = 0
    for a in _positive_reads(p):
        if a.quantifier or a.conditional:
            continue
        sites = {x.name: x.label for x in a.arguments}
        pure = all(x.joins and x.label is not None for x in a.arguments)
        if pure:
            for b in seen:
                if b.relation == a.relation and b.conjunction == a.conjunction and b.branch == a.branch:
                    have = {x.name: x.label for x in b.arguments if x.label is not None}
                    if all(have.get(k) == v for k, v in sites.items()):
                        n += 1
                        break
        seen.append(a)
    return n


@feature
def w2_open_orientation(p):
    """W2: the number of positive reads of a library relation or macro that give no site to a column of an orientation
    type (Dir, Axis, D4 and the like) while they give a site to another column. The read then ranges over every
    direction or axis, as `(dist_pair (:P P) (:K *K) (:K2 *K2))` does without `(:D D)`.

    Needs: form and library. Monotone: no."""
    n = 0
    for a in _positive_reads(p):
        i = a.interface
        if i.kind not in ('relation', 'macro'):
            continue
        given = {x.column for x in a.arguments if x.column}
        if not given:
            continue
        for name, c in i.columns.items():
            if getattr(c, 'type', None) in ORIENTATION_TYPES and name not in given and '.' not in name:
                n += 1
    return n
