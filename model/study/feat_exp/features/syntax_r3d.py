"""Form-only features of explorer D, round 3: the form, the library interfaces and the types of the sites."""
import collections as C

from featlib import feature

COMPARE = {'<': 'strict', '>': 'strict', '<=': 'nonstrict', '>=': 'nonstrict', '!=': 'neq', '=': 'eq'}
LIBRARY_KINDS = ('relation', 'macro')


def _made(body):
    """{(OR path, label)}: the labels that a starred site inside an OR makes and every other branch of that OR names.
    Where one branch stars such a label, the text puts the star at one site, and every atom of the OR that names the
    label makes it."""
    named = C.defaultdict(lambda: C.defaultdict(set))
    for a in body.arguments:
        if a.label is None:
            continue
        for orp, b in a.atom.branch:
            named[orp, a.label][b].add(a.binds)
    out = set()
    for (orp, label), branches in named.items():
        siblings = {b for (o, _), by in named.items() if o == orp for b in by}
        if any(True in flags for flags in branches.values()) and set(branches) >= siblings:
            out.add((orp, label))
    return out


def _makes(a, made):
    """True where the site makes its label: a starred site, or a site of a label that the branches of an OR make."""
    return a.label is not None and (a.binds or any((orp, a.label) in made for orp, _ in a.atom.branch))


@feature
def d7_pair_comparison(p):
    """D7: comparison atoms (<, >, <=, >=, !=, =) between two variables that two atoms of the same library relation or macro make at number columns (such as two margin atoms, or two box_extent atoms; a macro column is a number column when the body variable it stands for is made at one): counts of strict, nonstrict, neq and eq ones; and `uncompared`, the number of such relations with two or more making atoms where no comparison atom joins two of their variables."""
    body = p.clause.body
    out = {'strict': 0, 'nonstrict': 0, 'neq': 0, 'eq': 0, 'uncompared': 0}
    if body is None:
        return {k: float(v) for k, v in out.items()}
    made = _made(body)
    makers = C.defaultdict(lambda: C.defaultdict(set))   # relation -> atoms that make it a label -> labels
    owner = C.defaultdict(set)                           # label -> {(relation, atom)}
    for a in body.arguments:
        at = a.atom
        if at.kind in LIBRARY_KINDS and a.column_type == 'Number' and _makes(a, made):
            makers[at.relation][id(at)].add(a.label)
            owner[a.label].add((at.relation, id(at)))
    compared = set()
    for at in body.comparisons:
        kind = COMPARE.get(at.operator)
        u, v = at.first, at.second
        if kind is None or u is None or v is None or u.label is None or v.label is None:
            continue
        if any(ru == rv and iu != iv for ru, iu in owner[u.label] for rv, iv in owner[v.label]):
            out[kind] += 1
            compared |= {ru for ru, iu in owner[u.label] for rv, iv in owner[v.label] if ru == rv and iu != iv}
    out['uncompared'] = sum(1 for rel, atoms in makers.items() if len(atoms) >= 2 and rel not in compared)
    return {k: float(v) for k, v in out.items()}
