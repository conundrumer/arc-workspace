"""Round 2, explorer A: form-only features (form, library interfaces and the field types of tables before the point)."""
import collections as C

from featlib import feature, frame_zero, signature


def _made(scope):
    """The arguments that make their label. A label made outside every OR is made at its starred site. A label that an
    OR's first branch makes and every later branch names is made in each branch of that OR, at the branch's positive
    site (or `=` operand) of the label, outside NOT, ALL and IF tests, whose atom comes first in canonical order,
    wherever the stars stand."""
    out = {id(a) for a in scope.arguments if a.binds}
    branches = C.defaultdict(set)
    for a in scope.atoms:
        for orp, k in a.branch:
            branches[orp].add(k)
    for v in scope.variables.values():
        for b in v.binders:
            for orp, k in b.atom.branch:
                if k != 1:
                    continue
                picks = []
                for kk in sorted(branches[orp]):
                    occ = [a for a in v.occurrences if a.atom is not None and a.atom.branch and a.atom.branch[-1] == (orp, kk)
                           and not a.atom.negated and a.atom.conditional != 'test' and a.atom.quantifier is None
                           and (a.atom.operator is None or (a.atom.operator == '=' and a is a.atom.first))]
                    if not occ:
                        picks = None
                        break
                    picks.append(min(occ, key=lambda a: (repr(signature(a.atom)), a.name)))
                if picks:
                    out -= {id(a) for a in v.occurrences if a.atom is not None and any(o == orp for o, _ in a.atom.branch)}
                    out |= {id(a) for a in picks}
    return out


@feature
def a2_zero_sites(p):
    """A2: literal 0 at a site whose column is not a Number, split by whether the atom makes a new label.

    A producer is an atom with a site that makes its label (a starred site, or the first site in a later branch of an
    OR of a label the OR exports); any other atom is a filter. zero_prod / zero_filter count the sites holding the
    literal 0 in producer / filter atoms where the 0 is not the number zero (the site's column type, from the library
    interface or the table the atom reads, is not Number) and not the grid frame; zero_frame counts the sites where the
    0 is the grid frame (`featlib.FRAME_ZERO_SITES`), in atoms of either kind. Comparison atoms are skipped.
    """
    out = {'zero_prod': 0, 'zero_filter': 0, 'zero_frame': 0}
    body = p.clause.body
    if body is None:
        return out
    made = _made(body)
    for a in body.atoms:
        if a.operator:
            continue
        kind = 'prod' if any(id(x) in made for x in a.arguments) else 'filter'
        out['zero_' + kind] += sum(1 for x in a.arguments if x.is_zero and x.literal != 'number zero'
                                   and not frame_zero(x))
        out['zero_frame'] += sum(1 for x in a.arguments if frame_zero(x))
    return out
