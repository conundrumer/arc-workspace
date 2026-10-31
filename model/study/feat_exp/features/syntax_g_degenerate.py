"""Group G1, a degenerate site in the form: the candidate's form, the library interfaces and the types of the sites.

An atom makes the labels that it stars (`*V`, `^V`). Where one branch of an OR stars a label that every other branch
names, every atom of the OR that names the label makes it. An atom that makes a label is an output atom, and any other
atom is a test atom. An output is live when its label is exported (`^V`) or occurs in another atom, and dead otherwise.

An atom is degenerate when a literal 0 stands at a site whose type is known and is not Number (the zero box, which
the library admits only at a Box, Position or Offset), or when one label stands at two sites that do not make it. A
literal 0 at a site where the zero box is the grid frame (`featlib.FRAME_ZERO_SITES`) is not a degenerate site: it
is counted in `zero_frame`.
"""
import collections as C

from featlib import feature, frame_zero


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
    """True where the site makes its label: a starred site, or a site of a label that the branches of an OR make."""
    return a.label is not None and (a.binds or any((orp, a.label) in made for orp, _ in a.atom.branch))


def _role(atom, made):
    """'test' (the atom makes no label), 'live' (a label it makes is exported or occurs in another atom) or 'dead'."""
    outs = [a for a in atom.arguments if _makes(a, made)]
    if not outs:
        return 'test'
    for a in outs:
        if a.key or (a.variable is not None and any(o.atom is not atom for o in a.variable.occurrences)):
            return 'live'
    return 'dead'


def _degenerate(atom):
    """(zero, repeat) of an atom."""
    zero = any(a.is_zero and a.resolved_type not in (None, 'Number') and not frame_zero(a) for a in atom.arguments)
    labels = [a.label for a in atom.arguments if a.joins]
    return zero, len(labels) != len(set(labels))


def _or_nodes(items, base=(), start=0):
    """(path, branch indexes) of each OR node of a scope's body, with the path an Atom's `branch` names it by."""
    for i in range(start, len(items)):
        it, path = items[i], base + (i,)
        if not isinstance(it, list) or not it:
            continue
        if not isinstance(it[0], str):
            yield from _or_nodes(it, path)
        elif it[0] == 'NOT':
            yield from _or_nodes(it, path, 1)
        elif it[0] == 'OR':
            branches = [k for k in range(1, len(it)) if isinstance(it[k], list)]
            yield path, branches
            for k in branches:
                yield from _or_nodes(it[k], path + (k,))
        elif it[0] in ('IF', 'ALL'):
            for k in range(1, len(it)):
                if isinstance(it[k], list):
                    yield from _or_nodes(it[k], path + (k,))


@feature
def g1_degenerate(p):
    """G1 degenerate site in the form: atoms with a literal 0 at a site that is not a Number (`zero_*`) or a label at
    two sites that do not make it (`rep_*`), by NOT (pos, neg) and by role (test, live, dead; `live_any` and `test_any`
    sum them); `zero_frame`, atoms with a literal 0 at a site where it is the grid frame; `isolated`, atoms whose sites hold no label; `or_none_clean` and `or_mixed`, the OR nodes whose branches
    all have a degenerate atom, and those where some do. The `*_dead` keys settle when the clause is finished.

    Needs: form. Monotone: partly.
    """
    body = p.clause.body
    if body is None:
        return None
    atoms = [a for a in body.atoms if a.operator is None]
    made = _made(body) if atoms else set()
    out = C.Counter()
    bad_in = set()
    for a in atoms:
        zero, repeat = _degenerate(a)
        if zero or repeat:
            side = 'neg' if a.negated else 'pos'
            role = _role(a, made)
            out[f'zero_{side}_{role}'] += zero
            out[f'rep_{side}_{role}'] += repeat
            bad_in.update(a.branch)
    keys = [f'{k}_{s}_{r}' for k in ('zero', 'rep') for s in ('pos', 'neg') for r in ('test', 'live', 'dead')]
    res = {k: out[k] for k in keys}
    res['live_any'] = sum(res[k] for k in keys if k.endswith('_live'))
    res['test_any'] = sum(res[k] for k in keys if k.endswith('_test'))
    res['zero_frame'] = sum(1 for a in atoms if any(frame_zero(x) for x in a.arguments))
    res['isolated'] = sum(1 for a in body.atoms if a.arguments and all(x.label is None for x in a.arguments))
    nodes = dict(_or_nodes(body.body))
    none_clean = mixed = 0
    for path, branches in nodes.items():
        flags = [(path, k) in bad_in for k in branches]
        none_clean += bool(flags) and all(flags)
        mixed += any(flags) and not all(flags)
    res['or_none_clean'] = none_clean
    res['or_mixed'] = mixed
    return res
