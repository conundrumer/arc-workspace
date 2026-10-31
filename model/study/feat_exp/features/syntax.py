"""Syntax of the candidate's form alone, as the search sees a proposed clause.

These features can learn patterns of the mutation generator instead of validity, so the
report fits every model with and without this family (`features.py --syntax`).
"""
import collections as C

from featlib import feature, parse


def _forms(tree, out):
    if isinstance(tree, list):
        if tree and tree[0] == 'OR':
            out['or'] += 1
            out['branches'] += sum(len(b) for b in tree[1:] if isinstance(b, list))
        if tree and tree[0] == 'NOT':
            out['not'] += 1
        if tree and tree[0] in ('OR', 'NOT', 'IF', 'ALL'):
            out['forms'] += 1
        for s in tree:
            _forms(s, out)


@feature
def form(p):
    """Counts over the candidate's typed body: atoms (relations and comparisons), OR forms and their conjuncts, NOT
    forms, atoms per library relation or fact (`rel:<name>`; reads of relations declared before the point count
    under `rel:&`, and `>` and `>=` under `<` and `<=`), sites, literal 0 at sites, labels made with `*` and `^` and joined, labels at two sites of one
    atom, labels, labels with one occurrence that the form makes (a label made outside the form, such as an INIT key variable, is not counted), atoms that repeat another up to binding marks, and the size
    (atoms + arguments + forms)."""
    body = p.clause.body
    if body is None:
        return None
    out = C.Counter()
    out['atoms'] = len(body.atoms)
    _forms(parse(p.form), out)
    keys = C.Counter()
    for a in body.atoms:
        derived = a.relation.startswith('&')
        rel = {'>': '<', '>=': '<='}.get(a.relation, a.relation)
        out['rel:' + ('&' if derived else rel)] += 1
        out['reads' if derived else 'lib_atoms'] += 1
        if not a.operator:
            out['sites'] += len({x.path[-2] for x in a.arguments})
            out['zero'] += sum(x.is_zero for x in a.arguments)
            seen = C.Counter(x.label for x in a.arguments if x.label)
            out['self_join'] += sum(k > 1 for k in seen.values())
        for x in a.arguments:
            if x.binds:
                out['caret' if x.key else 'bind'] += 1
            elif x.label:
                out['join'] += 1
        keys[a.key()] += 1
    out['vars'] = len(body.variables)
    out['singleton_vars'] = sum(len(v.occurrences) == 1 and bool(v.binders) for v in body.variables.values())
    out['dup_atoms'] = sum(k - 1 for k in keys.values())
    out['tokens'] = len(body.atoms) + len(body.arguments) + out.pop('forms', 0)
    return dict(out)
