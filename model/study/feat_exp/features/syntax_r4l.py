"""Form-only features of explorer L, round 4."""
import collections as C

from featlib import feature

TABLE_KINDS = ('fact', 'table', 'clause', 'port', 'output', 'x')
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


@feature
def l7_join_index(p):
    """L7: what makes the variables that the atoms of the form join (unstarred sites of atoms other than comparisons).

    The atoms that make a variable are its binders (the atoms that star it, and where one branch of an OR makes it,
    every atom of that OR that names it). The depth of a variable is 0 where nothing makes it, and else 1 plus the
    greatest depth of the variables that one of its binders joins (a variable that its binder joins, other than
    itself; a cycle counts 0). Over the joins: mean_depth and max_depth; `lib`, the share of joins whose variable a
    library relation or macro makes; `table`, the share whose variable an input fact or a table read makes.
    None without a join.
    """
    body = p.clause.body
    if body is None:
        return None
    made = _made(body)
    makes = lambda a: a.label is not None and (a.binds or any((orp, a.label) in made for orp, _ in a.atom.branch))
    binders = C.defaultdict(list)       # label -> atoms that make it
    for a in body.arguments:
        if makes(a) and a.atom not in binders[a.label]:
            binders[a.label].append(a.atom)
    reads = {}                          # atom -> labels it joins

    def joined(atom):
        if atom not in reads:
            reads[atom] = {a.label for a in atom.arguments if a.label is not None and not makes(a)}
        return reads[atom]

    depth = {}

    def depth_of(label, path=()):
        if label in depth:
            return depth[label]
        if label in path or not binders[label]:
            return 0
        d = 1 + max((depth_of(w, path + (label,)) for atom in binders[label] for w in joined(atom) if w != label),
                    default=0)
        depth[label] = d
        return d

    depths, lib, table = [], [], []
    for atom in body.atoms:
        if atom.operator:
            continue
        for a in atom.arguments:
            if a.label is None or makes(a):
                continue
            depths.append(depth_of(a.label))
            lib.append(any(b.kind in LIBRARY_KINDS for b in binders[a.label]))
            table.append(any(b.kind in TABLE_KINDS for b in binders[a.label]))
    if not depths:
        return None
    n = len(depths)
    return {'mean_depth': sum(depths) / n, 'max_depth': max(depths), 'lib': sum(lib) / n, 'table': sum(table) / n}
